// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React, {useState} from "react";
import { renameApiProfile, deleteApiProfile } from "../api";
import { showError, showSuccess } from "../notify";
import ConfirmModal from "./ConfirmModal.jsx";
import { useModal } from "../ui/ModalStack.jsx";

export default function SelectApiProfileModal({items,onChoose,onAddNew,onClose}){
  const {isTop,hidden}=useModal(onClose);
  const [list,setList]=useState(items||[]);
  const [editingId,setEditingId]=useState(null);
  const [editVal,setEditVal]=useState("");
  const [menuOpen,setMenuOpen]=useState(null);
  const [confirm,setConfirm]=useState(null);

  const startEdit=(it)=>{ setEditingId(it.id); setEditVal((it.name||"").trim() || `API ${it.api_id}`); setMenuOpen(null); };
  const submitEdit=async()=>{ const id=editingId; if(!id) return; const it=list.find(x=>x.id===id); if(!it){ setEditingId(null); return; } const next=(editVal||"").trim(); const prev=((it.name||"").trim() || `API ${it.api_id}`); if(next===prev){ setEditingId(null); return; } try{ await renameApiProfile(id,next); setList(prev=>prev.map(x=>x.id===id?{...x,name:next}:x)); setEditingId(null); showSuccess("Название обновлено"); }catch(e){ showError(e,"Не удалось обновить"); } };
  const askDelete=(it)=>{ setConfirm({id:it.id,name:(it.name||"").trim()||`API ${it.api_id}`}); setMenuOpen(null); };
  const doDelete=async()=>{ try{ await deleteApiProfile(confirm.id); setList(prev=>prev.filter(x=>x.id!==confirm.id)); setConfirm(null); showSuccess("API удалён"); }catch(e){ setConfirm(null); showError(e,e?.error==="api_profile_in_use"?"API используется аккаунтами":"Не удалось удалить"); } };

  const backdropClick=()=>{ if(menuOpen) setMenuOpen(null); else if(isTop) onClose(); };
  const bodyClick=(e)=>{ e.stopPropagation(); if(menuOpen) setMenuOpen(null); };

  if (hidden && !confirm) return null;
  if (hidden && confirm) {
    return (
      <ConfirmModal
        title="Удалить API профиль?"
        message={`«${confirm.name}» будет удалён. Если он используется аккаунтами — удаление запрещено.`}
        onCancel={()=>setConfirm(null)}
        onConfirm={doDelete}
      />
    );
  }

  return (
    <div className="modal" onClick={backdropClick}>
      <div className="modal-body" onClick={bodyClick}>
        <button className="close-x" onClick={onClose} aria-label="close">×</button>
        <h3 className="modal-title center">Выбери API профиль</h3>

        <div className="list" style={{display:"grid",gap:8}}>
          {(!list || list.length===0) && <div>Профилей нет</div>}

          {list.map(it=>{
            const isEdit = editingId===it.id;
            return (
              <div key={it.id} className={`item row ${isEdit?"editing":""}`} style={{display:"flex",alignItems:"center",gap:8}}>
                <div style={{flex:1,cursor:isEdit?"default":"pointer"}} onClick={()=>!isEdit && onChoose(it.id)}>
                  {isEdit ? (
                    <input
                      className="inline-edit"
                      autoFocus
                      value={editVal}
                      onChange={e=>setEditVal(e.target.value)}
                      onKeyDown={e=>{ if(e.key==="Enter") submitEdit(); if(e.key==="Escape") setEditingId(null); }}
                      onBlur={submitEdit}
                    />
                  ) : (
                    <span>{(it.name||"").trim() || `API ${it.api_id}`}</span>
                  )}
                </div>

                <div className="kebab" onClick={(e)=>{ e.stopPropagation(); setMenuOpen(menuOpen===it.id?null:it.id); }}>⋮</div>

                {menuOpen===it.id && (
                  <div className="menu menu-anim" onClick={e=>e.stopPropagation()}>
                    <div className="menu-item" onClick={()=>startEdit(it)}>Переименовать</div>
                    <div className="menu-item danger" onClick={()=>askDelete(it)}>Удалить</div>
                  </div>
                )}
              </div>
            );
          })}

          <button className="link" onClick={onAddNew}>Добавить новый API</button>
        </div>

        {confirm && (
          <ConfirmModal
            title="Удалить API профиль?"
            message={`«${confirm.name}» будет удалён. Если он используется аккаунтами — удаление запрещено.`}
            onCancel={()=>setConfirm(null)}
            onConfirm={doDelete}
          />
        )}
      </div>
    </div>
  );
}
