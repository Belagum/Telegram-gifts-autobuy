// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React,{useState} from "react";
import { login } from "../api";
import { useNavigate, Link } from "react-router-dom";
import { showError, showSuccess } from "../notify";

export default function Login(){
  const [u,setU]=useState(""), [p,setP]=useState("");
  const [loading,setLoading]=useState(false);
  const nav = useNavigate();

  const submit=async()=>{
    if(loading) return;
    setLoading(true);
    try{ await login(u,p); showSuccess("Вход выполнен"); nav("/"); }
    catch(e){ showError(e, "Неверные данные"); }
    finally{ setLoading(false); }
  };

  return (
    <div className="auth">
      <h2>Вход</h2>
      <input placeholder="username" value={u} onChange={e=>setU(e.target.value)} disabled={loading}/>
      <input type="password" placeholder="password" value={p} onChange={e=>setP(e.target.value)} disabled={loading}/>
      <button onClick={submit} disabled={loading} className={`btn ${loading?"btn--progress":""}`}>
        {loading ? "Загрузка…" : "Войти"}
      </button>
      <div className="muted">Нет аккаунта? <Link to="/register">Зарегистрироваться</Link></div>
    </div>
  );
}
