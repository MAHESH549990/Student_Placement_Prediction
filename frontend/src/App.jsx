import React,{useEffect,useState} from 'react';
import {api,clearSession,token} from './api';
import AppLayout from './components/AppLayout';
import AuthPage from './pages/AuthPage';
import AdminDashboard from './pages/AdminDashboard';
import {StudentDashboard} from './pages/StudentDashboard';
import PlacementCheck from './pages/PlacementCheck';
import CareerPlan from './pages/CareerPlan';

export default function App(){const [user,setUser]=useState(null),[checking,setChecking]=useState(true),[page,setPage]=useState(''),[refresh,setRefresh]=useState(0);useEffect(()=>{if(!token()){setChecking(false);return}api('/auth/me').then(d=>setUser(d.user)).catch(()=>clearSession()).finally(()=>setChecking(false))},[]);useEffect(()=>{if(user)setPage(user.role==='admin'?'Overview':'My dashboard')},[user]);function logout(){clearSession();setUser(null);setPage('')}if(checking)return <div className="loading-screen"><div className="loading-mark">G</div><span>Preparing your workspace…</span></div>;if(!user)return <AuthPage onAuth={setUser}/>;const admin=user.role==='admin';return <AppLayout user={user} page={page} setPage={setPage} onLogout={logout}>{admin?<AdminDashboard page={page} setPage={setPage}/>:page==='Placement check'?<PlacementCheck setPage={setPage} onSaved={()=>setRefresh(n=>n+1)}/>:page==='Career plan'?<CareerPlan setPage={setPage}/>:<StudentDashboard key={refresh} user={user} setPage={setPage}/>}</AppLayout>}
