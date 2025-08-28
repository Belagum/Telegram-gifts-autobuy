const KEY = "token";
export function setToken(t){ localStorage.setItem(KEY, t); }
export function getToken(){ return localStorage.getItem(KEY) || ""; }
export function clearToken(){ localStorage.removeItem(KEY); }
