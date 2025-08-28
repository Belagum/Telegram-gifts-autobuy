import React from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { me, onUnauthorized } from "./api";

export default function App(){
  const nav = useNavigate();
  const loc = useLocation();
  const [ready, setReady] = React.useState(false);
  const subOnceRef = React.useRef(false);

  React.useEffect(()=>{
    const unsub = onUnauthorized(()=>{ setReady(true); nav("/login", { replace: true }); });
    return unsub;
  },[nav]);

  React.useEffect(()=>{
    const pub = loc.pathname.startsWith("/login") || loc.pathname.startsWith("/register");
    if (pub) { setReady(true); return; }
    if (subOnceRef.current) return;
    subOnceRef.current = true;
    let ab = false;
    (async ()=>{
      try { await me(); if (!ab) setReady(true); }
      catch { if (!ab) nav("/login", { replace: true }); }
    })();
    return ()=>{ ab = true; };
  },[loc.pathname, nav]);

  if (!ready) return null;
  return <div className="wrap"><Outlet/></div>;
}
