// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React,{useEffect,useState} from "react";
import { listChannels, deleteChannel, updateChannel } from "../api";
import { showError, showSuccess } from "../notify";
import ConfirmModal from "./ConfirmModal.jsx";
import EditChannelModal from "./EditChannelModal.jsx";
import { useModal } from "../ui/ModalStack.jsx";

function titleOf(it){ return (it.title||"").trim() || String(it.channel_id); }

export default function ChannelsModal({onClose}){
  const {isTop,hidden}=useModal(onClose);
  const [items,setItems]=useState([]);
  const [confirm,setConfirm]=useState(null);     // {id,name} | null
  const [edit,setEdit]=useState(null);           // {} -> add, {id,...} -> edit
  const [menuOpen,setMenuOpen]=useState(null);   // id | null
  const [editingId,setEditingId]=useState(null);
  const [editVal,setEditVal]=useState("");

  const load=async()=>{
    try{ const {items}=await listChannels(); setItems(items||[]); }
    catch(e){ showError(e,"Не удалось загрузить"); }
  };
  useEffect(()=>{ load(); },[]);

  const startRename=(it)=>{ setEditingId(it.id); setEditVal(titleOf(it)); setMenuOpen(null); };
  const submitRename=async()=>{
    const id=editingId; if(!id) return;
    const it=items.find(x=>x.id===id); if(!it){ setEditingId(null); return; }
    const next=(editVal||"").trim(); const prev=titleOf(it);
    if(next===prev){ setEditingId(null); return; }
    try{
      await updateChannel(id,{ title: next });
      setItems(prev=>prev.map(x=>x.id===id?{...x,title:next}:x));
      setEditingId(null); showSuccess("Название обновлено");
    }catch(e){ showError(e,"Не удалось обновить"); }
  };

  const askDelete=(it)=>{ setConfirm({id:it.id,name:titleOf(it)}); setMenuOpen(null); };
  const doDelete=async()=>{
    try{ await deleteChannel(confirm.id); setItems(prev=>prev.filter(x=>x.id!==confirm.id)); setConfirm(null); showSuccess("Канал удалён"); }
    catch(e){ setConfirm(null); showError(e,"Не удалось удалить"); }
  };

  const backdropClick=()=>{ if(menuOpen) setMenuOpen(null); else if(isTop) onClose(); };
  const bodyClick=(e)=>{ e.stopPropagation(); if(menuOpen) setMenuOpen(null); };

  // 1) подтверждение — показываем только ConfirmModal
  if (confirm){
    return (
      <ConfirmModal
        title="Удалить канал?"
        message={`«${confirm.name}» будет удалён.`}
        onCancel={()=>setConfirm(null)}
        onConfirm={doDelete}
      />
    );
  }

  // 2) редактирование/добавление — показываем только EditChannelModal
  if (edit){
    return (
      <EditChannelModal
        initial={Object.keys(edit).length?edit:null}
        onClose={()=>setEdit(null)}
        onSaved={()=>{ setEdit(null); load(); }}
      />
    );
  }

  if (hidden) return null;

  // 3) основной список каналов
  return (
    <div className="modal" onClick={backdropClick}>
      <div className="modal-body" onClick={bodyClick}>
        <button className="close-x" onClick={onClose} aria-label="close">×</button>
        <h3 className="modal-title center">Каналы</h3>

        <div className="list" style={{display:"grid",gap:8}}>
          {(!items || items.length===0) && <div>Каналов нет</div>}

          {items.map(it=>{
            const isRename = editingId===it.id;
            return (
              <div key={it.id} className={`item row ${isRename?"editing":""}`} style={{display:"flex",alignItems:"center",gap:8}}>
                <div
                  style={{flex:1,cursor:isRename?"default":"pointer"}}
                  onClick={()=>!isRename && setEdit(it)}
                >
                  {isRename ? (
                    <input
                      className="inline-edit"
                      autoFocus
                      value={editVal}
                      onChange={e=>setEditVal(e.target.value)}
                      onKeyDown={e=>{ if(e.key==="Enter") submitRename(); if(e.key==="Escape") setEditingId(null); }}
                      onBlur={submitRename}
                    />
                  ) : (
                    <>
                      <div>{titleOf(it)}</div>
                      <div style={{opacity:0.6,fontSize:12}}>{it.channel_id}</div>
                    </>
                  )}
                </div>

                <div className="kebab" onClick={(e)=>{ e.stopPropagation(); setMenuOpen(menuOpen===it.id?null:it.id); }}>⋮</div>

                {menuOpen===it.id && (
                  <div className="menu menu-anim" onClick={e=>e.stopPropagation()}>
                    <div className="menu-item" onClick={()=>startRename(it)}>Переименовать</div>
                    <div className="menu-item danger" onClick={()=>askDelete(it)}>Удалить</div>
                  </div>
                )}
              </div>
            );
          })}

          <button className="link" onClick={()=>setEdit({})}>Добавить канал</button>
        </div>
      </div>
    </div>
  );
}
