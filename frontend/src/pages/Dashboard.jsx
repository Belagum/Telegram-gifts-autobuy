// src/pages/Dashboard.jsx
import React,{useEffect,useState} from "react";
import { me, listAccounts, listApiProfiles } from "../api";
import AccountList from "../components/AccountList.jsx";
import AddApiModal from "../components/AddApiModal.jsx";
import AddAccountModal from "../components/AddAccountModal.jsx";
import SelectApiProfileModal from "../components/SelectApiProfileModal.jsx";
import { useNavigate } from "react-router-dom";

export default function Dashboard(){
  const nav = useNavigate();
  const [accounts,setAccounts]=useState(undefined);
  const [apiProfiles,setApiProfiles]=useState([]);
  const [openApi,setOpenApi]=useState(false);
  const [openSelect,setOpenSelect]=useState(false);
  const [openAcc,setOpenAcc]=useState(false);
  const [apiProfileId,setApiProfileId]=useState(null);

  const load=async()=>{
    await me();
    const res=await listAccounts();
    const a=res?.accounts;
    setAccounts(Array.isArray(a)? a : undefined);
  };
  const refreshProfiles=async()=>{
    const {items}=await listApiProfiles();
    setApiProfiles(items||[]);
  };

  useEffect(()=>{ load().catch(()=>{ nav("/login"); }); },[]);

  const startAdd=async()=>{ await refreshProfiles(); setOpenSelect(true); };

  const onApiChosen=(id)=>{ setApiProfileId(id); setOpenSelect(false); setOpenAcc(true); };
  const onAddNewFromSelect=()=>{ setOpenSelect(false); setOpenApi(true); };

  const onApiSaved=async()=>{ await refreshProfiles(); setOpenApi(false); setOpenSelect(true); };
  const onApiClosed=async()=>{ await refreshProfiles(); setOpenApi(false); setOpenSelect(true); };

  const done=()=>{ setOpenAcc(false); setApiProfileId(null); load(); };

  return (
    <>
      <div className="header">
        <h2>TG Gifts</h2><div className="spacer"/><button onClick={startAdd}>Добавить аккаунт</button>
      </div>

      <AccountList accounts={accounts}/>

      {openSelect && (
        <SelectApiProfileModal
          items={apiProfiles}
          onChoose={onApiChosen}
          onAddNew={onAddNewFromSelect}
          onClose={()=>setOpenSelect(false)}
        />
      )}

      {openApi && (
        <AddApiModal
          onClose={onApiClosed}
          onSaved={onApiSaved}
        />
      )}

      {openAcc && (
        <AddAccountModal
          apiProfileId={apiProfileId}
          onClose={()=>setOpenAcc(false)}
          onSuccess={done}
        />
      )}
    </>
  );
}
