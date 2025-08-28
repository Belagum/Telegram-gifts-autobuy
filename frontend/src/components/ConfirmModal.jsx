import React,{useEffect} from "react";
import { createPortal } from "react-dom";
import { useModal } from "../ui/ModalStack.jsx";

export default function ConfirmModal({title,message,onConfirm,onCancel}){
  const {isTop,hidden,suspendAllExceptSelf,resumeAll}=useModal(onCancel);
  useEffect(()=>{ suspendAllExceptSelf(); return ()=>resumeAll(); },[]);
  if(hidden) return null;

  const backdrop=()=>{ if(isTop) onCancel(); };

  return createPortal(
    <div className="modal modal-confirm" onClick={backdrop}>
      <div className="modal-body modal-confirm" onClick={e=>e.stopPropagation()}>
        <h3 className="modal-title">{title}</h3>
        <div className="modal-text">{message}</div>
        <div className="actions">
          <button className="btn" onClick={onConfirm}>Да</button>
          <button className="btn link" onClick={onCancel}>Отмена</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
