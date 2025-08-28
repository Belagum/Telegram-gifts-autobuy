const base = "/api";

let unauthorizedHandled = false;
const isJson = (r) => (r.headers.get("content-type") || "").includes("application/json");

export function resetUnauthorizedFlag(){ unauthorizedHandled = false; }
export function onUnauthorized(fn){
  const h = () => fn();
  window.addEventListener("api:unauthorized", h);
  return () => window.removeEventListener("api:unauthorized", h);
}

export async function apiFetch(url, options={}){
  const r = await fetch(url, { credentials: "include", ...options });
  if (r.status === 401) {
    if (!unauthorizedHandled) {
      unauthorizedHandled = true;
      window.dispatchEvent(new Event("api:unauthorized"));
    }
    let body = {};
    try{ body = isJson(r) ? await r.json() : {}; }catch{}
    const err = body || { error: "unauthorized" };
    err.__unauth = true;
    throw err;
  }
  return r;
}

async function parseJson(r){
  const body = isJson(r) ? await r.json().catch(()=>({})) : {};
  if (!r.ok) throw body;
  return body;
}

const jget = (u, o={}) => apiFetch(u, o).then(parseJson);

// AUTH
export async function register(username, password){
  return jget(`${base}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}
export async function login(username, password){
  const res = await jget(`${base}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  resetUnauthorizedFlag();
  return res;
}
export async function logout(){
  const res = await jget(`${base}/auth/logout`, { method: "DELETE" });
  resetUnauthorizedFlag();
  return res;
}
export async function me(){ return jget(`${base}/me`); }

// ACCOUNTS
export async function listAccounts(){ return jget(`${base}/accounts`); }
export async function refreshAccount(id){
  return jget(`${base}/account/${id}/refresh`, { method: "POST" });
}
export async function refreshAccountStream(id, onEvent){
  const r = await apiFetch(`${base}/account/${id}/refresh`, {
    method: "POST",
    headers: { Accept: "application/x-ndjson" },
  });
  if (!r.body) return;
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line) continue;
      try { onEvent?.(JSON.parse(line)); } catch {}
    }
  }
}

// API PROFILES
export async function listApiProfiles(){ return jget(`${base}/apiprofiles`); }
export async function createApiProfile(api_id, api_hash, name){
  return jget(`${base}/apiprofile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_id, api_hash, name }),
  });
}
export async function renameApiProfile(id, name){
  return jget(`${base}/apiprofile/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}
export async function deleteApiProfile(id){
  return jget(`${base}/apiprofile/${id}`, { method: "DELETE" });
}

// LOGIN FLOW
export async function sendCode(api_profile_id, phone){
  return jget(`${base}/auth/send_code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_profile_id, phone }),
  });
}
export async function confirmCode(login_id, code){
  return jget(`${base}/auth/confirm_code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login_id, code }),
  });
}
export async function confirmPassword(login_id, password){
  return jget(`${base}/auth/confirm_password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login_id, password }),
  });
}
export async function cancelLogin(login_id){
  return jget(`${base}/auth/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login_id }),
  });
}
