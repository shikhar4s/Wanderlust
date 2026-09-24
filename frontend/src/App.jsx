import React,{useEffect,useRef,useState} from 'react';
import {useDispatch,useSelector} from 'react-redux';
import {Routes,Route,Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {MapPin,Search,Plus,Check,Compass,Route as RouteIcon,Users,Sparkles,Bell,Star,Menu,X,ArrowRight,LogOut,AlertCircle,LoaderCircle,Home,CalendarDays,MessageCircle,UserRound,BriefcaseBusiness,ExternalLink} from 'lucide-react';
import {api,login,signup,tokens} from './api';
import {setUser,logout,togglePlace,setDestination,setDates,clearTrip} from './main';
import TripPlanner from './TripPlanner';
import Trips from './Trips';
import GuidesMarketplace from './GuidesMarketplace';
import {GuideDashboard,GuideProfile,GuideCoverage,GuideServices,GuideAvailability,AvailabilityPreview,GuideRequests,GuideBookings} from './GuidePortal';
import MessagesPage from './MessagesPage';
import {Notifications,TouristProfile,TouristBookings,GuideReviews,Assistant,AssistantWidget} from './Community';
import {configure as configureLocations,getCountries,getStatesOfCountry,getCitiesOfState} from '@countrystatecity/countries-browser';

configureLocations({baseURL:'/geo',timeout:8000});

const fallback='https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80';
const imageUrl=url=>url?.replace(/^https:\/\/thumb\.wikimedia\.org\//,'https://upload.wikimedia.org/')||'';
function Logo(){return <Link className="logo" to="/"><span className="logoMark">W</span><span>Wanderlust</span></Link>}
function Status({loading,error,empty}){if(loading)return <div className="state"><LoaderCircle className="spin"/> Loading…</div>;if(error)return <div className="state error"><AlertCircle/> {error}</div>;if(empty)return <div className="state">{empty}</div>;return null}
function Protected({role,children}){const user=useSelector(s=>s.auth.user),location=useLocation();if(!user)return <Navigate to={`/login/${role.toLowerCase()}`} state={{from:location}} replace/>;if(user.role!==role)return <Navigate to={user.role==='GUIDE'?'/guide/dashboard':'/discover'} replace/>;return children}

function SiteHeader(){
 const user=useSelector(s=>s.auth.user),dispatch=useDispatch(),navigate=useNavigate(),[open,setOpen]=useState(false);
 const tourist=[['Discover','/discover'],['Search locations','/search'],['Your Trips','/trips'],['Local Guides','/guides'],['Bookings','/bookings'],['AI Assistant','/assistant'],['Messages','/messages'],['Notifications','/notifications'],['Profile','/profile']];
 const guide=[['Dashboard','/guide/dashboard'],['Profile','/guide/profile'],['Coverage','/guide/coverage'],['Services','/guide/services'],['Availability','/guide/availability'],['Requests','/guide/requests'],['Bookings','/guide/bookings'],['Reviews','/guide/reviews'],['Messages','/messages'],['Notifications','/notifications']];
 function signout(){tokens.clear();dispatch(logout());navigate('/')}
 return <header><Logo/>{user&&<nav className={open?'open':''}>{(user.role==='GUIDE'?guide:tourist).map(([label,url])=><Link key={url} to={url} onClick={()=>setOpen(false)}>{label}</Link>)}</nav>}<div className="headActions">{user?<><Link className="icon" to="/notifications" aria-label="Notifications"><Bell/></Link><Link to={user.role==='GUIDE'?'/guide/profile':'/profile'} className="userBadge"><span className="avatar">{user.photo_url?<img src={user.photo_url} alt=""/>:user.name?.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><span><b>Hi, {user.first_name||user.name?.split(' ')[0]}</b><small>{user.role==='GUIDE'?'Local Guide':'Let’s travel'}</small></span></Link><button className="icon" onClick={signout} aria-label="Log out"><LogOut/></button></>:<><Link className="textLink" to="/login/tourist">Log in</Link><Link className="signupLink" to="/signup/tourist">Sign up</Link></>}<button className="menu" onClick={()=>setOpen(!open)} aria-label="Menu">{open?<X/>:<Menu/>}</button></div></header>
}

function WorkspaceSidebar({user}){const location=useLocation();const tourist=[['Home','/discover',Home],['Search locations','/search',Search],['Your Trips','/trips',CalendarDays],['Local Guides','/guides',Users],['Bookings','/bookings',BriefcaseBusiness],['Messages','/messages',MessageCircle],['Notifications','/notifications',Bell],['Profile','/profile',UserRound]];const guide=[['Dashboard','/guide/dashboard',Home],['My Profile','/guide/profile',UserRound],['Coverage','/guide/coverage',MapPin],['Services','/guide/services',BriefcaseBusiness],['Availability','/guide/availability',CalendarDays],['Requests','/guide/requests',Users],['Bookings','/guide/bookings',Check],['Messages','/messages',MessageCircle],['Reviews','/guide/reviews',Star]];return <aside className={`workspaceSidebar ${user.role==='GUIDE'?'guideSidebar':''}`}><Logo/><small>{user.role==='GUIDE'?'GUIDE PORTAL':'TOURIST INTERFACE'}</small><nav>{(user.role==='GUIDE'?guide:tourist).map(([label,path,Icon])=><Link key={path} className={location.pathname===path?'active':''} to={path}><Icon size={18}/>{label}</Link>)}</nav><div className="sideTagline">{user.role==='GUIDE'?'Guide the world. Share your story.':'Collect places, not things.'}</div></aside>}

function Landing(){return <><section className="hero landing"><div className="heroShade"/><div className="heroContent"><div className="eyebrow"><Compass/> Travel planning with local perspective</div><h1>Explore more.<br/>Travel smarter.</h1><p>Build a day-by-day journey around places you care about, then meet trusted locals who make the destination feel personal.</p><div className="roleActions"><Link to="/signup/tourist">Continue as Tourist <ArrowRight/></Link><Link to="/signup/guide">Continue as Local Guide <ArrowRight/></Link></div></div></section><section className="roleExplain"><div><MapPin/><h3>Discover places</h3><p>Search destinations using live map data.</p></div><div><RouteIcon/><h3>Build a real itinerary</h3><p>Save geographically grouped days to your account.</p></div><div><Users/><h3>Connect with locals</h3><p>Find guides by coverage, services and availability.</p></div></section></>}

function AuthPage({role,mode}){
 const isSignup=mode==='signup',isGuide=role==='GUIDE',dispatch=useDispatch(),navigate=useNavigate();
 const [form,setForm]=useState({name:'',email:'',password:'',confirm:'',terms:false}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function submit(event){event.preventDefault();setError('');if(isSignup&&(form.password!==form.confirm||!form.terms)){setError(form.password!==form.confirm?'Passwords do not match.':'You must accept the terms.');return}setBusy(true);try{const user=isSignup?await signup({name:form.name,email:form.email,password:form.password,confirm_password:form.confirm,terms:form.terms,role}):await login(form.email,form.password);if(user.role!==role){tokens.clear();throw new Error(`This account is registered as a ${user.role.toLowerCase()}, not a ${role.toLowerCase()}.`)}dispatch(setUser(user));navigate(isGuide?(isSignup?'/guide/onboarding':'/guide/dashboard'):'/discover',{replace:true})}catch(exc){setError(exc.message)}finally{setBusy(false)}}
 return <div className={`authPage ${isGuide?'guideAuth':''}`}><section className="authVisual"><Logo/><div><span>{isGuide?'LOCAL GUIDE PORTAL':'TOURIST ACCOUNT'}</span><h1>{isSignup?'Begin your Wanderlust journey.':'Welcome back.'}</h1><p>{isGuide?'Share your city, manage services and meet travellers.':'Your saved trips and discoveries are waiting.'}</p></div></section><form className="authCard" onSubmit={submit}><Logo/><h2>{isSignup?'Create':'Log in to'} your {isGuide?'Guide':'Tourist'} account</h2>{error&&<div className="formError"><AlertCircle/>{error}</div>}{isSignup&&<label>Full name<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>}<label>Email address<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Password<input type="password" required minLength="8" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label>{isSignup&&<><label>Confirm password<input type="password" required value={form.confirm} onChange={e=>setForm({...form,confirm:e.target.value})}/></label><label className="check"><input type="checkbox" checked={form.terms} onChange={e=>setForm({...form,terms:e.target.checked})}/> I agree to the Terms and Privacy Policy</label></>}<button className="primary" disabled={busy}>{busy?<LoaderCircle className="spin"/>:isSignup?'Create account':'Log in'}</button><p>{isSignup?'Already have an account?':'New to Wanderlust?'} <Link to={`/${isSignup?'login':'signup'}/${role.toLowerCase()}`}>{isSignup?'Log in':'Sign up'}</Link></p><div className="switchRole">Looking for the other portal? <Link to={`/${mode}/${isGuide?'tourist':'guide'}`}>{isGuide?'Tourist':'Guide'} {mode}</Link></div></form></div>
}

function PlaceCard({place,cityImage}){
 const dispatch=useDispatch(),selected=useSelector(s=>s.trip.selected.some(x=>x.id===place.id)),destination=useSelector(s=>s.trip.destination);
 const [imageStage,setImageStage]=useState(0);
 useEffect(()=>setImageStage(0),[place.image_url,cityImage]);
 const exactImage=imageUrl(place.image_url),destinationImage=imageUrl(cityImage),images=[exactImage,destinationImage,fallback].filter((url,index,array)=>url&&array.indexOf(url)===index),shownImage=images[imageStage];
 const rad=n=>n*Math.PI/180,dLat=rad(place.latitude-(destination?.latitude||place.latitude)),dLon=rad(place.longitude-(destination?.longitude||place.longitude)),a=Math.sin(dLat/2)**2+Math.cos(rad(place.latitude))*Math.cos(rad(destination?.latitude||place.latitude))*Math.sin(dLon/2)**2,distance=Math.round(12742*Math.asin(Math.sqrt(a))*10)/10;
 const googleUrl=`https://www.google.com/search?q=${encodeURIComponent([place.name,destination?.name,destination?.country].filter(Boolean).join(', '))}`;
 return <article className="placeCard"><div className="image">{shownImage?<img src={shownImage} onError={()=>setImageStage(stage=>stage+1)} alt={imageStage===0&&exactImage&&place.image_kind!=='nearby'?place.name:`View near ${destination?.name||'the destination'}`} loading="lazy"/>:<div className="imagePlaceholder"><MapPin/><span>Image unavailable</span></div>}<span>{place.category||'Attraction'}</span>{shownImage&&(shownImage!==exactImage||place.image_kind==='nearby')&&<small className="imageHint">{shownImage===exactImage?'Nearby photo':shownImage===destinationImage?'Destination view':'Illustrative photo'}</small>}</div><div className="placeBody"><div className="placeTitle"><h3>{place.name}</h3>{place.rating&&<span className="rating"><Star/> {place.rating}</span>}</div><p>{place.description||'A noteworthy place to explore during your trip.'}</p><div className="meta"><MapPin/>{distance} km from {destination?.name||'city center'}</div><div className="placeActions"><button className={selected?'added':''} onClick={()=>dispatch(togglePlace(place))}>{selected?<><Check/> Added</>:<><Plus/> Add to trip</>}</button><a href={googleUrl} target="_blank" rel="noopener noreferrer" aria-label={`Google ${place.name} in ${destination?.name||'this city'}`}><ExternalLink size={15}/> Google it</a></div></div></article>
}

function TripBuilder({onCreated}){
 const {selected,destination,start,end}=useSelector(s=>s.trip),dispatch=useDispatch(),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function generate(){setError('');if(!destination||!start||!end||!selected.length){setError('Choose dates and at least one place.');return}if(end<start){setError('End date must be after the start date.');return}setBusy(true);try{const trip=await api('/trips/plan/',{body:{destination:destination.id,title:`${destination.name} trip`,start_date:start,end_date:end,place_ids:selected.map(p=>p.id)}});onCreated(trip)}catch(exc){setError(exc.message)}finally{setBusy(false)}}
 return <aside className="selection"><div className="selectionHead"><div><span className="step">TRIP BUILDER</span><h2>Plan your escape</h2></div><span className="count">{selected.length}</span></div><label>Destination<div className="input"><MapPin/>{destination?.name||'Search first'}</div></label><div className="dateRow"><label>Start<input type="date" value={start} onChange={e=>dispatch(setDates({start:e.target.value,end}))}/></label><label>End<input type="date" value={end} onChange={e=>dispatch(setDates({start,end:e.target.value}))}/></label></div><div className="selectedList">{selected.length?selected.map((place,index)=><div className="selectedItem" key={place.id}><span>{index+1}</span><img src={place.image_url||fallback} alt=""/><div><b>{place.name}</b><small>{place.category}</small></div><button onClick={()=>dispatch(togglePlace(place))} aria-label={`Remove ${place.name}`}><X/></button></div>):<div className="empty"><RouteIcon/><p>Add places to create your route.</p></div>}</div>{error&&<div className="miniError">{error}</div>}<button className="primary" disabled={busy||!selected.length} onClick={generate}>{busy?<LoaderCircle className="spin"/>:<Sparkles/>} Generate & save trip</button></aside>
}

function DashboardExtras({destination}){
 const [guides,setGuides]=useState([]),[trips,setTrips]=useState([]);
 useEffect(()=>{api('/trips/').then(data=>setTrips(data.results||data||[])).catch(()=>{})},[]);
 useEffect(()=>{if(destination)api(`/guides/?destination=${destination.id}`).then(data=>setGuides(data.results||data||[])).catch(()=>setGuides([]))},[destination?.id]);
 const upcoming=trips.filter(t=>t.end_date>=new Date().toISOString().slice(0,10)).slice(0,3);
 return <div className="dashboardExtras"><section className="formPanel"><div className="panelHeading"><h2>Your upcoming trips</h2><Link to="/trips">View all →</Link></div>{upcoming.length?upcoming.map(t=><Link className="dashboardTrip" to={`/trips/${t.id}`} key={t.id}><img src={t.destination_detail?.image_url||fallback} alt=""/><span><b>{t.title}</b><small>{t.start_date} – {t.end_date}</small></span><ArrowRight size={17}/></Link>):<p className="emptySmall">Start planning by adding places above.</p>}</section><section className="formPanel"><div className="panelHeading"><h2>Local guides {destination?`in ${destination.name}`:''}</h2><Link to="/guides">View all →</Link></div>{guides.filter(g=>g.services.some(s=>s.active)).slice(0,3).map(g=><Link className="dashboardGuide" to="/guides" key={g.id}>{g.photo_url?<img src={g.photo_url} alt=""/>:<span className="avatar">{g.name.slice(0,1)}</span>}<span><b>{g.name}</b><small>{g.years_experience} years · from ₹{Math.min(...g.services.filter(s=>s.active).map(s=>Number(s.price)))}</small></span><ArrowRight size={16}/></Link>)}{!guides.some(g=>g.services.some(s=>s.active))&&<p className="emptySmall">No active guides in this city yet. <Link to="/guides">Explore all guides</Link>.</p>}</section></div>
}

function LocationBrowser({onSelect}){
 const [countries,setCountries]=useState([]),[states,setStates]=useState([]),[cities,setCities]=useState([]);
 const [countryCode,setCountryCode]=useState(''),[stateCode,setStateCode]=useState(''),[cityQuery,setCityQuery]=useState(''),[chosen,setChosen]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 useEffect(()=>{getCountries().then(setCountries).catch(()=>setMessage('Location list could not load. Use the direct city search below.'))},[]);
 useEffect(()=>{setStates([]);setCities([]);setStateCode('');setChosen(null);setCityQuery('');if(countryCode)getStatesOfCountry(countryCode).then(setStates).catch(()=>setMessage('States could not load. Try direct city search.'))},[countryCode]);
 useEffect(()=>{setCities([]);setChosen(null);setCityQuery('');if(countryCode&&stateCode){setBusy(true);getCitiesOfState(countryCode,stateCode).then(setCities).catch(()=>setMessage('Cities could not load. Try direct city search.')).finally(()=>setBusy(false))}},[countryCode,stateCode]);
 const country=countries.find(item=>item.iso2===countryCode),state=states.find(item=>item.iso2===stateCode),needle=cityQuery.trim().toLocaleLowerCase();
 const options=needle.length?cities.filter(item=>item.name.toLocaleLowerCase().startsWith(needle)).slice(0,30):cities.slice(0,30);
 function openCity(){if(!chosen){setMessage('Choose a city from the matching list first.');return}setMessage('');onSelect(chosen.name,`csc:${countryCode}:${stateCode}:${chosen.id}`,{country:country.name,region:state.name,latitude:chosen.latitude,longitude:chosen.longitude})}
 return <section className="locationBrowser" aria-label="Browse locations"><div className="locationBrowserTop"><div><span className="kicker">SEARCH LOCATIONS</span><h2>Choose exactly where to explore</h2><p>Pick a country, state or province, then a city. Or use the direct search below for another place.</p></div><MapPin size={27}/></div><div className="locationFields"><label>Country<select value={countryCode} onChange={event=>{setCountryCode(event.target.value);setMessage('')}}><option value="">Select country</option>{countries.map(item=><option key={item.iso2} value={item.iso2}>{item.name}</option>)}</select></label><label>State / province<select value={stateCode} disabled={!countryCode||!states.length} onChange={event=>{setStateCode(event.target.value);setMessage('')}}><option value="">Select state or province</option>{states.map(item=><option key={item.iso2} value={item.iso2}>{item.name}</option>)}</select></label><label className="locationCityField">City<input value={cityQuery} disabled={!stateCode} onChange={event=>{setCityQuery(event.target.value);setChosen(null);setMessage('')}} placeholder={busy?'Loading cities…':'Type a city name'} autoComplete="off"/>{stateCode&&cityQuery&&<div className="locationCityOptions" role="listbox">{options.length?options.map(item=><button type="button" key={item.id} onClick={()=>{setChosen(item);setCityQuery(item.name)}}>{item.name}</button>):<p>No city in this list. Try direct search below.</p>}</div>}</label><button className="primary locationExplore" disabled={!chosen} onClick={openCity}><Search size={17}/> Explore city</button></div>{chosen&&<p className="locationChosen">Selected: {chosen.name}, {state?.name}, {country?.name}</p>}{message&&<p className="locationError">{message}</p>}<small className="locationCredit">Location list: <a href="https://github.com/dr5hn/countrystatecity-npm" target="_blank" rel="noopener noreferrer">CountryStateCity (ODbL)</a>. Map results: OpenStreetMap.</small></section>
}

function SearchPage(){
 const navigate=useNavigate(),[query,setQuery]=useState(''),[options,setOptions]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{if(query.trim().length<2){setOptions([]);setBusy(false);return}let cancelled=false;setBusy(true);setOptions([]);const timer=setTimeout(()=>{api(`/destinations/suggest/?q=${encodeURIComponent(query)}`).then(data=>{if(!cancelled)setOptions(data.results||[])}).catch(()=>{if(!cancelled)setError('City suggestions are unavailable right now.')}).finally(()=>{if(!cancelled)setBusy(false)})},250);return()=>{cancelled=true;clearTimeout(timer)}},[query]);
 function open(name,cityId='',details=null){navigate('/discover',{state:{locationSelection:{name,cityId,details}}})}
 return <main className="searchPage"><div className="searchPageHead"><span className="kicker">FIND YOUR NEXT DESTINATION</span><h1>Search the world, your way.</h1><p>Browse country → state → city, or search a city directly. Then explore real mapped attractions and trails.</p></div><LocationBrowser onSelect={open}/><section className="directSearchPanel"><div><span className="kicker">DIRECT SEARCH</span><h2>Already have a city in mind?</h2><p>Type a city and choose the right region from the results.</p></div><label>City name<input value={query} onChange={event=>{setQuery(event.target.value);setError('')}} placeholder="Try Jaipur, Manali, Paris…" autoComplete="off"/></label>{busy&&<p>Finding cities…</p>}{error&&<p className="locationError">{error}</p>}{query.trim().length>=2&&!busy&&<div className="directCityOptions">{options.length?options.map(item=><button key={item.provider_id} onClick={()=>open(item.name,item.provider_id)}><b>{item.name}</b><span>{[item.region,item.country].filter(Boolean).join(', ')}</span><ArrowRight size={17}/></button>):<p>No match yet. Try another spelling or browse above.</p>}</div>}</section></main>
}

function Discover(){
 const dispatch=useDispatch(),navigate=useNavigate(),route=useLocation(),destination=useSelector(s=>s.trip.destination),requestId=useRef(0),photoRequested=useRef(new Set());
 const [query,setQuery]=useState(''),[suggestions,setSuggestions]=useState([]),[showSuggestions,setShowSuggestions]=useState(false),[suggestLoading,setSuggestLoading]=useState(false),[searchHint,setSearchHint]=useState(''),[places,setPlaces]=useState([]),[heroImage,setHeroImage]=useState(''),[category,setCategory]=useState('All'),[placeQuery,setPlaceQuery]=useState(''),[visibleCount,setVisibleCount]=useState(24),[loading,setLoading]=useState(false),[error,setError]=useState('');
 async function chooseCity(value,cityId='',location=null){
  if(!value.trim())return;
  const current=++requestId.current;photoRequested.current=new Set();setLoading(true);setError('');setSearchHint('');setShowSuggestions(false);setSuggestions([]);setPlaces([]);setHeroImage('');dispatch(clearTrip());
  try{
   const params=new URLSearchParams({q:value});if(cityId)params.set('city_id',cityId);if(location)for(const [key,val] of Object.entries(location))params.set(key,String(val));
   const found=await api(`/destinations/search/?${params}`);if(current!==requestId.current)return;
   dispatch(setDestination(found));setQuery([found.name,found.region,found.country].filter(Boolean).join(', '));setHeroImage(imageUrl(found.image_url));
   const categoryRank={heritage:0,attraction:1,museum:2,viewpoint:3,gallery:4,trek:5,nature:6};
   setPlaces([...(found.places||[])].filter(p=>p.name?.trim()).sort((a,b)=>(categoryRank[a.category]??7)-(categoryRank[b.category]??7)||Number(Boolean(b.image_url))-Number(Boolean(a.image_url))||Math.hypot(a.latitude-found.latitude,a.longitude-found.longitude)-Math.hypot(b.latitude-found.latitude,b.longitude-found.longitude)||a.name.localeCompare(b.name)));
   setCategory('All');setPlaceQuery('');setVisibleCount(24);
   if(!found.places?.length)setError(found.warning||'This city was found, but mapped places are temporarily unavailable.');else if(found.warning)setError(found.warning)
  }catch(exc){if(current===requestId.current)setError(exc.message)}finally{if(current===requestId.current)setLoading(false)}
 }
 useEffect(()=>{dispatch(clearTrip())},[dispatch]);
 useEffect(()=>{const selected=route.state?.locationSelection;if(selected){chooseCity(selected.name,selected.cityId,selected.details);navigate('/discover',{replace:true,state:null})}},[route.state]);
 useEffect(()=>{
  if(query.trim().length<2||!showSuggestions){setSuggestions([]);setSuggestLoading(false);return}
  let cancelled=false;setSuggestLoading(true);
  const timer=setTimeout(()=>api(`/destinations/suggest/?q=${encodeURIComponent(query)}`).then(data=>{if(!cancelled)setSuggestions(data.results||[])}).catch(()=>{if(!cancelled)setSuggestions([])}).finally(()=>{if(!cancelled)setSuggestLoading(false)}),250);
  return()=>{cancelled=true;clearTimeout(timer)}
 },[query,showSuggestions]);
 async function search(event){
  event.preventDefault();if(!query.trim())return;
  try{
   const choices=suggestions.length?suggestions:(await api(`/destinations/suggest/?q=${encodeURIComponent(query)}`)).results||[];
   const [cityName,...qualifiers]=query.split(',').map(part=>part.trim().toLocaleLowerCase());
   const exact=choices.filter(city=>city.name.toLocaleLowerCase()===cityName&&(!qualifiers[0]||[city.region,city.country].some(part=>part?.toLocaleLowerCase()===qualifiers[0])));
   if(exact.length===1){chooseCity(exact[0].name,exact[0].provider_id);return}
   if(choices.length===1){chooseCity(choices[0].name,choices[0].provider_id);return}
   if(choices.length){setSuggestions(choices);setShowSuggestions(true);setSearchHint('Choose the correct city and region from the list.');return}
   chooseCity(query)
  }catch(exc){setError(exc.message)}
 }
 const categories=[['All','All'],['Attractions','attraction'],['Heritage','heritage'],['Museums','museum'],['Viewpoints','viewpoint'],['Treks & Trails','trek'],['Nature','nature'],['Galleries','gallery']];
 const filtered=places.filter(p=>(category==='All'||p.category===category)&&(!placeQuery.trim()||p.name.toLowerCase().includes(placeQuery.trim().toLowerCase())));
 useEffect(()=>{
  if(!destination?.id||!places.length)return;
  const wanted=filtered.slice(0,Math.min(visibleCount,72)).filter(place=>!place.image_url&&!photoRequested.current.has(place.id)).slice(0,24);
  if(!wanted.length)return;
  wanted.forEach(place=>photoRequested.current.add(place.id));
  const current=requestId.current;
  api(`/destinations/${destination.id}/photos/`,{body:{place_ids:wanted.map(place=>place.id)}}).then(data=>{
   if(current!==requestId.current)return;
   if(data.destination_image_url)setHeroImage(data.destination_image_url);
   if(Object.keys(data.photos||{}).length)setPlaces(previous=>previous.map(place=>data.photos[place.id]?{...place,image_url:data.photos[place.id].url,image_kind:data.photos[place.id].kind}:place));
  }).catch(()=>{});
 },[destination?.id,places,category,placeQuery,visibleCount]);
 return <><section className="hero discoverHero" style={heroImage?{backgroundImage:`url("${heroImage}")`}:undefined}><div className="heroShade"/><div className="heroContent"><div className="eyebrow"><Compass/> Live destination discovery</div><h1>Explore<br/>{destination?`${destination.name}, ${destination.country}`:'the world'}</h1><p>Real places, beautiful routes, and local perspectives for your next journey.</p><div className="citySearch"><form onSubmit={search}><MapPin/><input role="combobox" aria-expanded={showSuggestions&&query.trim().length>=2} aria-controls="city-suggestions" value={query} onChange={e=>{setQuery(e.target.value);setShowSuggestions(true);setSuggestions([]);setSearchHint('')}} onFocus={()=>setShowSuggestions(true)} onKeyDown={e=>{if(e.key==='Escape')setShowSuggestions(false)}} placeholder="Search a city, e.g. Jaipur, Paris, Kyoto…" autoComplete="off"/><button aria-label="Search destinations"><Search/></button></form>{searchHint&&<div className="citySearchHint">{searchHint}</div>}{showSuggestions&&query.trim().length>=2&&<div id="city-suggestions" className="citySuggestions" role="listbox">{suggestLoading?<p>Finding cities…</p>:suggestions.length?suggestions.map(city=><button key={city.provider_id||`${city.name}:${city.region}:${city.country}`} type="button" role="option" aria-selected="false" onClick={()=>chooseCity(city.name,city.provider_id)}><MapPin size={16}/><span><b>{city.name}</b><small>{[city.region,city.country].filter(Boolean).join(', ')}</small></span></button>):<p>No matching cities yet. Press Search to try the full name.</p>}</div>}</div></div></section><main className="discoverContent"><div className="content"><div className="sectionTop"><div><span className="kicker">DISCOVER {destination?.name?.toUpperCase()||'THE WORLD'}</span><h2>{destination?`Places in ${destination.name}`:'Find places for your trip'}</h2></div>{destination&&<span>{places.length} mapped places</span>}</div>{places.length>0&&<><div className="categoryChips">{categories.map(([name,key])=><button key={key} className={category===key?'active':''} onClick={()=>{setCategory(key);setVisibleCount(24)}}>{name} <small>{key==='All'?places.length:places.filter(p=>p.category===key).length}</small></button>)}</div><label className="placeSearch"><Search size={17}/><input value={placeQuery} onChange={e=>{setPlaceQuery(e.target.value);setVisibleCount(24)}} placeholder={`Find a place in ${destination.name}…`}/></label></>}<Status loading={loading} error={!places.length&&error}/>{!destination&&!loading&&!error&&<div className="discoveryEmpty"><Search/><h3>Where would you like to go?</h3><p>Search a city above to see its places and photos. Results appear only for the city you choose.</p></div>}{destination&&!loading&&places.length>0&&filtered.length===0&&<div className="discoveryEmpty"><Search/><h3>No places match this filter</h3><p>Try another category or search term.</p></div>}{filtered.length>0&&<><p className="resultCount">Showing {Math.min(visibleCount,filtered.length)} of {filtered.length} matching places</p><div className="places">{filtered.slice(0,visibleCount).map(place=><PlaceCard key={place.id} place={place} cityImage={heroImage}/>)}</div>{filtered.length>visibleCount&&<div className="loadPlaces"><button className="viewAllPlaces" onClick={()=>setVisibleCount(n=>n+24)}>Show more places</button><button className="viewAllPlaces" onClick={()=>setVisibleCount(filtered.length)}>Show all {filtered.length}</button></div>}</>}</div><TripBuilder onCreated={trip=>{dispatch(clearTrip());navigate(`/trips/${trip.id}`)}}/></main><DashboardExtras destination={destination}/></>
}

function App(){const user=useSelector(s=>s.auth.user),sharedRole=user?.role||'TOURIST';return <div className={user?'appShell':''}>{user&&<WorkspaceSidebar user={user}/>}<div className="shellMain"><SiteHeader/><Routes>
 <Route path="/" element={<Landing/>}/>
 {['tourist','guide'].flatMap(role=>['login','signup'].map(mode=><Route key={role+mode} path={`/${mode}/${role}`} element={<AuthPage role={role.toUpperCase()} mode={mode}/>}/>))}
 <Route path="/discover" element={<Protected role="TOURIST"><Discover/></Protected>}/>
 <Route path="/search" element={<Protected role="TOURIST"><SearchPage/></Protected>}/>
 <Route path="/trips" element={<Protected role="TOURIST"><Trips/></Protected>}/>
 <Route path="/trips/:id" element={<Protected role="TOURIST"><TripPlanner/></Protected>}/>
 <Route path="/guides" element={<Protected role="TOURIST"><GuidesMarketplace/></Protected>}/>
 <Route path="/assistant" element={<Protected role="TOURIST"><Assistant/></Protected>}/>
 <Route path="/profile" element={<Protected role="TOURIST"><TouristProfile/></Protected>}/>
 <Route path="/bookings" element={<Protected role="TOURIST"><TouristBookings/></Protected>}/>
 <Route path="/guide/onboarding" element={<Protected role="GUIDE"><GuideProfile/></Protected>}/>
 <Route path="/guide/dashboard" element={<Protected role="GUIDE"><GuideDashboard/></Protected>}/>
 <Route path="/guide/profile" element={<Protected role="GUIDE"><GuideProfile/></Protected>}/>
 <Route path="/guide/coverage" element={<Protected role="GUIDE"><GuideCoverage/></Protected>}/>
 <Route path="/guide/services" element={<Protected role="GUIDE"><GuideServices/></Protected>}/>
 <Route path="/guide/availability" element={<Protected role="GUIDE"><GuideAvailability/><AvailabilityPreview/></Protected>}/>
 <Route path="/guide/requests" element={<Protected role="GUIDE"><GuideRequests/></Protected>}/>
 <Route path="/guide/bookings" element={<Protected role="GUIDE"><GuideBookings/></Protected>}/>
 <Route path="/guide/reviews" element={<Protected role="GUIDE"><GuideReviews/></Protected>}/>
 <Route path="/messages" element={<Protected role={sharedRole}><MessagesPage/></Protected>}/>
 <Route path="/notifications" element={<Protected role={sharedRole}><Notifications/></Protected>}/>
 <Route path="*" element={<Navigate to="/" replace/>}/>
 </Routes>{user&&<AssistantWidget/>}<footer><Logo/><span>Thoughtful trips. Real local knowledge.</span><span>Map and place data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · Cities via <a href="https://open-meteo.com/en/docs/geocoding-api" target="_blank" rel="noreferrer">Open-Meteo / GeoNames</a> · Images via <a href="https://commons.wikimedia.org/" target="_blank" rel="noreferrer">Wikimedia Commons</a></span><span>© 2026 Wanderlust</span></footer></div></div>}
export default App;
