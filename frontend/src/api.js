const API = '/api';
export function token(){return localStorage.getItem('placement_token')||''}
export function saveSession(data){localStorage.setItem('placement_token',data.token);localStorage.setItem('placement_user',JSON.stringify(data.user))}
export function clearSession(){localStorage.removeItem('placement_token');localStorage.removeItem('placement_user')}
export async function api(path,options={}){const headers={...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(token()?{Authorization:`Bearer ${token()}`}:{}) ,...options.headers};const res=await fetch(`${API}${path}`,{...options,headers});const data=await res.json().catch(()=>({}));if(!res.ok){if(res.status===401&&token())clearSession();throw Error(data.error||'Request failed.')}return data}
