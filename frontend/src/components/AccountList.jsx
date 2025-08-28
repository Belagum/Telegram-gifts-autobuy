// src/components/AccountList.jsx
import React,{useEffect,useState,useRef,useLayoutEffect}from"react";
import {toast}from"react-toastify";
import {refreshAccountStream, apiFetch}from"../api";

function ts(d){if(!d)return 0;const t=Date.parse(d);return Number.isFinite(t)?t:0;}
function fmt(d){if(!d)return"—";try{return new Date(d).toLocaleString();}catch{return d;}}
function sortByLastChecked(a){return[...(a||[])].sort((x,y)=>ts(y.last_checked_at)-ts(x.last_checked_at));}

const CARD_MIN_W=220, CARD_H=140, GAP=12;

async function fetchAccountsWait(signal){
  const r=await apiFetch("/api/accounts?wait=1",{signal,method:"GET",headers:{Accept:"application/json"},cache:"no-store"});
  const ct=r.headers.get("content-type")||"";const data=ct.includes("application/json")?await r.json().catch(()=>({})):{};
  return{status:r.status,data};
}

export default function AccountList({accounts:initial}){
  const [phase,setPhase]=useState("boot");
  const [items,setItems]=useState(Array.isArray(initial)?sortByLastChecked(initial):[]);
  const [loadingIds,setLoadingIds]=useState({});
  const [skCount,setSkCount]=useState(6);

  const skWrapRef=useRef(null);
  const nodeMapRef=useRef(new Map());
  const prevRectsRef=useRef(new Map());
  const prevOrderRef=useRef([]);
  const listToastRef=useRef(null);
  const pollTimerRef=useRef(null);
  const abortRef=useRef(null);
  const lastStateRef=useRef("boot");
  const hasReadyOnceRef=useRef(false);
  const moveRef=useRef({id:null,prevIndex:-1});

  useEffect(()=>{ if(Array.isArray(initial)){ setItems(sortByLastChecked(initial)); if(initial.length>0){ setPhase("ready"); hasReadyOnceRef.current=true; } } },[initial]);

  useEffect(()=>{
    function recalc(){
      const el=skWrapRef.current;if(!el){setSkCount(6);return;}
      const r=el.getBoundingClientRect();
      const cols=Math.max(1,Math.floor((r.width+GAP)/(CARD_MIN_W+GAP)));
      const visibleH=Math.max(0,window.innerHeight-r.top-16);
      const rows=Math.max(1,Math.ceil((visibleH+GAP)/(CARD_H+GAP)));
      setSkCount(cols*rows);
    }
    recalc();
    const ro=new ResizeObserver(recalc);
    if(skWrapRef.current)ro.observe(skWrapRef.current);
    window.addEventListener("resize",recalc);
    document.addEventListener("visibilitychange",()=>{ if(!document.hidden) loadOnce(true); });
    return()=>{ window.removeEventListener("resize",recalc); ro.disconnect(); };
  },[]);

  const clearPoll=()=>{ if(pollTimerRef.current){ clearTimeout(pollTimerRef.current); pollTimerRef.current=null; } };
  const schedulePoll=(ms)=>{ clearPoll(); pollTimerRef.current=setTimeout(()=>loadOnce(false),ms); };

  async function loadOnce(){
    try{
      if(abortRef.current)abortRef.current.abort();
      const ctrl=new AbortController(); abortRef.current=ctrl;
      const {status,data}=await fetchAccountsWait(ctrl.signal);
      if(status===200&&data?.state==="ready"&&Array.isArray(data.accounts)){
        const next=sortByLastChecked(data.accounts||[]);
        setItems(next); hasReadyOnceRef.current=true;
        setPhase(next.length?"ready":"empty"); lastStateRef.current="ready"; clearPoll();
      }else if(status===202||data?.state==="refreshing"){
        setPhase(items.length?"ready":"refreshing"); lastStateRef.current="refreshing"; schedulePoll(900);
      }else{
        setPhase(items.length?"ready":(hasReadyOnceRef.current?"empty":"boot")); clearPoll();
      }
    }catch(e){
      if(e?.name!=="AbortError"){ toast.dismiss(); toast.error("Ошибка загрузки аккаунтов"); }
      setPhase(items.length?"ready":(lastStateRef.current==="refreshing"?"refreshing":"boot")); clearPoll();
    }
  }

  useEffect(()=>{ loadOnce(); return()=>{ clearPoll(); if(abortRef.current)abortRef.current.abort(); }; },[]);

  useEffect(()=>{
    const showLoader=(phase==="boot"||phase==="refreshing")&&items.length===0;
    if(showLoader&&!listToastRef.current){ listToastRef.current=toast.loading("Обновляю аккаунты…",{autoClose:false}); }
    if((!showLoader)&&listToastRef.current){ toast.dismiss(listToastRef.current); listToastRef.current=null; }
  },[phase,items.length]);

  useLayoutEffect(()=>{
    const nodeMap=nodeMapRef.current, prevRects=prevRectsRef.current;
    const nextRects=new Map(); nodeMap.forEach((n,id)=>{ if(n) nextRects.set(id,n.getBoundingClientRect()); });

    const prevOrder=prevOrderRef.current, nextOrder=items.map(x=>x.id);
    const prevIndex=new Map(prevOrder.map((id,i)=>[id,i]));
    const nextIndex=new Map(nextOrder.map((id,i)=>[id,i]));
    const movingId=moveRef.current.id, movingPrev=moveRef.current.prevIndex;
    const movingNext=typeof movingId==="number"? nextIndex.get(movingId) : -1;
    const staged=movingId!=null && movingPrev>=0 && movingNext>=0 && movingPrev!==movingNext;

    nodeMap.forEach((node,id)=>{
      if(!node)return;
      const prev=prevRects.get(id), next=nextRects.get(id);
      const iPrev=prevIndex.get(id), iNext=nextIndex.get(id);
      if(!prev){
        node.style.opacity="0"; node.style.transform="translateY(10px)";
        const d=Math.min((iNext??0)*40,300);
        requestAnimationFrame(()=>{ node.style.transition=`opacity 260ms ease ${d}ms, transform 260ms ease ${d}ms`; node.style.opacity="1"; node.style.transform="translateY(0)"; });
        return;
      }
      if(next){
        const dx=prev.left-next.left, dy=prev.top-next.top;
        if(dx||dy){
          let delayMs=0;
          if(staged){
            if(id===movingId){
              if(movingPrev===0){ node.style.transition="transform 0s"; node.style.transform=""; return; }
              delayMs=0;
            }else if(iPrev>=movingNext && iPrev<movingPrev){
              delayMs=(iPrev-movingNext+1)*70;
            }
          }
          node.style.transition="transform 0s";
          node.style.transform=`translate(${dx}px, ${dy}px)`;
          requestAnimationFrame(()=>{ node.style.transition=`transform 260ms ease ${delayMs}ms`; node.style.transform="translate(0, 0)"; });
        }
      }
    });

    prevRectsRef.current=nextRects;
    prevOrderRef.current=items.map(x=>x.id);
    moveRef.current={id:null,prevIndex:-1};
  },[items]);

  const applyUpdate=(acc)=>{
    const id=acc?.id;
    if(id!=null){
      const prevIdx=prevOrderRef.current.indexOf(id);
      moveRef.current=(prevIdx>=0? {id,prevIndex:prevIdx}:{id:null,prevIndex:-1});
    }
    setItems(prev=>sortByLastChecked(prev.map(x=>x.id===acc.id?{...x,...acc}:x)));
  };
  const removeAccount=(id)=>{ setItems(prev=>sortByLastChecked(prev.filter(x=>x.id!==id))); };
  const markLoading=(id,on)=>{ setLoadingIds(prev=>{ const n={...prev}; if(on)n[id]=true; else delete n[id]; return n; }); };

  const doRefresh=async(id)=>{
    if(loadingIds[id])return;
    markLoading(id,true);
    const tid=toast.loading("Готовлюсь…");
    try{
      await refreshAccountStream(id,(ev)=>{
        if(ev.error==="session_invalid"||ev.error_code==="AUTH_KEY_UNREGISTERED"){
          markLoading(id,false); removeAccount(id);
          toast.update(tid,{render:ev.detail||"Сессия невалидна. Аккаунт удалён.",type:"error",isLoading:false,autoClose:3500});
          loadOnce(); return;
        }
        if(ev.error){
          markLoading(id,false);
          const txt=ev.error_code?`${ev.error_code}${ev.detail?`: ${ev.detail}`:""}`:(ev.detail||ev.error);
          toast.update(tid,{render:txt,type:"error",isLoading:false,autoClose:3500});
          loadOnce(); return;
        }
        if(ev.done){
          markLoading(id,false); applyUpdate(ev.account);
          toast.update(tid,{render:"Данные обновлены",type:"success",isLoading:false,autoClose:2000});
          return;
        }
        if(ev.stage){ toast.update(tid,{render:ev.message||ev.stage,isLoading:true}); }
      });
    }catch(e){
      markLoading(id,false);
      toast.update(tid,{render:e?.detail||e?.error||"Ошибка обновления",type:"error",isLoading:false,autoClose:3500});
      loadOnce();
    }
  };

  const saveNode=(id)=>(el)=>{ if(el)nodeMapRef.current.set(id,el); else nodeMapRef.current.delete(id); };

  const showSkeleton=(phase==="boot"||phase==="refreshing")&&items.length===0;
  const showEmpty=(phase==="empty"||((phase==="ready")&&items.length===0&&hasReadyOnceRef.current));

  if(showSkeleton){
    return(
      <div className="list list-accounts" ref={skWrapRef}>
        <div className="skeleton-grid">
          {Array.from({length:skCount}).map((_,i)=>(
            <div key={i} className="skeleton-account">
              <div className="sk-title sk-line"/><div className="sk-username sk-line"/>
              <div className="sk-stars sk-line"/><div className="sk-updated sk-line"/><div className="sk-button sk-line"/>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if(showEmpty){
    return(<div className="list list-accounts"><div className="empty muted">Аккаунтов нет</div></div>);
  }

  return(
    <div className="list list-accounts">
      {items.map(a=>{
        const isLoading=!!loadingIds[a.id];
        return(
          <div key={a.id} ref={saveNode(a.id)} className="card account-card">
            <div className="title">{a.first_name||"Без имени"}</div>
            <div>@{a.username||"—"}</div>
            <div>Звёзды: {a.stars}</div>
            <div>
              {a.is_premium
                ? `Премиум: ✅ (до ${a.premium_until})`
                : "Премиум: ❌"}
            </div>
            <div className="muted" style={{marginTop:8}}>Обновлено: {fmt(a.last_checked_at)}</div>
            <div style={{marginTop:10,display:"flex",gap:8,flexWrap:"wrap"}}>
              <button onClick={()=>doRefresh(a.id)} disabled={isLoading} className={`btn ${isLoading?"btn--progress":""}`}>
                {isLoading?"Обновляю…":"Обновить"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
