// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React,{useState,useMemo} from "react";
import { createChannel, updateChannel } from "../api";
import { showError, showPromise } from "../notify";
import { useModal } from "../ui/ModalStack.jsx";

export default function EditChannelModal({onClose,onSaved,initial}){
  const {isTop,hidden}=useModal(onClose);
  const isEdit=!!(initial&&initial.id);

  const [channelId,setChannelId]=useState(initial?.channel_id ?? "");
  const [title,setTitle]=useState(initial?.title ?? "");
  const [pMin,setPMin]=useState(initial?.price_min!=null?String(initial.price_min):"");
  const [pMax,setPMax]=useState(initial?.price_max!=null?String(initial.price_max):"");
  const [sMin,setSMin]=useState(initial?.supply_min!=null?String(initial.supply_min):"");
  const [sMax,setSMax]=useState(initial?.supply_max!=null?String(initial.supply_max):"");
  const [saving,setSaving]=useState(false);

  const onlyDigits=(s)=>s.replace(/[^\d]/g,"");
  const numericChange=(setter)=>(e)=>setter(onlyDigits(e.target.value));
  const blockNonDigits=(e)=>{ if(e.data && /[^\d]/.test(e.data)) e.preventDefault(); };
  const onPasteDigits=(setter)=>(e)=>{ e.preventDefault(); const t=(e.clipboardData.getData("text")||""); setter(onlyDigits(t)); };

  const chanSanitize=(s)=>s.replace(/[^-\d]/g,"").replace(/(?!^)-/g,""); // '-' только в начале
  const chanChange=(e)=>setChannelId(chanSanitize(e.target.value));
  const chanBeforeInput=(e)=>{ if(e.data && /[^-\d]/.test(e.data)) e.preventDefault(); };

  const toInt=(s)=>s===""?null:parseInt(s,10);

  const idError=useMemo(()=>{
    if(isEdit) return "";
    const v=(channelId||"").trim();
    if(!v) return "Укажи ID канала";
    if(!/^-?\d+$/.test(v)) return "ID — только цифры и ‘-’";
    return "";
  },[channelId,isEdit]);

  const rangeError=useMemo(()=>{
    const pm=toInt(pMin), px=toInt(pMax), sm=toInt(sMin), sx=toInt(sMax);
    if (pm!=null && px!=null && pm>px) return "price_min ≤ price_max";
    if (sm!=null && sx!=null && sm>sx) return "supply_min ≤ supply_max";
    return "";
  },[pMin,pMax,sMin,sMax]);

  const error = idError || rangeError;
  const canSave = !saving && !error;

  const save=async(e)=>{ e?.preventDefault?.(); e?.stopPropagation?.(); if(!canSave){ showError(error||"Исправь ошибки"); return; }
    setSaving(true);
    try{
      const payload={ title:(title||"").trim()||null, price_min:toInt(pMin), price_max:toInt(pMax), supply_min:toInt(sMin), supply_max:toInt(sMax) };
      if(isEdit){
        await showPromise(updateChannel(initial.id,payload),"Сохраняю…","Сохранено","Ошибка сохранения");
        onSaved?.();
      }else{
        const id=(channelId||"").trim();
        const res=await showPromise(createChannel({...payload,channel_id:id}),"Соединяюсь…",(r)=>`Канал ${r?.channel_id ?? id} добавлен`,"Не удалось добавить канал");
        onSaved?.(res?.channel_id ?? id);
      }
    }finally{ setSaving(false); }
  };

  if(hidden) return null;

  return (
    <div className="modal" onClick={()=>{ if(isTop) onClose(); }}>
      <div className="modal-body" onClick={(e)=>e.stopPropagation()}>
        <button className="close-x" onClick={onClose} aria-label="close">×</button>
        <h3 className="modal-title center">{isEdit?"Канал":"Добавить канал"}</h3>

        <form className="form" onSubmit={save}>
          {!isEdit && (
            <input
              placeholder="-1001234567890"
              value={channelId}
              onChange={chanChange}
              onBeforeInput={chanBeforeInput}
              onPaste={(e)=>{ e.preventDefault(); setChannelId(chanSanitize(e.clipboardData.getData("text")||"")); }}
            />
          )}

          <input placeholder="Название (опц.)" value={title} onChange={(e)=>setTitle(e.target.value)} />

          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
            <input
              type="text" inputMode="numeric" pattern="\d*" placeholder="Цена мин"
              value={pMin} onChange={numericChange(setPMin)} onBeforeInput={blockNonDigits} onPaste={onPasteDigits(setPMin)}
            />
            <input
              type="text" inputMode="numeric" pattern="\d*" placeholder="Цена макс"
              value={pMax} onChange={numericChange(setPMax)} onBeforeInput={blockNonDigits} onPaste={onPasteDigits(setPMax)}
            />
          </div>

          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
            <input
              type="text" inputMode="numeric" pattern="\d*" placeholder="Саплай мин"
              value={sMin} onChange={numericChange(setSMin)} onBeforeInput={blockNonDigits} onPaste={onPasteDigits(setSMin)}
            />
            <input
              type="text" inputMode="numeric" pattern="\d*" placeholder="Саплай макс"
              value={sMax} onChange={numericChange(setSMax)} onBeforeInput={blockNonDigits} onPaste={onPasteDigits(setSMax)}
            />
          </div>

          {(error) && <div style={{color:"#f55",marginTop:6,fontSize:13}}>{error}</div>}

          <div style={{marginTop:8}}>
            <button type="button" onClick={save} disabled={!canSave} aria-disabled={!canSave} title={error||""} style={{width:"100%"}}>
              {saving?"Сохранение...":"Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
