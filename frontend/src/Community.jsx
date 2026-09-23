import React,{useEffect,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {api} from './api';

const list=data=>data?.results||data||[];
export function Notifications(){
 const [items,setItems]=useState([]),[error,setError]=useState('');
 const reload=()=>api('/notifications/').then(data=>setItems(list(data))).catch(exc=>setError(exc.message));
 useEffect(()=>{reload()},[]);
 async function read(id){try{await api(`/notifications/${id}/read/`,{body:{}});reload()}catch(exc){setError(exc.message)}}
 return <div className="page"><div className="pageTitle"><div><span className="kicker">ACTIVITY</span><h1>Notifications</h1></div></div>{error&&<div className="formError">{error}</div>}{!items.length&&<p>Nothing new yet.</p>}{items.map(item=><div className="panelRow" key={item.id}><b>{item.title}</b><span>{item.body} · {new Date(item.created_at).toLocaleString()}</span>{!item.read_at&&<button onClick={()=>read(item.id)}>Mark read</button>}</div>)}</div>
}

export function TouristProfile(){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{api('/auth/me/').then(setData).catch(exc=>setError(exc.message))},[]);
 return <div className="page"><div className="pageTitle"><div><span className="kicker">YOUR ACCOUNT</span><h1>Profile</h1></div></div>{error&&<div className="formError">{error}</div>}{data&&<div className="formPanel"><h2>{data.name}</h2><p>{data.email}</p><p>Role: {data.role}</p></div>}</div>
}

export function TouristBookings(){
 const [bookings,setBookings]=useState([]),[reviews,setReviews]=useState([]),[error,setError]=useState(''),[rating,setRating]=useState(5),[text,setText]=useState('');
 async function reload(){try{setBookings(list(await api('/bookings/')));setReviews(list(await api('/reviews/')))}catch(exc){setError(exc.message)}}
 useEffect(()=>{reload()},[]);
 async function cancel(id){if(!window.confirm('Cancel this booking?'))return;try{await api(`/bookings/${id}/change_status/`,{body:{status:'CANCELLED'}});reload()}catch(exc){setError(exc.message)}}
 async function review(event,id){event.preventDefault();try{await api('/reviews/',{body:{booking:id,rating:Number(rating),text}});setText('');reload()}catch(exc){setError(exc.message)}}
 return <div className="page"><div className="pageTitle"><div><span className="kicker">LOCAL TOURS</span><h1>Your guide bookings</h1></div></div>{error&&<div className="formError">{error}</div>}{!bookings.length&&<p>No guide bookings yet.</p>}{bookings.map(booking=>{const existing=reviews.find(item=>item.booking===booking.id);return <div className="formPanel" key={booking.id}><h2>Booking #{booking.id}</h2><p>{new Date(booking.start).toLocaleString()} → {new Date(booking.end).toLocaleString()} · ₹{booking.final_price} · {booking.status}</p>{booking.status==='CONFIRMED'&&<button className="outline" onClick={()=>cancel(booking.id)}>Cancel booking</button>}{booking.status==='COMPLETED'&&!existing&&<form onSubmit={event=>review(event,booking.id)}><label>Rating<select value={rating} onChange={event=>setRating(event.target.value)}>{[5,4,3,2,1].map(number=><option key={number}>{number}</option>)}</select></label><label>Your review<textarea value={text} onChange={event=>setText(event.target.value)}/></label><button className="primary">Submit review</button></form>}{existing&&<p>Your review: {existing.rating}/5 — {existing.text}</p>}</div>})}</div>
}

export function GuideReviews(){
 const [items,setItems]=useState([]),[error,setError]=useState('');
 useEffect(()=>{api('/reviews/').then(data=>setItems(list(data))).catch(exc=>setError(exc.message))},[]);
 return <div className="page"><div className="pageTitle"><div><span className="kicker">TRAVELLER FEEDBACK</span><h1>Your reviews</h1></div></div>{error&&<div className="formError">{error}</div>}{!items.length&&<p>No completed-tour reviews yet.</p>}{items.map(item=><div className="panelRow" key={item.id}><b>{item.rating}/5</b><span>{item.text} · {new Date(item.created_at).toLocaleDateString()}</span></div>)}</div>
}

export function Assistant(){
 const [query]=useSearchParams(),[trip,setTrip]=useState(null),[messages,setMessages]=useState([]),[question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{const id=query.get('trip');if(id)api(`/trips/${id}/`).then(setTrip).catch(exc=>setError(exc.message))},[query]);
 async function ask(event){event.preventDefault();setBusy(true);setError('');try{const result=await api('/assistant/ask/',{body:{question,trip_id:trip?.id}});setMessages(previous=>[...previous,{q:question,a:result.answer}]);setQuestion('')}catch(exc){setError(exc.message)}finally{setBusy(false)}}
 return <div className="page"><div className="pageTitle"><div><span className="kicker">TRAVEL GUIDANCE</span><h1>AI Travel Assistant</h1><p>{trip?`Discussing ${trip.title} · ${trip.days.length} days`:'Ask about a destination or open a trip for itinerary context.'}</p></div></div>{error&&<div className="formError">{error}</div>}<div className="formPanel assistantPanel"><div className="messageThread">{messages.map((message,index)=><React.Fragment key={index}><div className="bubble mine">{message.q}</div><div className="bubble">{message.a}</div></React.Fragment>)}{!messages.length&&<p>Ask about food, places, local customs, or your current itinerary.</p>}</div><form className="inlineForm" onSubmit={ask}><input value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about your trip…" required/><button disabled={busy}>Ask</button></form></div></div>
}
