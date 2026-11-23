/* WHOOP Insights v2. No external JavaScript, analytics or requests except this app. */
'use strict';
const $=id=>document.getElementById(id);
const qsa=s=>[...document.querySelectorAll(s)];
const state={days:30,tab:(location.hash||'#overview').slice(1),demo:new URLSearchParams(location.search).get('demo')==='1',connected:false,data:null,loading:false,sport:'all',metric:'recovery',predictor:'workout_strain'};
const number=(n,d=1)=>n==null?'—':Number(n).toLocaleString('de-DE',{maximumFractionDigits:d});
const dateLabel=d=>d?new Date(d+'T12:00:00').toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'}):'—';
const duration=h=>h==null?'—':`${Math.floor(h)}:${String(Math.round((h%1)*60)).padStart(2,'0')} h`;
const clock=h=>h==null?'—':`${String(Math.floor(h)%24).padStart(2,'0')}:${String(Math.round((h%1)*60)).padStart(2,'0')} Uhr`;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const metricNames={recovery:'Recovery am Morgen',sleep_hours:'Schlafdauer',deep_hours:'Tiefschlaf',performance:'Schlafperformance',hrv:'HRV am Morgen'};
const units={recovery:'Punkte',sleep_hours:'h',deep_hours:'h',performance:'%',hrv:'ms'};
const predictorNames={workout_strain:'Workout-Strain',total_minutes:'Trainingsdauer (min)',hours_before_sleep:'Abstand zum Schlafbeginn (h)'};
const show=(id,on)=>{const el=$(id);if(el)el.hidden=!on};
function notice(s){$('errorAlert').textContent=s;show('errorAlert',!!s)}
function setStatus(t,label){$('connectionPill').className='status-pill '+t;$('connectionPill').innerHTML='<span class="status-led"></span> '+esc(label)}
function tile(label,value,desc,accent=''){return `<article class="metric-card ${accent}"><div class="metric-title">${esc(label)}</div><div class="metric-value">${value}</div><div class="metric-foot">${esc(desc)}</div></article>`}
function cardValue(v,unit='',dec=1){return v==null?'—':`${number(v,dec)}${unit?` <span class="metric-unit">${esc(unit)}</span>`:''}`}
function seriesChart(id,rows,key,opts={}){
  const el=$(id);if(!el)return;
  const valid=rows.map((r,i)=>({i,v:r[key],date:r.date})).filter(r=>r.v!==null&&r.v!==undefined&&Number.isFinite(+r.v));
  if(!valid.length){el.innerHTML='<div class="no-data">Für diesen Zeitraum liegen keine Messwerte vor.</div>';return}
  const w=720,h=230,p={t:20,r:24,b:39,l:48},pw=w-p.l-p.r,ph=h-p.t-p.b;
  let lo=opts.min??Math.floor(Math.min(...valid.map(r=>+r.v))*.94),hi=opts.max??Math.ceil(Math.max(...valid.map(r=>+r.v))*1.06);
  if(lo===hi)hi=lo+1;
  const X=i=>p.l+(rows.length>1?i/(rows.length-1):.5)*pw,Y=v=>p.t+(1-(v-lo)/(hi-lo))*ph;
  let html=`<svg role="img" aria-label="${esc(opts.title||key)} Verlauf" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">`;
  for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4,y=Y(v);html+=`<line class="grid-line" x1="${p.l}" x2="${w-p.r}" y1="${y}" y2="${y}"/><text class="axis-label" x="${p.l-10}" y="${y+4}" text-anchor="end">${number(v,opts.digits??0)}</text>`}
  const n=rows.length;const tick=[0,Math.floor((n-1)/4),Math.floor((n-1)/2),Math.floor((n-1)*3/4),n-1];
  [...new Set(tick)].forEach(i=>html+=`<text class="axis-label" x="${X(i)}" y="${h-8}" text-anchor="middle">${dateLabel(rows[i].date)}</text>`);
  const groups=[];let current=[];
  for(const v of rows.map((r,i)=>({i,v:r[key]}))){if(v.v===null||v.v===undefined){if(current.length)groups.push(current);current=[]}else current.push(v)}if(current.length)groups.push(current);
  const color=opts.color||'#b8f56d';const grad='grad-'+id;
  html+=`<defs><linearGradient id="${grad}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".22"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`;
  for(const g of groups){if(g.length<2)continue;const line=g.map((z,i)=>(i?'L':'M')+X(z.i).toFixed(1)+' '+Y(z.v).toFixed(1)).join(' ');html+=`<path d="${line} L${X(g[g.length-1].i)} ${p.t+ph} L${X(g[0].i)} ${p.t+ph} Z" fill="url(#${grad})"/><path d="${line}" stroke="${color}" stroke-width="2.7" fill="none"/>`}
  const step=Math.ceil(valid.length/45);
  valid.forEach((z,i)=>{if(i%step!==0&&i!==valid.length-1)return;html+=`<circle cx="${X(z.i)}" cy="${Y(z.v)}" r="3.6" fill="${color}"><title>${dateLabel(z.date)} · ${number(z.v,1)} ${opts.unit||''}</title></circle>`});
  el.innerHTML=html+'</svg>';
}
function overview(d){
 const s=d.summary;
 const defs=[['Recovery',s.recovery,'%','Tage mit Messwerten'],['HRV',s.hrv,'ms','Herzratenvariabilität'],['Ruhepuls',s.rhr,'bpm','Nächtlicher Ruhepuls'],['Schlafdauer',s.sleep_hours,'h','Pro Hauptschlaf']];
 $('metricGrid').innerHTML=defs.map(([l,m,u,sub])=>tile(l,m.value==null?'—':u==='h'?duration(m.value):cardValue(m.value,u,u==='ms'||u==='bpm'?0:1),`${m.count} Messtage · ${sub}`)).join('');
 seriesChart('recoveryPlot',d.rows,'recovery',{min:0,max:100,unit:'%',title:'Recovery'});
 seriesChart('hrvPlot',d.rows,'hrv',{color:'#72d9bd',unit:'ms',title:'HRV'});
 $('insightList').innerHTML=d.insights.length?d.insights.map(x=>`<div class="insight-row"><span class="insight-point">↗</span><p>${esc(x.text)}</p></div>`).join(''):'<div class="insight-row"><span class="insight-point">·</span><p>Aktuell gibt es noch keine hinreichend belegten Unterschiede zwischen den vergangenen zwei Wochen.</p></div>';
 $('recentRows').innerHTML=d.rows.slice(-7).reverse().map(r=>`<tr><td>${dateLabel(r.date)}</td><td>${cardValue(r.recovery,'%')}</td><td>${cardValue(r.hrv,'ms')}</td><td>${duration(r.sleep_hours)}</td></tr>`).join('');
}
function sleep(d){
 const s=d.summary;
 $('sleepMetrics').innerHTML=[tile('Ø Schlafdauer',duration(s.sleep_hours.value),`${s.sleep_hours.count} Nächte`),tile('Ø Schlafperformance',cardValue(s.performance.value,'%'),`${s.performance.count} Nächte`),tile('Ø Schlafeffizienz',cardValue(s.efficiency.value,'%'),`${s.efficiency.count} Nächte`)].join('');
 seriesChart('sleepDetailPlot',d.rows,'sleep_hours',{color:'#91aef6',unit:'h',digits:1,title:'Schlafdauer'});
 seriesChart('performancePlot',d.rows,'performance',{min:0,max:100,color:'#b8f56d',unit:'%',title:'Schlafperformance'});
 seriesChart('bedtimePlot',d.rows,'bedtime',{color:'#e6b181',digits:1,title:'Einschlafzeit'});
 const stages=[['Leichtschlaf',d.stages.light,'#78a8f0'],['Tiefschlaf',d.stages.deep,'#b8f56d'],['REM',d.stages.rem,'#ac8df0']];
 const total=stages.reduce((v,x)=>v+(x[1]||0),0);
 $('stagesPlot').innerHTML=total?`<div class="sleep-stage-bar">${stages.map(x=>`<span title="${esc(x[0])}: ${duration(x[1])}" style="width:${100*(x[1]||0)/total}%;background:${x[2]}"></span>`).join('')}</div><div class="stage-legend">${stages.map(x=>`<div class="stage-legend-item"><span class="stage-color" style="background:${x[2]}"></span>${x[0]} <b>${duration(x[1])}</b></div>`).join('')}</div>`:'<div class="no-data">Keine Schlafphasen vorhanden.</div>';
 $('sleepRows').innerHTML=d.rows.filter(x=>x.sleep_hours!==null).slice(-10).reverse().map(r=>`<tr><td>${dateLabel(r.date)}</td><td>${duration(r.sleep_hours)}</td><td>${cardValue(r.performance,'%')}</td><td>${cardValue(r.efficiency,'%')}</td><td>${clock(r.bedtime)}</td></tr>`).join('')||'<tr><td colspan="5">Keine bewerteten Hauptschlafphasen</td></tr>';
}
function horizontalBars(id,items,unit){const el=$(id);if(!items.length){el.innerHTML='<div class="no-data">Keine Daten verfügbar.</div>';return}const max=Math.max(1,...items.map(x=>x.value));el.innerHTML=items.map((x,i)=>`<div class="horizontal-bar-row"><div class="bar-titles"><span>${esc(x.name)}</span><strong>${number(x.value,0)} ${unit}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${100*x.value/max}%;background:${['#b8f56d','#72d9bd','#91aef6','#ac8df0','#e6b181','#e6a7a1'][i%6]}"></div></div></div>`).join('')}
function training(d){
 const w=d.workouts;
 const mins=d.workout_minutes;
 $('trainingMetrics').innerHTML=[tile('Trainingseinheiten',String(d.workout_count),`Im gewählten Zeitraum`),tile('Gesamtdauer',duration(mins/60),'Sportlich erfasste Zeit'),tile('Ø Workout-Strain',cardValue(d.workout_count?mean(w.filter(x=>x.strain!==null).map(x=>x.strain)):null,''),'Nur bewertete Workouts')].join('');
 horizontalBars('activityBreakdown',d.activities.slice(0,7).map(x=>({name:x.sport,value:x.minutes})),'min');
 horizontalBars('zonesPlot',d.zones.map((x,i)=>({name:'Zone '+i,value:x})).filter(x=>x.value>0),'min');
 $('workoutCountTag').textContent=`${d.workout_count} WORKOUTS`;
 $('workoutList').innerHTML=w.length?w.slice(0,35).map(x=>`<div class="workout-row"><span class="workout-mark">⌁</span><span class="workout-label">${esc(x.sport)}<small>${dateLabel(x.date)} · ${number(x.minutes,0)} min · Ø HF ${cardValue(x.avg_hr,'bpm',0)}</small></span><span class="workout-score">${cardValue(x.strain)} <small>Strain</small></span></div>`).join(''):'<div class="no-data">Im ausgewählten Zeitraum wurden keine Workouts geliefert.</div>';
}
function mean(arr){const v=arr.filter(x=>x!==null&&x!==undefined&&Number.isFinite(+x));return v.length?v.reduce((a,b)=>a+Number(b),0)/v.length:null}
function pearson(xs){if(xs.length<8)return null;const mx=mean(xs.map(x=>x[0])),my=mean(xs.map(x=>x[1]));const a=xs.reduce((s,p)=>s+(p[0]-mx)*(p[1]-my),0);const b=xs.reduce((s,p)=>s+(p[0]-mx)**2,0);const c=xs.reduce((s,p)=>s+(p[1]-my)**2,0);return b>0&&c>0?a/Math.sqrt(b*c):null}
function scatter(id,items,xKey,yKey){const el=$(id);if(items.length<2){el.innerHTML='<div class="no-data">Noch zu wenige vollständige Messpaare für eine Grafik.</div>';return}
 const w=720,h=230,p={l:52,r:28,t:19,b:40},xv=items.map(x=>x[xKey]),yv=items.map(x=>x[yKey]);let xmin=Math.min(...xv),xmax=Math.max(...xv),ymin=Math.min(...yv),ymax=Math.max(...yv);
 if(xmin===xmax)xmax=xmin+1;if(ymin===ymax)ymax=ymin+1;
 const X=x=>p.l+(x-xmin)/(xmax-xmin)*(w-p.l-p.r),Y=y=>h-p.b-(y-ymin)/(ymax-ymin)*(h-p.t-p.b);
 let svg=`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="${esc(predictorNames[xKey])} und ${esc(metricNames[yKey])}">`;
 for(let i=0;i<5;i++){const y=p.t+i*(h-p.t-p.b)/4;const val=ymax-(ymax-ymin)*i/4;svg+=`<line x1="${p.l}" y1="${y}" x2="${w-p.r}" y2="${y}" class="grid-line"/><text class="axis-label" text-anchor="end" x="${p.l-10}" y="${y+4}">${number(val,1)}</text>`}
 for(let i=0;i<5;i++){const val=xmin+(xmax-xmin)*i/4;svg+=`<text class="axis-label" text-anchor="middle" x="${p.l+(w-p.l-p.r)*i/4}" y="${h-8}">${number(val,1)}</text>`}
 items.forEach(q=>{svg+=`<circle cx="${X(q[xKey])}" cy="${Y(q[yKey])}" r="5.2" fill="#72d9bd" fill-opacity=".78" stroke="#b8f56d" stroke-width=".65"><title>${dateLabel(q.date)} · ${predictorNames[xKey]} ${number(q[xKey])} · ${metricNames[yKey]} ${number(q[yKey])} ${units[yKey]}</title></circle>`});
 svg+='</svg>';el.innerHTML=svg;
}
function connections(d){
 const all=d.connections.pairs||[],available=d.connections.available;
 show('connectionMissing',!available);
 if(!available)$('connectionMissing').textContent='WHOOP liefert derzeit keine Workout-Daten. Damit können Trainingseinheiten nicht zuverlässig zugeordnet werden. Korrelationen und Training-vs.-Ruhetag-Vergleiche sind deaktiviert, bis der Workout-Abruf wieder funktioniert.';
 const activities=[...new Set(all.filter(p=>p.sport).map(p=>p.sport))].sort();
 const select=$('sportFilter');const before=select.value||state.sport;
 select.innerHTML='<option value="all">Alle Sportarten</option>'+activities.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
 if(activities.includes(before))select.value=before;else select.value='all';state.sport=select.value;
 if(!available){$('analysisMetrics').innerHTML=tile('Messpaare','—','Keine Workout-Daten')+tile('Korrelation','—','Keine belastbare Aussage')+tile('Vergleich','—','Nicht verfügbar');$('scatterPlot').innerHTML='<div class="no-data">Workout-Daten fehlen.</div>';$('comparisonPlot').innerHTML='<div class="no-data">Workout-Daten fehlen.</div>';$('pairedRows').innerHTML='<tr><td colspan="5">Keine sichere Zuordnung möglich</td></tr>';return}
 const train=all.filter(p=>p.workout_count>0&&(state.sport==='all'||p.sport===state.sport));
 const rest=all.filter(p=>p.workout_count===0);
 const metric=state.metric,predictor=state.predictor;
 const complete=train.filter(p=>p[predictor]!==null&&p[metric]!==null);
 const r=pearson(complete.map(p=>[p[predictor],p[metric]]));
 const a=train.map(p=>p[metric]).filter(x=>x!==null),b=rest.map(p=>p[metric]).filter(x=>x!==null);
 const av=mean(a),bv=mean(b),difference=av!==null&&bv!==null?av-bv:null;
 $('analysisMetrics').innerHTML=tile('Nächte nach Training',String(train.length),`${complete.length} vollständige Messpaare`)+tile('Korrelationskoeffizient',r===null?'—':number(r,2),r===null?`Mindestens 8 vollständige Paare nötig (aktuell ${complete.length})`:`Explorativ · ${complete.length} vollständige Paare`)+tile('Training minus Ruhe',difference===null||a.length<4||b.length<4?'—':`${difference>0?'+':''}${number(difference,1)} <span class="metric-unit">${units[metric]}</span>`,`${a.length} Trainingsnächte / ${b.length} ruhige Nächte`);
 $('scatterTitle').textContent=`${predictorNames[predictor]} vs. ${metricNames[metric]}`;
 $('comparisonTitle').textContent=`Ø ${metricNames[metric]} im Vergleich`;
 scatter('scatterPlot',complete,predictor,metric);
 $('correlationCaption').textContent=r===null?`Keine Korrelationszahl: ${complete.length} statt mindestens 8 vollständiger Messpaare. Die einzelnen Punkte sind dennoch sichtbar.`:`Pearson r = ${number(r,2)} · n = ${complete.length}. Beobachteter linearer Zusammenhang, keine Ursache-Wirkung-Aussage.`;
 const vals=[{name:state.sport==='all'?'Nach Workout':`Nach ${state.sport}`,val:av,n:a.length},{name:'Ohne Workout (24 h)',val:bv,n:b.length}];
 const max=Math.max(1,...vals.map(x=>x.val||0));
 $('comparisonPlot').innerHTML=vals.map((x,i)=>`<div class="comparison-row"><div class="bar-titles"><span>${esc(x.name)}</span><strong>${x.val===null?'—':number(x.val,1)+' '+units[metric]} <small>(n=${x.n})</small></strong></div><div class="bar-track comparison"><div class="bar-fill" style="width:${100*(x.val||0)/max}%;background:${i?'#91aef6':'#b8f56d'}"></div></div></div>`).join('')+(a.length<4||b.length<4?'<p class="chart-footer">Kleine Gruppen: Unterschiede nicht interpretieren.</p>':'');
 $('pairedRows').innerHTML=train.slice(-18).reverse().map(p=>`<tr><td>${dateLabel(p.date)}</td><td>${esc(p.sport||'—')}${p.workout_count>1?` (${p.workout_count} Workouts)`:''}</td><td>${cardValue(p.workout_strain,'',1)}</td><td>${duration(p.sleep_hours)}</td><td>${cardValue(p.recovery,'%',0)}</td></tr>`).join('')||'<tr><td colspan="5">Keine zuordenbaren Workouts im Zeitraum</td></tr>';
}
function render(d){overview(d);sleep(d);training(d);connections(d);$('rangeCaption').textContent=`${dateLabel(d.from)} – ${dateLabel(d.to)} · ${d.data_points} Tage mit Recovery-Werten`;show('demoAlert',d.demo);if(d.warnings?.length)notice('Einige WHOOP-Datenbereiche sind aktuell nicht verfügbar: '+d.warnings.join(', '));else notice('');$('lastUpdated').textContent=d.refreshed_at?'WHOOP aktualisiert: '+new Date(d.refreshed_at).toLocaleString('de-DE',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'Demodaten'}
function setTab(tab){if(!['overview','sleep','training','connections'].includes(tab))tab='overview';state.tab=tab;const title={overview:['Dein Tagesüberblick','COCKPIT'],sleep:['Dein Schlaflabor','SCHLAF'],training:['Deine Trainingsanalyse','TRAINING'],connections:['Training & Regeneration','ZUSAMMENHÄNGE']};$('pageTitle').textContent=title[tab][0];$('sectionEyebrow').textContent=title[tab][1];$('breadcrumb').textContent=title[tab][1];qsa('[data-tab]').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));for(const k of Object.keys(title))show(k+'Tab',k===tab)}
async function load(force=false){if(state.loading)return;state.loading=true;show('loading',true);if(!state.data)show('dashboard',false);notice('');try{const params=new URLSearchParams({days:String(state.days)});if(state.demo)params.set('demo','1');if(force)params.set('force','1');const response=await fetch('/api/dashboard?'+params,{cache:'no-store',credentials:'same-origin'});const data=await response.json();if(!response.ok){if(response.status===401){state.connected=false;show('connectPanel',true);show('dashboard',false);setStatus('','Nicht verbunden')}throw Error(data.error||'WHOOP-Daten konnten nicht abgerufen werden.')}state.data=data;show('dashboard',true);show('connectPanel',false);setStatus(data.demo?'demo':'connected',data.demo?'Beispieldaten':'WHOOP verbunden');render(data);setTab(state.tab)}catch(e){notice(e.message||'Abruf fehlgeschlagen')}finally{show('loading',false);state.loading=false}}
async function init(){let status={connected:false,configured:false};try{status=await fetch('/api/status',{credentials:'same-origin'}).then(r=>r.json())}catch{}state.connected=status.connected;show('logoutSide',status.connected);$('setupHint').hidden=status.configured;$('connectBtn').hidden=!status.configured;show('connectPanel',!state.connected&&!state.demo);if(new URLSearchParams(location.search).has('error'))notice('WHOOP-Anmeldung fehlgeschlagen. Bitte erneut verbinden.');if(state.demo||state.connected)load();else setStatus('','Nicht verbunden');qsa('[data-days]').forEach(x=>x.addEventListener('click',()=>{state.days=Number(x.dataset.days);qsa('[data-days]').forEach(b=>b.classList.toggle('selected',x===b));load()}));qsa('[data-tab]').forEach(x=>x.addEventListener('click',e=>{e.preventDefault();setTab(x.dataset.tab);history.replaceState(null,'','#'+x.dataset.tab);window.scrollTo({top:0,behavior:'smooth'})}));$('sportFilter').addEventListener('change',e=>{state.sport=e.target.value;if(state.data)connections(state.data)});$('predictorFilter').addEventListener('change',e=>{state.predictor=e.target.value;if(state.data)connections(state.data)});$('metricFilter').addEventListener('change',e=>{state.metric=e.target.value;if(state.data)connections(state.data)});$('demoBtn').addEventListener('click',()=>{state.demo=true;history.replaceState(null,'','/?demo=1');load()});$('refreshBtn').addEventListener('click',()=>{if(state.demo||state.connected)load(true)});$('logoutSide').addEventListener('click',async()=>{if(!confirm('WHOOP-Verbindung wirklich trennen?'))return;await fetch('/auth/disconnect',{method:'POST',credentials:'same-origin'});location.href='/'});setTab(state.tab);setInterval(()=>{if(state.connected&&!state.demo&&document.visibilityState==='visible'&&!state.loading)load()},300000)}
init();
