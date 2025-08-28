// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import React,{useState} from "react";
import { register } from "../api";
import { useNavigate, Link } from "react-router-dom";
import { showError, showSuccess } from "../notify";

export default function Register(){
  const [u,setU]=useState(""), [p,setP]=useState("");
  const [loading,setLoading]=useState(false);
  const nav = useNavigate();

  const submit=async()=>{
    if(loading) return;
    setLoading(true);
    try{ await register(u,p); showSuccess("Аккаунт создан"); nav("/"); }
    catch(e){ showError(e, "Ошибка регистрации"); }
    finally{ setLoading(false); }
  };

  return (
    <div className="auth">
      <h2>Регистрация</h2>
      <input placeholder="username" value={u} onChange={e=>setU(e.target.value)} disabled={loading}/>
      <input type="password" placeholder="password" value={p} onChange={e=>setP(e.target.value)} disabled={loading}/>
      <button onClick={submit} disabled={loading} className={`btn ${loading?"btn--progress":""}`}>
        {loading ? "Загрузка…" : "Создать аккаунт"}
      </button>
      <div className="muted">Уже есть аккаунт? <Link to="/login">Войти</Link></div>
    </div>
  );
}
