// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

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

React.useEffect(() => {
  const pub = loc.pathname.startsWith("/login") || loc.pathname.startsWith("/register");
  let aborted = false;

  if (pub) {
    (async () => {
      try {
        await me();
        if (!aborted) nav("/", { replace: true });
      } catch {
        if (!aborted) setReady(true);
      }
    })();
    return () => { aborted = true; };
  }

  if (subOnceRef.current) return;
  subOnceRef.current = true;

  let aborted2 = false;
  (async () => {
    try {
      await me();
      if (!aborted2) setReady(true);
    } catch {
      if (!aborted2) nav("/login", { replace: true });
    }
  })();
  return () => { aborted2 = true; };
}, [loc.pathname, nav]);

  if (!ready) return null;
  return <div className="wrap"><Outlet/></div>;
}
