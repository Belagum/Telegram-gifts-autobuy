// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import React,{useEffect,useState} from "react";
import { sendCode, confirmCode, confirmPassword, cancelLogin } from "../api";
import { showError, showInfo, showPromise } from "../notify";
import { useModal } from "../ui/ModalStack.jsx";

export default function AddAccountModal({apiProfileId,onClose,onSuccess}){
  const {isTop,hidden}=useModal(onClose);
  const [step,setStep]=useState("phone");
  const [phone,setPhone]=useState(""), [loginId,setLoginId]=useState(""), [code,setCode]=useState(""), [password,setPassword]=useState("");
  const [busy,setBusy]=useState(null); // 'send'|'code'|'pass'|'cancel'|null

  useEffect(()=>{ const onKey=e=>{ if(e.key==="Escape") onClose(); if(e.key==="Enter") { if(step==="phone") doSend(); else if(step==="code") doCode(); else if(step==="password") doPass(); } }; document.addEventListener("keydown",onKey); return ()=>document.removeEventListener("keydown",onKey); },[step,phone,code,password]);

  const doSend=async()=>{
    const ph = phone.trim();
    if(!ph) return showError({message:"Введите телефон"});
    setBusy("send");
    try{
      const p = sendCode(apiProfileId, ph);
      showPromise(p, "Отправляю код…", "Код отправлен", "Ошибка отправки кода");
      const r = await p;
      setLoginId(r.login_id); setStep("code");
    } finally { setBusy(null); }
  };

  const doCode=async()=>{
    const c = code.trim();
    if(!c) return showError({message:"Введите код"});
    setBusy("code");
    try{
      const p = confirmCode(loginId, c);
      showPromise(p, "Проверяю код…", "Код подтверждён", "Ошибка подтверждения");
      const r = await p;
      if(r.need_2fa){ setStep("password"); showInfo("Требуется пароль 2FA"); }
      else if(r.ok){ onSuccess(); onClose(); }
      else showError(r, "Ошибка подтверждения");
    } finally { setBusy(null); }
  };

  const doPass=async()=>{
    const pwd = password;
    if(!pwd) return showError({message:"Введите пароль"});
    setBusy("pass");
    try{
      const p = confirmPassword(loginId, pwd);
      showPromise(p, "Входим…", "Аккаунт добавлен", "Ошибка пароля");
      const r = await p;
      if(r.ok){ onSuccess(); onClose(); }
      else showError(r, "Ошибка пароля");
    } finally { setBusy(null); }
  };

  const doCancel=async()=>{
    setBusy("cancel");
    try{
      if(loginId){
        const p = cancelLogin(loginId);
        showPromise(p, "Отменяю…", "Вход отменён", "Не удалось отменить");
        await p;
      }
    } finally { setBusy(null); onClose(); }
  };

  const onBackdropClick=()=>{ if(isTop) onClose(); };
  if(hidden) return null;

  return (
    <div className="modal" onClick={onBackdropClick}>
      <div className="modal-body" onClick={e=>e.stopPropagation()}>
        <button className="close-x" onClick={onClose} aria-label="close">×</button>
        <h3 style={{textAlign:"center"}}>Добавить аккаунт</h3>

        {step==="phone" && (
          <div className="form">
            <input placeholder="+79998887766" value={phone} onChange={e=>setPhone(e.target.value)} disabled={busy==="send"}/>
            <button onClick={doSend} disabled={busy==="send" || !phone.trim()}>Отправить код</button>
          </div>
        )}

        {step==="code" && (
          <div className="form">
            <input placeholder="Код из Telegram" value={code} onChange={e=>setCode(e.target.value)} disabled={busy==="code"}/>
            <button onClick={doCode} disabled={busy==="code" || !code.trim()}>Подтвердить</button>
          </div>
        )}

        {step==="password" && (
          <div className="form">
            <input type="password" placeholder="Пароль 2FA" value={password} onChange={e=>setPassword(e.target.value)} disabled={busy==="pass"}/>
            <button onClick={doPass} disabled={busy==="pass" || !password}>Войти</button>
          </div>
        )}
      </div>
    </div>
  );
}
