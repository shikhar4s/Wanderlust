import React,{useEffect,useMemo,useState} from 'react';
import {Link,useParams} from 'react-router-dom';
import {MapContainer,TileLayer,Marker,Polyline,Popup,useMap} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {api} from './api';
import {Plus,Save,RotateCcw,Route as RouteIcon,Trash2,MapPin,GripVertical} from 'lucide-react';

const fallback='https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=80';
function Fit({stops,focus}){
 const map=useMap();
 useEffect(()=>{const points=stops.map(s=>[s.place.latitude,s.place.longitude]);if(points.length>1)map.fitBounds(points,{padding:[35,35]});else if(points.length)map.setView(points[0],13)},[map,stops]);
 useEffect(()=>{if(focus)map.flyTo([focus.place.latitude,focus.place.longitude],15)},[map,focus]);
 return null;
}
function RouteMap({stops,focus,onFocus}){
 const center=stops.length?[stops[0].place.latitude,stops[0].place.longitude]:[24.5854,73.7125];
 return <MapContainer center={center} zoom={12} className="realMap" scrollWheelZoom={false}><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><Fit stops={stops} focus={focus}/>{stops.length>1&&<Polyline positions={stops.map(s=>[s.place.latitude,s.place.longitude])} color="#0866ee" weight={4}/ >}{stops.map((s,i)=><Marker key={s.id} position={[s.place.latitude,s.place.longitude]} icon={L.divIcon({className:'routeMarker',html:`<span>${i+1}</span>`,iconSize:[30,30]})} eventHandlers={{click:()=>onFocus(s)}}><Popup>{s.place.name}</Popup></Marker>)}</MapContainer>;
}

export default function TripPlanner(){
 const {id}=useParams();const [trip,setTrip]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[active,setActive]=useState(0),[focus,setFocus]=useState(null),[draft,setDraft]=useState(null),[places,setPlaces]=useState([]),[addOpen,setAddOpen]=useState(false);
 const days=trip?.days||[];const day=days[active];
 useEffect(()=>{api(`/trips/${id}/`).then(setTrip).catch(e=>setError(e.message))},[id]);
 useEffect(()=>{if(trip)api(`/places/?destination=${trip.destination}`).then(r=>setPlaces(r.results||r)).catch(()=>{})},[trip?.destination]);
 function update(next){setTrip(next);setDraft(null);setError('')}
 async function mutate(path,body){setBusy(true);setError('');try{update(await api(`/trips/${id}/${path}/`,{body}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 function move(from,to,source=active,target=active){const groups=(draft||days.map(d=>d.stops.map(s=>s.id))).map(ids=>[...ids]);const [item]=groups[source].splice(from,1);groups[target].splice(to,0,item);setDraft(groups)}
 async function saveOrder(){if(!draft)return;await mutate('edit_stops',{days:draft})}
 const shown=draft?draft[active].map(sid=>days.flatMap(d=>d.stops).find(s=>s.id===sid)):day?.stops||[];
 const stopCount=days.reduce((n,d)=>n+d.stops.length,0);
 if(!trip)return <div className="page"><div className="state">{error||'Loading trip…'}</div></div>;
 if(!days.length)return <div className="page"><h1>{trip.title}</h1><div className="state">This trip has no itinerary yet. Search the destination and add places to build one.</div><Link className="signupLink" to="/discover">Discover places</Link></div>;
 return <div className="page tripWorkspace"><div className="pageTitle"><div><span className="kicker">YOUR TRIP PLANNER</span><h1>{trip.title}</h1><p>{trip.start_date} → {trip.end_date} · {days.length} days · {stopCount} places</p></div><div className="toolbar"><button className="outline" onClick={()=>mutate('optimize',{day_id:day.id})} disabled={busy||shown.length<2}><RouteIcon/> Optimize day</button><button className="outline" onClick={()=>window.confirm('Regenerate your trip? This replaces manual stop edits.')&&mutate('generate',{place_ids:days.flatMap(d=>d.stops.map(s=>s.place.id))})} disabled={busy}><RotateCcw/> Regenerate</button><button className="signupLink" onClick={saveOrder} disabled={!draft||busy}><Save/> Save order</button></div></div>{error&&<div className="formError">{error}</div>}<div className="dayTabs">{days.map((d,i)=><button className={active===i?'active':''} key={d.id} onClick={()=>{setActive(i);setFocus(null)}}>Day {d.position}<small>{d.date}</small></button>)}</div><div className="planner"><section className="timeline"><h2>Day {day.position} route</h2><p>Drag stops to reorder, or move them to another day. Save to keep changes after refresh.</p>{shown.map((s,i)=><article className="stop editableStop" key={s.id} draggable onDragStart={e=>e.dataTransfer.setData('text/plain',`${active}:${i}`)} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const [src,index]=e.dataTransfer.getData('text/plain').split(':').map(Number);move(index,i,src)}} onClick={()=>setFocus(s)}><GripVertical/><img src={s.place.image_url||fallback}/><div><b>{i+1}. {s.place.name}</b><small>{s.place.category} · {s.duration_minutes} min {s.distance_from_previous_km?`· ${s.distance_from_previous_km} km`:''}</small><select aria-label={`Move ${s.place.name} to day`} value={active} onClick={e=>e.stopPropagation()} onChange={e=>move(i,(draft?draft[Number(e.target.value)]:days[Number(e.target.value)].stops).length,active,Number(e.target.value))}>{days.map((d,j)=><option key={d.id} value={j}>Day {j+1}</option>)}</select></div><button aria-label={`Remove ${s.place.name}`} onClick={e=>{e.stopPropagation();if(window.confirm(`Remove ${s.place.name} from this trip?`))mutate('remove_place',{stop_id:s.id})}}><Trash2/></button></article>)}{!shown.length&&<p className="empty">No places on this day yet.</p>}<button className="addStop" onClick={()=>setAddOpen(!addOpen)}><Plus/> Add place</button>{addOpen&&<div className="placePicker">{places.filter(p=>!days.some(d=>d.stops.some(s=>s.place.id===p.id))).map(p=><button key={p.id} onClick={()=>{mutate('add_place',{day_id:day.id,place_id:p.id});setAddOpen(false)}}>{p.name}</button>)}{!places.length&&<p>No places available. Search this destination in Discover.</p>}</div>}<label className="notesField">Trip notes<textarea defaultValue={trip.notes} key={trip.id+':'+trip.notes} onBlur={e=>{if(e.target.value!==trip.notes)api(`/trips/${id}/`,{method:'PATCH',body:{notes:e.target.value}}).then(update).catch(err=>setError(err.message))}} placeholder="Ideas, reservations, reminders…"/></label><Link to={`/assistant?trip=${id}`}>Ask the travel assistant about this trip</Link></section><div className="mapPanel"><RouteMap stops={shown} focus={focus} onFocus={setFocus}/><div className="mapCaption"><MapPin/> {focus?.place.name||'Select a stop or marker to focus the map'}</div></div></div></div>
}
