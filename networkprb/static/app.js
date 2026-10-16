'use strict';
const $=id=>document.getElementById(id);
let config,context,prediction,requestNumber=0,displayedHidden=0;
const fmt=v=>v==null?'Unavailable':`${v.toFixed(2)}%`;
const stamp=s=>new Date(s).getTime();
const localInput=s=>new Date(s).toISOString().slice(0,16);
const selectionKey=()=>JSON.stringify(['series','origin','scenario'].map(id=>$(id).value));
async function api(path,payload){const r=await fetch(path,{signal:AbortSignal.timeout(15000),...(payload?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:{})});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
async function update(){
 const n=++requestNumber,hidden=Number($('scenario').value),submittedSelection=selectionKey();$('error').hidden=true;$('update').disabled=true;$('update').textContent='Calculating…';
 $('request-status').textContent='Calculating forecasts for the selected sector and time…';
 try{
  const s=config.series[Number($('series').value)];const origin=new Date($('origin').value+'Z');
  if(!Number.isFinite(origin.getTime()))throw Error('Choose a valid UTC time.');
  const identity={technology:s.technology,band_mhz:s.band_mhz,station:s.station,sector:s.sector,origin_utc:origin.toISOString()};
  const c=await api('/replay/context',identity);
  const req=c.prediction_request;
  // Only history is submitted to the prediction API; later answers stay in display context.
  if(hidden)req.history=req.history.filter(v=>stamp(v.timestamp_utc)<=origin.getTime()-hidden*60000);
  const p=await api('/predict',req);
  if(n!==requestNumber)return;
  context=c;prediction=p;displayedHidden=hidden;render();
  $('request-status').textContent=`Forecast loaded · ${s.technology==='LTE'?'4G':'5G'} · ${s.station} · Sector ${s.sector} · ${p.origin_utc.slice(0,16).replace('T',' ')} UTC · ${hidden?`Latest ${hidden} minutes hidden`:'Original history'} · Request ${n}`;
  if(selectionKey()!==submittedSelection)$('request-status').textContent+=' · Selection changed. Click Show forecast to apply your new choices.';
 }catch(e){if(n===requestNumber){context=prediction=null;$('cards').replaceChildren();$('chart').replaceChildren();$('status').textContent='Unable to load';$('explanation').textContent='Adjust the selection and try again.';$('request-status').textContent='Forecast was not loaded. Check the message below and try again.';$('error').textContent=e.name==='TimeoutError'?'The local service took too long to respond. Try Show forecast again.':e.message;$('error').hidden=false;}}
 finally{if(n===requestNumber){$('update').disabled=false;$('update').textContent='Show forecast';}}
}
function render(){
 const p=prediction,c=context,hidden=displayedHidden,show=$('actuals').checked;
 $('status').textContent=p.status==='fresh_model'?'MODEL FORECAST':p.status==='stale_persistence'?'LAST READING REUSED':'NO ESTIMATE';
 $('explanation').textContent=(hidden?`Simulated missing readings: latest ${hidden} minutes hidden. `:'')+(p.status==='fresh_model'?(p.missing_inputs.length?'Current reading available; some past inputs are missing. Ranges may be less reliable.':'Current and required past inputs available.'):p.status==='stale_persistence'?`Latest available reading is ${p.age_minutes} minutes old. Reusing it; forecast ranges are withheld.`:'No reading within the last 60 minutes. The service withholds predictions.');
 $('role').textContent=c.role==='station_holdout'?'Station excluded from training':'Station represented in training';
 $('previous').disabled=stamp(p.origin_utc)<=stamp(config.origin_start_inclusive);
 $('next').disabled=stamp(p.origin_utc)+900000>=stamp(config.origin_end_exclusive);
 $('cards').replaceChildren(...p.forecasts.map(f=>{
  const actual=c.display_only_observations.find(v=>stamp(v.timestamp_utc)===stamp(f.target_utc))?.utilization_pct;
  const card=document.createElement('article');card.className='card';
  const title=document.createElement('h2');title.textContent=`In ${f.horizon_minutes} minutes · ${f.target_utc.slice(11,16)} UTC`;
  const value=document.createElement('div');value.className='value';value.textContent=fmt(f.predicted_utilization_pct);
  const range=document.createElement('div');range.className='range';range.textContent=f.range_lower_pct==null?'Range withheld':`Range ${fmt(f.range_lower_pct)} – ${fmt(f.range_upper_pct)}`;
  const comparison=document.createElement('div');comparison.className='comparison';comparison.textContent=!show?'Later actual hidden':actual==null?'Later actual: no recorded reading':`Later actual: ${fmt(actual)}`;
  if(show&&actual!=null&&f.predicted_utilization_pct!=null){const line=document.createElement('div');line.textContent=`Difference: ${Math.abs(actual-f.predicted_utilization_pct).toFixed(2)} percentage points`;comparison.append(line);}
  if(!f.target_within_evaluated_period){const note=document.createElement('div');note.textContent='Target is beyond the evaluated time period.';comparison.append(note);}
  card.append(title,value,range,comparison);return card;
 }));draw();
}
function draw(){
 const svg=$('chart');svg.replaceChildren();const NS='http://www.w3.org/2000/svg';
 const add=(tag,attrs,text)=>{const e=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!=null)e.textContent=text;svg.append(e);return e;};
 const o=stamp(prediction.origin_utc),x=t=>55+(t-(o-21600000))/25200000*905,y=v=>255-v*2.1;
 add('rect',{x:x(o),y:35,width:1000-x(o)-40,height:220,fill:'#edf6f2'});
 for(let v=0;v<=100;v+=25){add('line',{x1:55,x2:960,y1:y(v),y2:y(v),stroke:'#e4ebe6'});add('text',{x:42,y:y(v)+4,'text-anchor':'end'},v+'%');}
 for(let h=-6;h<=1;h++){const t=o+h*3600000;add('text',{x:x(t),y:283,'text-anchor':'middle'},new Date(t).toISOString().slice(11,16));}
 add('line',{x1:x(o),x2:x(o),y1:28,y2:258,stroke:'#76a99a','stroke-dasharray':'4 4'});
 add('text',{x:x(o)-8,y:19,'text-anchor':'end'},'Forecast issued here →');
 const rows=context.display_only_observations;let previous=null;
 for(const r of rows){const t=stamp(r.timestamp_utc),future=t>o;if(r.utilization_pct==null||(future&&!$('actuals').checked)){previous=null;continue;}const color=future?'#9c6850':'#29423b';
  if(previous)add('line',{x1:x(previous.t),y1:y(previous.v),x2:x(t),y2:y(r.utilization_pct),stroke:color,'stroke-width':2});
  add('circle',{cx:x(t),cy:y(r.utilization_pct),r:2.5,fill:color});previous={t,v:r.utilization_pct};
 }
 for(const f of prediction.forecasts){if(f.predicted_utilization_pct==null)continue;const xx=x(stamp(f.target_utc));if(f.range_lower_pct!=null){add('line',{x1:xx,x2:xx,y1:y(f.range_lower_pct),y2:y(f.range_upper_pct),stroke:'#087f76','stroke-width':8,'stroke-opacity':.25});}const point=add('circle',{cx:xx,cy:y(f.predicted_utilization_pct),r:5,fill:'#087f76',stroke:'white','stroke-width':2});const title=document.createElementNS(NS,'title');title.textContent=`${f.horizon_minutes} min: ${fmt(f.predicted_utilization_pct)}`;point.append(title);}
 add('text',{x:55,y:307},'Clock time (UTC) · missing observations stay blank');
}
$('update').addEventListener('click',update);
['series','scenario','origin'].forEach(id=>$(id).addEventListener('change',()=>{
 $('request-status').textContent='Selection changed. Click Show forecast to apply your choices. The cards still show the previous result.';
}));
$('actuals').addEventListener('change',()=>{if(prediction)render();});
for(const [id,delta] of [['previous',-900000],['next',900000]])$(id).addEventListener('click',()=>{$('origin').value=localInput(stamp($('origin').value+'Z')+delta);update();});
(async()=>{try{config=await api('/series');config.series.forEach((s,i)=>{const option=document.createElement('option');option.value=i;option.textContent=`${s.technology==='LTE'?'4G':'5G'} · ${s.station} · Sector ${s.sector}`;$('series').append(option);});$('series').value=config.series.findIndex(s=>s.technology==='LTE'&&s.station==='Site 16'&&s.sector==='1');$('origin').min=localInput(config.origin_start_inclusive);$('origin').max=localInput(stamp(config.origin_end_exclusive)-900000);$('origin').value=localInput(config.origin_start_inclusive);await update();}catch(e){$('error').hidden=false;$('error').textContent=e.message;}})();
