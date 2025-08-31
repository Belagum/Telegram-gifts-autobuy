// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import React,{useEffect,useState} from "react";
import openCentered from "../utils/openCentered.js";
import { me, listAccounts, listApiProfiles } from "../api";
import AccountList from "../components/AccountList.jsx";
import AddApiModal from "../components/AddApiModal.jsx";
import AddAccountModal from "../components/AddAccountModal.jsx";
import SelectApiProfileModal from "../components/SelectApiProfileModal.jsx";
import ChannelsModal from "../components/ChannelsModal.jsx";
import { useNavigate } from "react-router-dom";

export default function Dashboard(){
  const nav = useNavigate();
  const [accounts,setAccounts]=useState([]);
  const [apiProfiles,setApiProfiles]=useState([]);
  const [openApi,setOpenApi]=useState(false);
  const [openSelect,setOpenSelect]=useState(false);
  const [openAcc,setOpenAcc]=useState(false);
  const [openChannels,setOpenChannels]=useState(false);
  const [apiProfileId,setApiProfileId]=useState(null);

  const openGifts=()=> openCentered("/gifts","gifts",520,700);
  const openSettings=()=> openCentered("/settings","settings",520,600);

  const load=async()=>{ await me(); const res=await listAccounts(); const a=res?.items??res?.accounts??[]; setAccounts(Array.isArray(a)?a:[]); };
  const refreshProfiles=async()=>{ const {items}=await listApiProfiles(); setApiProfiles(items||[]); };
  useEffect(()=>{ load().catch(()=>{ nav("/login"); }); },[]);
  const startAdd=async()=>{ await refreshProfiles(); setOpenSelect(true); };
  const onApiChosen=(id)=>{ setApiProfileId(id); setOpenSelect(false); setOpenAcc(true); };
  const onAddNewFromSelect=()=>{ setOpenSelect(false); setOpenApi(true); };
  const onApiSaved=async()=>{ await refreshProfiles(); setOpenApi(false); setOpenSelect(true); };
  const onApiClosed=async()=>{ await refreshProfiles(); setOpenApi(false); setOpenSelect(true); };
  const done=()=>{ setOpenAcc(false); setApiProfileId(null); load(); };
  const hasAcc = accounts?.length > 0;

  return (
    <>
      <div className="header" style={{marginBottom:12, gap:12}}>
        <h2 style={{margin:0}}>TG Gifts</h2>
        <div className="spacer"/>
        <button onClick={()=>setOpenChannels(true)}>Каналы</button>
        <button onClick={openSettings}>Настройки</button>
        {hasAcc && <button onClick={openGifts}>Подарки</button>}
        <button onClick={startAdd}>Добавить аккаунт</button>
      </div>

      <AccountList accounts={accounts||[]} />

      {openSelect && (
        <SelectApiProfileModal
          items={apiProfiles}
          onChoose={onApiChosen}
          onAddNew={onAddNewFromSelect}
          onClose={()=>setOpenSelect(false)}
        />
      )}
      {openApi && (<AddApiModal onClose={onApiClosed} onSaved={onApiSaved} />)}
      {openAcc && (<AddAccountModal apiProfileId={apiProfileId} onClose={()=>setOpenAcc(false)} onSuccess={done} />)}
      {openChannels && (<ChannelsModal onClose={()=>setOpenChannels(false)} />)}
    </>
  );
}
