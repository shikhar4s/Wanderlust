import React from 'react';
import {createRoot} from 'react-dom/client';
import {Provider} from 'react-redux';
import {configureStore,createSlice} from '@reduxjs/toolkit';
import App from './App';
import './styles.css';

const tripSlice=createSlice({name:'trip',initialState:{selected:[],days:4},reducers:{togglePlace:(s,a)=>{const i=s.selected.findIndex(x=>x.id===a.payload.id);i>=0?s.selected.splice(i,1):s.selected.push(a.payload)},setDays:(s,a)=>{s.days=a.payload},clear:(s)=>{s.selected=[]}}});
export const {togglePlace,setDays,clear}=tripSlice.actions;
export const store=configureStore({reducer:{trip:tripSlice.reducer}});
createRoot(document.getElementById('root')).render(<React.StrictMode><Provider store={store}><App/></Provider></React.StrictMode>);

