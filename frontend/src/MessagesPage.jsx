import React,{useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {api,tokens} from './api';

const list=data=>data?.results||data||[];
export default function MessagesPage(){
 const [query]=useSearchParams(),[conversations,setConversations]=useState([]),[active,setActive]=useState(null),[messages,setMessages]=useState([]),[offers,setOffers]=useState([]),[body,setBody]=useState(''),[price,setPrice]=useState(''),[error,setError]=useState('');
 const socket=useRef(null);
 async function reload(){try{const data=list(await api('/conversations/'));setConversations(data);setActive(current=>current||data.find(item=>String(item.request)===query.get('request'))?.id||data[0]?.id)}catch(exc){setError(exc.message)}}
 useEffect(()=>{reload()},[]);
 useEffect(()=>{
  if(!active)return;
  const update=()=>api(`/conversations/${active}/messages/`).then(setMessages).catch(exc=>setError(exc.message));
  update();const timer=setInterval(update,8000);
  const base=(import.meta.env.VITE_API_URL||'http://127.0.0.1:8000/api').replace(/\/api\/?$/,'').replace(/^http/,'ws');
  try{socket.current=new WebSocket(`${base}/ws/conversations/${active}/`,['jwt',tokens.get()?.access||'']);socket.current.onmessage=event=>{const item=JSON.parse(event.data);setMessages(previous=>previous.some(message=>message.id===item.id)?previous:[...previous,item])}}catch{socket.current=null}
  return()=>{clearInterval(timer);socket.current?.close();socket.current=null}
 },[active]);
 useEffect(()=>{api('/offers/').then(data=>setOffers(list(data))).catch(()=>{})},[active]);
 const current=conversations.find(item=>item.id===active),mine=tokens.get()?.user?.id,negotiable=current?.request_detail?.service_pricing_type==='NEGOTIABLE';
 async function send(event){event.preventDefault();try{if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({body}));else{await api(`/conversations/${active}/messages/`,{body:{body}});setMessages(await api(`/conversations/${active}/messages/`))}setBody('')}catch(exc){setError(exc.message)}}
 async function makeOffer(event){event.preventDefault();try{await api('/offers/',{body:{request:current.request,amount:price}});setPrice('');setOffers(list(await api('/offers/')));reload()}catch(exc){setError(exc.message)}}
 async function accept(id){if(!window.confirm('Accept this price offer?'))return;try{await api(`/offers/${id}/accept/`,{body:{}});setOffers(list(await api('/offers/')));reload()}catch(exc){setError(exc.message)}}
 return <div className="page"><div className="pageTitle"><div><span className="kicker">CONVERSATIONS</span><h1>Messages & offers</h1></div></div>{error&&<div className="formError">{error}</div>}<div className="messageLayout"><aside>{conversations.map(item=><button className={active===item.id?'active':''} key={item.id} onClick={()=>setActive(item.id)}>{item.request_detail?.service_title}<small>{item.request_detail?.status}</small></button>)}{!conversations.length&&<p>No conversations yet. Request a guide to begin.</p>}</aside><section>{current?<><div className="messageThread">{messages.map(message=><div key={message.id} className={message.sender===mine?'bubble mine':'bubble'}>{message.body}<small>{new Date(message.created_at).toLocaleString()}</small></div>)}</div><form className="inlineForm" onSubmit={send}><input aria-label="Message" value={body} onChange={event=>setBody(event.target.value)} placeholder="Type a message…" required/><button>Send</button></form>{negotiable&&<div className="offerPanel"><h3>Price negotiation</h3>{offers.filter(item=>item.request===current.request).map(item=><div className="panelRow" key={item.id}><b>₹{item.amount}</b><span>{item.accepted_at?'Accepted':`Offered ${new Date(item.created_at).toLocaleString()}`}</span>{!item.accepted_at&&item.sender!==mine&&current.request_detail?.status==='NEGOTIATING'&&<button onClick={()=>accept(item.id)}>Accept</button>}</div>)}{['PENDING','NEGOTIATING'].includes(current.request_detail?.status)&&<form className="inlineForm" onSubmit={makeOffer}><input type="number" min="1" step="0.01" value={price} onChange={event=>setPrice(event.target.value)} placeholder="Offer price (₹)" required/><button>Send offer</button></form>}</div>}</>:<p>Select a conversation.</p>}</section></div></div>
}
