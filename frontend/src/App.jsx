import React,{useState} from 'react';
import {useDispatch,useSelector} from 'react-redux';
import {Routes,Route,Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {MapPin,Search,Plus,Check,Compass,Route as RouteIcon,Users,Sparkles,Bell,Star,Menu,X,ArrowRight,LogOut,AlertCircle,LoaderCircle} from 'lucide-react';
import {api,login,signup,tokens} from './api';
import {setUser,logout,togglePlace,setDestination,setDates,clearTrip} from './main';
import TripPlanner from './TripPlanner';
import Trips from './Trips';
import GuidesMarketplace from './GuidesMarketplace';
import {GuideDashboard,GuideProfile,GuideCoverage,GuideServices,GuideAvailability,AvailabilityPreview,GuideRequests,GuideBookings} from './GuidePortal';
import MessagesPage from './MessagesPage';
import {Notifications,TouristProfile,TouristBookings,GuideReviews,Assistant} from './Community';

const fallback='https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80';
function Logo(){return <Link className="logo" to="/"><span className="logoMark">W</span><span>Wanderlust</span></Link>}
function Status({loading,error,empty}){if(loading)return <div className="state"><LoaderCircle className="spin"/> Loading…</div>;if(error)return <div className="state error"><AlertCircle/> {error}</div>;if(empty)return <div className="state">{empty}</div>;return null}
function Protected({role,children}){const user=useSelector(s=>s.auth.user),location=useLocation();if(!user)return <Navigate to={`/login/${role.toLowerCase()}`} state={{from:location}} replace/>;if(user.role!==role)return <Navigate to={user.role==='GUIDE'?'/guide/dashboard':'/discover'} replace/>;return children}

function SiteHeader(){
 const user=useSelector(s=>s.auth.user),dispatch=useDispatch(),navigate=useNavigate(),[open,setOpen]=useState(false);
 const tourist=[['Discover','/discover'],['Your Trips','/trips'],['Local Guides','/guides'],['Bookings','/bookings'],['AI Assistant','/assistant'],['Messages','/messages'],['Notifications','/notifications'],['Profile','/profile']];
 const guide=[['Dashboard','/guide/dashboard'],['Profile','/guide/profile'],['Coverage','/guide/coverage'],['Services','/guide/services'],['Availability','/guide/availability'],['Requests','/guide/requests'],['Bookings','/guide/bookings'],['Reviews','/guide/reviews'],['Messages','/messages'],['Notifications','/notifications']];
 function signout(){tokens.clear();dispatch(logout());navigate('/')}
 return <header><Logo/>{user&&<nav className={open?'open':''}>{(user.role==='GUIDE'?guide:tourist).map(([label,url])=><Link key={url} to={url} onClick={()=>setOpen(false)}>{label}</Link>)}</nav>}<div className="headActions">{user?<><Link className="icon" to="/notifications" aria-label="Notifications"><Bell/></Link><span className="avatar">{user.name?.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><button className="icon" onClick={signout} aria-label="Log out"><LogOut/></button></>:<><Link className="textLink" to="/login/tourist">Log in</Link><Link className="signupLink" to="/signup/tourist">Sign up</Link></>}<button className="menu" onClick={()=>setOpen(!open)} aria-label="Menu">{open?<X/>:<Menu/>}</button></div></header>
}

function Landing(){return <><section className="hero landing"><div className="heroShade"/><div className="heroContent"><div className="eyebrow"><Compass/> Travel planning with local perspective</div><h1>Explore more.<br/>Travel smarter.</h1><p>Build a day-by-day journey around places you care about, then meet trusted locals who make the destination feel personal.</p><div className="roleActions"><Link to="/signup/tourist">Continue as Tourist <ArrowRight/></Link><Link to="/signup/guide">Continue as Local Guide <ArrowRight/></Link></div></div></section><section className="roleExplain"><div><MapPin/><h3>Discover places</h3><p>Search destinations using live map data.</p></div><div><RouteIcon/><h3>Build a real itinerary</h3><p>Save geographically grouped days to your account.</p></div><div><Users/><h3>Connect with locals</h3><p>Find guides by coverage, services and availability.</p></div></section></>}

function AuthPage({role,mode}){
 const isSignup=mode==='signup',isGuide=role==='GUIDE',dispatch=useDispatch(),navigate=useNavigate();
 const [form,setForm]=useState({name:'',email:'',password:'',confirm:'',terms:false}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function submit(event){event.preventDefault();setError('');if(isSignup&&(form.password!==form.confirm||!form.terms)){setError(form.password!==form.confirm?'Passwords do not match.':'You must accept the terms.');return}setBusy(true);try{const user=isSignup?await signup({name:form.name,email:form.email,password:form.password,confirm_password:form.confirm,terms:form.terms,role}):await login(form.email,form.password);if(user.role!==role){tokens.clear();throw new Error(`This account is registered as a ${user.role.toLowerCase()}, not a ${role.toLowerCase()}.`)}dispatch(setUser(user));navigate(isGuide?(isSignup?'/guide/onboarding':'/guide/dashboard'):'/discover',{replace:true})}catch(exc){setError(exc.message)}finally{setBusy(false)}}
 return <div className={`authPage ${isGuide?'guideAuth':''}`}><section className="authVisual"><Logo/><div><span>{isGuide?'LOCAL GUIDE PORTAL':'TOURIST ACCOUNT'}</span><h1>{isSignup?'Begin your Wanderlust journey.':'Welcome back.'}</h1><p>{isGuide?'Share your city, manage services and meet travellers.':'Your saved trips and discoveries are waiting.'}</p></div></section><form className="authCard" onSubmit={submit}><Logo/><h2>{isSignup?'Create':'Log in to'} your {isGuide?'Guide':'Tourist'} account</h2>{error&&<div className="formError"><AlertCircle/>{error}</div>}{isSignup&&<label>Full name<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>}<label>Email address<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Password<input type="password" required minLength="8" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label>{isSignup&&<><label>Confirm password<input type="password" required value={form.confirm} onChange={e=>setForm({...form,confirm:e.target.value})}/></label><label className="check"><input type="checkbox" checked={form.terms} onChange={e=>setForm({...form,terms:e.target.checked})}/> I agree to the Terms and Privacy Policy</label></>}<button className="primary" disabled={busy}>{busy?<LoaderCircle className="spin"/>:isSignup?'Create account':'Log in'}</button><p>{isSignup?'Already have an account?':'New to Wanderlust?'} <Link to={`/${isSignup?'login':'signup'}/${role.toLowerCase()}`}>{isSignup?'Log in':'Sign up'}</Link></p><div className="switchRole">Looking for the other portal? <Link to={`/${mode}/${isGuide?'tourist':'guide'}`}>{isGuide?'Tourist':'Guide'} {mode}</Link></div></form></div>
}

function PlaceCard({place}){
 const dispatch=useDispatch(),selected=useSelector(s=>s.trip.selected.some(x=>x.id===place.id)),destination=useSelector(s=>s.trip.destination);
 const rad=n=>n*Math.PI/180,dLat=rad(place.latitude-(destination?.latitude||place.latitude)),dLon=rad(place.longitude-(destination?.longitude||place.longitude)),a=Math.sin(dLat/2)**2+Math.cos(rad(place.latitude))*Math.cos(rad(destination?.latitude||place.latitude))*Math.sin(dLon/2)**2,distance=Math.round(12742*Math.asin(Math.sqrt(a))*10)/10;
 return <article className="placeCard"><div className="image"><img src={place.image_url||fallback} onError={e=>{if(e.currentTarget.src!==fallback)e.currentTarget.src=fallback}} alt={place.name}/><span>{place.category||'Attraction'}</span></div><div className="placeBody"><div className="placeTitle"><h3>{place.name}</h3>{place.rating&&<span className="rating"><Star/> {place.rating}</span>}</div><p>{place.description||'A noteworthy place to explore during your trip.'}</p><div className="meta"><MapPin/>{distance} km from {destination?.name||'city center'}</div><button className={selected?'added':''} onClick={()=>dispatch(togglePlace(place))}>{selected?<><Check/> Added</>:<><Plus/> Add to trip</>}</button></div></article>
}

function TripBuilder({onCreated}){
 const {selected,destination,start,end}=useSelector(s=>s.trip),dispatch=useDispatch(),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function generate(){setError('');if(!destination||!start||!end||!selected.length){setError('Choose dates and at least one place.');return}if(end<start){setError('End date must be after the start date.');return}setBusy(true);try{const trip=await api('/trips/plan/',{body:{destination:destination.id,title:`${destination.name} trip`,start_date:start,end_date:end,place_ids:selected.map(p=>p.id)}});onCreated(trip)}catch(exc){setError(exc.message)}finally{setBusy(false)}}
 return <aside className="selection"><div className="selectionHead"><div><span className="step">TRIP BUILDER</span><h2>Plan your escape</h2></div><span className="count">{selected.length}</span></div><label>Destination<div className="input"><MapPin/>{destination?.name||'Search first'}</div></label><div className="dateRow"><label>Start<input type="date" value={start} onChange={e=>dispatch(setDates({start:e.target.value,end}))}/></label><label>End<input type="date" value={end} onChange={e=>dispatch(setDates({start,end:e.target.value}))}/></label></div><div className="selectedList">{selected.length?selected.map((place,index)=><div className="selectedItem" key={place.id}><span>{index+1}</span><img src={place.image_url||fallback} alt=""/><div><b>{place.name}</b><small>{place.category}</small></div><button onClick={()=>dispatch(togglePlace(place))} aria-label={`Remove ${place.name}`}><X/></button></div>):<div className="empty"><RouteIcon/><p>Add places to create your route.</p></div>}</div>{error&&<div className="miniError">{error}</div>}<button className="primary" disabled={busy||!selected.length} onClick={generate}>{busy?<LoaderCircle className="spin"/>:<Sparkles/>} Generate & save trip</button></aside>
}

function Discover(){
 const dispatch=useDispatch(),navigate=useNavigate(),[query,setQuery]=useState(''),[places,setPlaces]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState('');
 async function search(event){event.preventDefault();if(!query.trim())return;setLoading(true);setError('');try{const destination=await api(`/destinations/search/?q=${encodeURIComponent(query)}`);dispatch(setDestination(destination));setPlaces(destination.places||[]);if(!destination.places?.length)setError('Destination found, but no attractions were returned. Try a nearby city or retry later.')}catch(exc){setError(exc.message)}finally{setLoading(false)}}
 return <><section className="hero"><div className="heroShade"/><div className="heroContent"><div className="eyebrow"><Compass/> Live destination discovery</div><h1>Where will your<br/>next story begin?</h1><p>Search globally, choose real places, and save a route shaped around your dates.</p><form onSubmit={search}><MapPin/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Try Paris, Jaipur, Kyoto…"/><button aria-label="Search destinations"><Search/></button></form></div></section><main><div className="content"><div className="sectionTop"><div><span className="kicker">LIVE RESULTS</span><h2>Places worth your time</h2></div></div><Status loading={loading} error={!places.length&&error}/>{places.length>0&&<div className="places">{places.map(place=><PlaceCard key={place.id} place={place}/>)}</div>}</div><TripBuilder onCreated={trip=>{dispatch(clearTrip());navigate(`/trips/${trip.id}`)}}/></main></>
}

function App(){const sharedRole=tokens.get()?.user?.role||'TOURIST';return <><SiteHeader/><Routes>
 <Route path="/" element={<Landing/>}/>
 {['tourist','guide'].flatMap(role=>['login','signup'].map(mode=><Route key={role+mode} path={`/${mode}/${role}`} element={<AuthPage role={role.toUpperCase()} mode={mode}/>}/>))}
 <Route path="/discover" element={<Protected role="TOURIST"><Discover/></Protected>}/>
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
 </Routes><footer><Logo/><span>Thoughtful trips. Real local knowledge.</span><span>Map and place data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a></span><span>© 2026 Wanderlust</span></footer></>}
export default App;
