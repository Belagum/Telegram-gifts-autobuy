// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getSettings, setSettings } from "../api";

function tailFromId(v){
  const d = String(v ?? "").replace(/\D+/g,"");
  return d.startsWith("100") ? d.slice(3) : d;
}

export default function SettingsPage(){
  const [token,setToken]=React.useState("");
  const [chatTail,setChatTail]=React.useState("");
  const [saving,setSaving]=React.useState(false);

  React.useEffect(()=>{ (async()=>{ try{
    const r=await getSettings();
    setToken(r.bot_token||"");
    setChatTail(tailFromId(r.notify_chat_id));
  }catch{} })(); },[]);

  const onChatChange = (e)=>{
    const raw = e.target.value || "";
    const d = raw.replace(/\D+/g,"");
    setChatTail(d.startsWith("100") ? d.slice(3) : d);
  };

  const save=async()=>{
    if (saving) return;
    setSaving(true);
    try{
      const chatId = chatTail ? `-100${chatTail}` : null;
      await setSettings(token||null, chatId);
      window.close();
    }finally{
      setSaving(false);
    }
  };

  return (
    <div className="wrap" style={{paddingBottom:76}}>
      <div className="header" style={{marginBottom:12,gap:12}}>
        <h2 style={{margin:0}}>Настройки</h2>
        <div className="spacer"/>
      </div>

      <div className="card" style={{padding:12,display:"grid",gap:8,marginBottom:12}}>
        <div className="title">Bot token</div>
        <input
          type="password"
          placeholder="123456:ABCDEF..."
          value={token}
          onChange={e=>setToken(e.target.value)}
        />
        <div className="muted" style={{fontSize:12}}>Используется для уведомлений и скачивания превью.</div>
      </div>

      <div className="card" style={{padding:12,display:"grid",gap:8,marginBottom:12}}>
        <div className="title">ID чата для уведомлений</div>
        <div style={{display:"flex",gap:8,alignItems:"center"}}>
          <div style={{padding:"0 8px",border:"1px solid #223",borderRadius:6,height:36,display:"flex",alignItems:"center"}}>-100</div>
          <input
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="XXXXXXXXXXXX"
            value={chatTail}
            onChange={onChatChange}
            style={{flex:1}}
          />
        </div>
        <div className="muted" style={{fontSize:12}}>Можно вставить полный ID — префикс будет добавлен автоматически.</div>
      </div>

      <div style={{position:"fixed",left:0,right:0,bottom:0,padding:12,background:"#0f141b",borderTop:"1px solid #223"}}>
        <button onClick={save} disabled={saving} style={{width:"100%",height:44}}>
          {saving ? "Сохраняю…" : "Сохранить"}
        </button>
      </div>
    </div>
  );
}
