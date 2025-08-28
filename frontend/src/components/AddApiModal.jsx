import React,{useEffect,useState} from "react";
import { createApiProfile } from "../api";
import { showError, showSuccess, showInfo } from "../notify";
import { useModal } from "../ui/ModalStack.jsx";

export default function AddApiModal({onClose,onSaved}){
  const {isTop,hidden}=useModal(onClose);
  const [apiId,setApiId]=useState(""), [apiHash,setApiHash]=useState(""), [name,setName]=useState("");
  useEffect(()=>{ const onKey=e=>{ if(e.key==="Escape") onClose(); }; document.addEventListener("keydown",onKey); return ()=>document.removeEventListener("keydown",onKey); },[onClose]);
  const save=async()=>{
    try{
      const r=await createApiProfile(apiId,apiHash,name);
      showSuccess("API сохранён"); onSaved(r.api_profile_id);
    }catch(e){
      if((e?.error==="duplicate_api_id"||e?.error==="duplicate_api_hash")&&e?.existing_id){ showInfo("Такой API уже есть — используем его"); onSaved(e.existing_id); }
      else showError(e,"Не удалось сохранить API");
    }
  };
  if(hidden) return null;
  return (
    <div className="modal" onClick={()=>{ if(isTop) onClose(); }}>
      <div className="modal-body" onClick={e=>e.stopPropagation()}>
        <button className="close-x" onClick={onClose} aria-label="close">×</button>
        <h3 className="modal-title center">API ID / API HASH</h3>
        <div className="form">
          <input placeholder="Отображаемое имя (опц.)" value={name} onChange={e=>setName(e.target.value)}/>
          <input placeholder="API ID" value={apiId} onChange={e=>setApiId(e.target.value)}/>
          <input placeholder="API HASH" value={apiHash} onChange={e=>setApiHash(e.target.value)}/>
          <button onClick={save}>Сохранить</button>
        </div>
      </div>
    </div>
  );
}
