// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import React from "react";
import { getSettings, setSettings } from "../api";

export default function SettingsPage(){
  const [token,setToken]=React.useState("");
  const [saving,setSaving]=React.useState(false);

  React.useEffect(()=>{ (async()=>{ try{ const r=await getSettings(); setToken(r.bot_token||""); }catch{} })(); },[]);

  const save=async()=>{
    if (saving) return;
    setSaving(true);
    try{
      await setSettings(token||null);
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

      <div className="card" style={{padding:12,display:"grid",gap:8}}>
        <div className="title">Bot token</div>
        <input
          type="password"
          placeholder="123456:ABCDEF..."
          value={token}
          onChange={e=>setToken(e.target.value)}
        />
        <div className="muted" style={{fontSize:12}}>Используется для уведомлений и скачивания превью.</div>
      </div>

      <div style={{
        position:"fixed", left:0, right:0, bottom:0,
        padding:12, background:"#0f141b", borderTop:"1px solid #223"
      }}>
        <button onClick={save} disabled={saving} style={{width:"100%",height:44}}>
          {saving ? "Сохраняю…" : "Сохранить"}
        </button>
      </div>
    </div>
  );
}
