// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import React,{createContext,useContext,useEffect,useMemo,useRef,useState,useCallback} from "react";

const Ctx = createContext(null);

export function ModalProvider({children}){
  const [stack,setStack] = useState([]);            // [{id,onClose}]
  const [suspender,setSuspender] = useState(null);  // id, скрывающий остальных

  const register = useCallback((id,onClose)=>{
    setStack(s => s.some(x=>x.id===id) ? s : [...s,{id,onClose}]);
    return () => setStack(s => s.filter(x => x.id !== id));
  },[]);

  // Один keydown-обработчик + актуальный стек в ref
  const stackRef = useRef(stack);
  useEffect(()=>{ stackRef.current = stack; },[stack]);
  useEffect(()=>{
    const onKey = e => {
      if(e.key === "Escape" && stackRef.current.length){
        const top = stackRef.current[stackRef.current.length-1];
        top.onClose?.();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  },[]);

  const value = useMemo(() => ({
    stack, register, suspender, setSuspender
  }), [stack, register, suspender]);

   useEffect(()=>{
      if (suspender && !stack.some(x => x.id === suspender)) {
        setSuspender(null);
      }
   }, [stack, suspender]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

let uid = 0;
export function useModal(onClose){
  const ctx = useContext(Ctx);
  if(!ctx) throw new Error("Wrap with <ModalProvider>");

  const idRef = useRef(`m${++uid}`);

  // Регистрируемся только при маунте/смене onClose
  useEffect(() => ctx.register(idRef.current, onClose), [ctx.register, onClose]);

  const isTop = ctx.stack.length && ctx.stack[ctx.stack.length-1].id === idRef.current;
  const hidden = !!ctx.suspender && ctx.suspender !== idRef.current;

  const suspendAllExceptSelf = () => ctx.setSuspender(idRef.current);
  const resumeAll = () => { if(ctx.suspender === idRef.current) ctx.setSuspender(null); };

  return { id:idRef.current, isTop, hidden, suspendAllExceptSelf, resumeAll };
}
