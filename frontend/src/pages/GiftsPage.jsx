// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import React from "react";
import { listGifts, refreshGifts, getGiftsSettings, setGiftsSettings, listAccounts } from "../api";
import lottie from "lottie-web";
import openCentered from "../utils/openCentered.js";

function priceFmt(x){ return typeof x==="number" ? x.toLocaleString() : x; }

const boxStyle = {
  height: 96,
  display: "grid",
  placeItems: "center",
  border: "1px solid #223",
  borderRadius: 8,
  marginBottom: 8,
  overflow: "hidden",
  background: "rgba(255,255,255,0.02)",
};

const TGS_CACHE = new Map();
function cacheGet(k){ return TGS_CACHE.get(k); }
function cacheSet(k,v){ TGS_CACHE.set(k,v); if(TGS_CACHE.size>30){ const f=TGS_CACHE.keys().next().value; TGS_CACHE.delete(f); } }

function useOnScreen(ref, rootMargin="800px"){
  const [v,setV]=React.useState(false);
  React.useEffect(()=>{
    const el=ref.current; if(!el) return;
    const io=new IntersectionObserver(([e])=>setV(e.isIntersecting),{root:null,rootMargin,threshold:0.01});
    io.observe(el);
    return ()=>io.disconnect();
  },[ref,rootMargin]);
  return v;
}

function TgsThumb({ fileId, uniq, onNoToken }){
  const params = new URLSearchParams();
  if (fileId) params.set("file_id", fileId);
  if (uniq) params.set("uniq", uniq);
  const lottieSrc = (fileId || uniq) ? `/api/gifts/sticker.lottie?${params.toString()}` : null;
  const ref = React.useRef(null);
  const animRef = React.useRef(null);

  React.useEffect(() => {
    if (!lottieSrc || !ref.current) return;
    let aborted = false;
    const controller = new AbortController();
    (async () => {
      try{
        const cached = cacheGet(lottieSrc);
        const data = cached ?? (await (async()=>{
          const r = await fetch(lottieSrc, { credentials: "include", signal: controller.signal });
          if (r.status === 409) {
            let b={}; try{ b=await r.json(); }catch{}
            if (b?.error === "no_bot_token") onNoToken?.();
            throw new Error("no_bot_token");
          }
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          const j = await r.json();
          cacheSet(lottieSrc, j);
          return j;
        })());
        if (aborted) return;
        if (animRef.current) { animRef.current.destroy(); animRef.current = null; }
        animRef.current = lottie.loadAnimation({
          container: ref.current,
          renderer: "svg",
          loop: true,
          autoplay: true,
          animationData: data,
          rendererSettings: { preserveAspectRatio: "xMidYMid meet", progressiveLoad: true, hideOnTransparent: true },
        });
      }catch(_){}
    })();
    return () => {
      aborted = true;
      controller.abort();
      if (animRef.current) { animRef.current.destroy(); animRef.current = null; }
    };
  }, [lottieSrc]);

  return <div style={boxStyle}><div ref={ref} style={{width:"100%",height:"100%",pointerEvents:"none"}}/></div>;
}

function ViewportCard({ g, onNoToken }){
  const shellRef = React.useRef(null);
  const visible = useOnScreen(shellRef);
  const limited = g.is_limited ? (g.available_amount!=null ? `Лимит: ${g.available_amount}` : "Лимит") : "Без лимита";
  const prem = g.require_premium ? "Premium" : "Обычный";
  return (
    <div ref={shellRef} className="card" style={{minHeight:200,padding:12}}>
      {visible ? (
        <>
          <TgsThumb fileId={g.sticker_file_id} uniq={g.sticker_unique_id} onNoToken={onNoToken} />
          <div style={{fontWeight:600,fontSize:12}}>#{g.id}</div>
          <div style={{fontSize:12}}>Цена: {priceFmt(g.price)}</div>
          <div style={{fontSize:12}}>{limited}</div>
          <div className="muted" style={{fontSize:12}}>{prem}</div>
        </>
      ) : (
        <>
          <div style={boxStyle}/>
          <div style={{height:12,marginTop:6,background:"rgba(255,255,255,0.05)",borderRadius:4}}/>
          <div style={{height:12,marginTop:6,background:"rgba(255,255,255,0.05)",borderRadius:4,width:"70%"}}/>
          <div style={{height:12,marginTop:6,background:"rgba(255,255,255,0.05)",borderRadius:4,width:"50%"}}/>
        </>
      )}
    </div>
  );
}

export default function GiftsPage(){
  const [items,setItems]=React.useState([]);
  const [loading,setLoading]=React.useState(false);
  const [auto,setAuto]=React.useState(false);
  const [hasAcc,setHasAcc]=React.useState(false);
  const [noToken,setNoToken]=React.useState(false);

  const PERIOD = 30;

  const filterTgs = React.useCallback(arr =>
    (arr||[]).filter(g=>g.sticker_file_id && (String(g.sticker_mime||"").includes("tgs") || String(g.sticker_mime||"").includes("gzip")))
  ,[]);

  const load = React.useCallback(async () => {
    const r = await listGifts();
    setItems(filterTgs(r.items));
  }, [filterTgs]);

  React.useEffect(()=>{ load(); },[load]);
  React.useEffect(()=>{ (async()=>{ try{ const r=await getGiftsSettings(); setAuto(!!r.auto_refresh);}catch{} })(); },[]);
  React.useEffect(()=>{ (async()=>{ try{ const r=await listAccounts(); setHasAcc(Array.isArray(r?.accounts)&&r.accounts.length>0); }catch{} })(); },[]);


  const doRefresh = React.useCallback(async () => {
    if (loading || !hasAcc) return;
    setLoading(true);
    try{
      const r = await refreshGifts();
      setItems(filterTgs(r.items));
    } finally { setLoading(false); }
  }, [loading, hasAcc, filterTgs]);

  const toggleAuto = React.useCallback(async ()=>{
    if (!hasAcc) return;
    const v=!auto;
    setAuto(v);
    try{ await setGiftsSettings(v); }catch{ setAuto(!v); }
  },[auto,hasAcc]);

  React.useEffect(() => {
    if (!auto || !hasAcc) return;
    let stopped=false, t=null;
    const schedule=()=>{ if(stopped) return; t=setTimeout(tick, PERIOD*1000); };
    const tick=async()=>{ if(stopped||document.hidden) return schedule(); await doRefresh(); schedule(); };
    const onVis=()=>{ if(!auto||!hasAcc) return; if(!document.hidden){ clearTimeout(t); schedule(); } };
    schedule();
    document.addEventListener("visibilitychange", onVis);
    return ()=>{ stopped=true; clearTimeout(t); document.removeEventListener("visibilitychange", onVis); };
  }, [auto, hasAcc, doRefresh]);

  return (
    <div className="wrap">
      {noToken && (
        <div className="card" style={{padding:12, marginBottom:12, display:"flex", alignItems:"center", gap:8}}>
          <div style={{flex:1}}>Нет Bot token. Укажите его в настройках, чтобы загрузить превью.</div>
          <button onClick={()=>openCentered("/settings","settings",520,420)}>Открыть настройки</button>
        </div>
      )}

      <div className="header" style={{marginBottom:12, gap:8, alignItems:"center"}}>
        <h2 style={{margin:0}}>Подарки</h2>
        <div className="spacer"/>
        {hasAcc && (
          <>
            <label className="switch">
              <input type="checkbox" checked={auto} onChange={toggleAuto}/>
              <span className="switch__track"><span className="switch__thumb"/></span>
              <span className="switch__text">Автообновление</span>
            </label>
            <button onClick={doRefresh} disabled={loading}>{loading ? "Обновляю…" : "Обновить"}</button>
          </>
        )}
      </div>

      <div className="list" style={{gridTemplateColumns:"repeat(auto-fill,minmax(150px,1fr))",gap:12}}>
        {items.map(g=> <ViewportCard key={g.id} g={g} onNoToken={()=>setNoToken(true)} />)}
      </div>
    </div>
  );
}
