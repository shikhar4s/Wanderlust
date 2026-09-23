import React from 'react';
import {createRoot} from 'react-dom/client';
import {Provider} from 'react-redux';
import {configureStore,createSlice} from '@reduxjs/toolkit';
import {BrowserRouter} from 'react-router-dom';
import App from './App';
import './styles.css';

const stored=(()=>{try{return JSON.parse(localStorage.getItem('wanderlust_tokens')||'null')?.user||null}catch{return null}})();
const authSlice=createSlice({name:'auth',initialState:{user:stored},reducers:{setUser:(s,a)=>{s.user=a.payload},logout:s=>{s.user=null}}});
const tripSlice=createSlice({name:'trip',initialState:{selected:[],destination:null,start:'',end:''},reducers:{togglePlace:(s,a)=>{const i=s.selected.findIndex(x=>x.id===a.payload.id);i>=0?s.selected.splice(i,1):s.selected.push(a.payload)},setDestination:(s,a)=>{s.destination=a.payload;s.selected=[]},setDates:(s,a)=>{s.start=a.payload.start;s.end=a.payload.end},clearTrip:s=>{s.selected=[];s.destination=null;s.start='';s.end=''}}});
export const {setUser,logout}=authSlice.actions;export const {togglePlace,setDestination,setDates,clearTrip}=tripSlice.actions;
export const store=configureStore({reducer:{auth:authSlice.reducer,trip:tripSlice.reducer}});
window.addEventListener('wanderlust:logout',()=>store.dispatch(logout()));
class ErrorBoundary extends React.Component{constructor(props){super(props);this.state={error:null}}static getDerivedStateFromError(error){return {error}}render(){return this.state.error?<div className="page"><div className="formError">This screen could not load: {this.state.error.message}</div><button className="outline" onClick={()=>window.location.reload()}>Retry</button></div>:this.props.children}}
createRoot(document.getElementById('root')).render(<React.StrictMode><Provider store={store}><BrowserRouter><ErrorBoundary><App/></ErrorBoundary></BrowserRouter></Provider></React.StrictMode>);
