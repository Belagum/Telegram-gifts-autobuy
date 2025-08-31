// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getSettings, setSettings } from "../api";

export default function SettingsPage(){
  const [token,setToken]=React.useState("");
  const [chatTail,setChatTail]=React.useState("");
  const [targetId,setTargetId]=React.useState(""); // NEW
  const [saving,setSaving]=React.useState(false);

  React.useEffect(()=>{ (async()=>{ try{
    const r=await getSettings();
    setToken(r.bot_token||"");
    const ch=String(r.notify_chat_id??""); setChatTail(ch.startsWith("-100")?ch.slice(4):ch.replace(/\D+/g,""));
    setTargetId(r.buy_target_id!=null?String(r.buy_target_id):"");
  }catch{} })(); },[]);

  const onChatChange=e=>{
    const d=(e.target.value||"").replace(/\D+/g,"");
    setChatTail(d.startsWith("100")?d.slice(3):d);
  };

  const onTargetChange=e=>{
    const raw=(e.target.value||"").trim();
    const ok = /^-?\d*$/.test(raw);
    if (ok) setTargetId(raw);
  };

  const save=async()=>{
    if (saving) return;
    setSaving(true);
    try{
      const chatId = chatTail ? `-100${chatTail}` : null;
      const tgt = targetId.trim()==="" ? null : Number(targetId);
      await setSettings((token||"").trim()||null, chatId, tgt);
    }finally{
      setSaving(false);
      window.close();
    }
  };

  return (
    <div className="wrap" style={{paddingBottom:76}}>
      <div className="header" style={{marginBottom:12,gap:12}}>
        <h2 style={{margin:0}}>Настройки</h2><div className="spacer"/>
      </div>

      <div className="card" style={{padding:12,display:"grid",gap:8,marginBottom:12}}>
        <div className="title">Bot token</div>
        <input type="password" placeholder="123456:ABCDEF..." value={token} onChange={e=>setToken(e.target.value)}/>
        <div className="muted" style={{fontSize:12}}>Используется для уведомлений и скачивания превью.</div>
      </div>

      <div className="card" style={{padding:12,display:"grid",gap:8,marginBottom:12}}>
        <div className="title">ID чата для уведомлений</div>
        <div style={{display:"flex",gap:8,alignItems:"center"}}>
          <div style={{padding:"0 8px",border:"1px solid #223",borderRadius:6,height:36,display:"flex",alignItems:"center"}}>-100</div>
          <input inputMode="numeric" pattern="[0-9]*" placeholder="XXXXXXXXXXXX" value={chatTail} onChange={onChatChange} style={{flex:1}}/>
        </div>
        <div className="muted" style={{fontSize:12}}>Можно вставить полный ID — префикс добавится автоматически.</div>
      </div>

      <div className="card" style={{padding:12,display:"grid",gap:8,marginBottom:12}}>
        <div className="title">ID получателя покупок (опционально)</div>
        <input inputMode="numeric" pattern="-?[0-9]*" placeholder="Напр. 123456789 или -1001234567890" value={targetId} onChange={onTargetChange}/>
        <div className="muted" style={{fontSize:12}}>Если заполнено — покупки отправляются на этот ID. Пусто — по каналам из списка.</div>
      </div>

      <div style={{position:"fixed",left:0,right:0,bottom:0,padding:12,background:"#0f141b",borderTop:"1px solid #223"}}>
        <button onClick={save} disabled={saving} className="btn btn--progress" style={{width:"100%",height:44}}>
          {saving ? "Сохраняю…" : "Сохранить"}
        </button>
      </div>
    </div>
  );
}
