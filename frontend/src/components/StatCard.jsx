import React from 'react';
export default function StatCard({label,value,detail,icon:Icon,tone='green'}){return <article className="stat-card"><div className="stat-label">{label}<span className={`stat-icon ${tone}`}><Icon size={18}/></span></div><strong>{value}</strong><small>{detail}</small></article>}
