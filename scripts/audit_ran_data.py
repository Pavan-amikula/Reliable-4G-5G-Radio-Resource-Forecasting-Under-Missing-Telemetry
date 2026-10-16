from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import zipfile,csv,io,json,datetime,collections,hashlib,os,time
p=str(PROJECT_ROOT / 'data/raw/Dataset_02.zip')
print('md5',hashlib.md5(open(p,'rb').read()).hexdigest(),flush=True)
res={}
with zipfile.ZipFile(p) as z:
 for f in z.namelist():
  if not f.endswith('.csv'):continue
  states={};tscache={};dates=set();rows=0;valid=0;missing=0;gt80=0;ge80=0;zeros=0;mx=0;mn=100;target_values=[];energy_missing=0;allmetrics_missing=0;allmetrics_missing_zero=0;missing_with_DL_positive=0;with_other_traffic=0
  with z.open(f) as raw:
   reader=csv.DictReader(io.TextIOWrapper(raw))
   cols=reader.fieldnames;target=[c for c in cols if c.endswith('RB utilization')][0];prefix=target.split()[0]
   metriccols=cols[3:]
   for r in reader:
    rows+=1
    tstr=r['Timestamp']; t=tscache.get(tstr)
    if t is None:
     t=int(datetime.datetime.fromisoformat(tstr).replace(tzinfo=datetime.timezone.utc).timestamp()/900);tscache[tstr]=t;dates.add(tstr[:10])
    key=(r['Base station'],r['Sector'])
    if key not in states:states[key]={'all':set(),'valid':set()}
    states[key]['all'].add(t)
    if not r['Radio unit energy consumption'] or not r['Baseband energy consumption']:energy_missing+=1
    if all(not r[c] for c in metriccols):allmetrics_missing+=1
    if all(not r[c] or float(r[c])==0 for c in metriccols):allmetrics_missing_zero+=1
    if r[target]:
     v=float(r[target]);valid+=1;target_values.append(v);mx=max(mx,v);mn=min(mn,v);gt80+=v>80;ge80+=v>=80;zeros+=v==0;states[key]['valid'].add(t)
    else:
     missing+=1
     if r[prefix+' data volume DL'] and float(r[prefix+' data volume DL'])>0:missing_with_DL_positive+=1
     if any(r[c] and float(r[c])>0 for c in [prefix+' data volume DL',prefix+' data volume UL',prefix+' active users DL',prefix+' active users UL']):with_other_traffic+=1
  target_values.sort()
  def stats(vals):
   vals=sorted(vals);return {'min':vals[0],'median':vals[len(vals)//2],'max':vals[-1]}
  details=[]
  for k,s in states.items():
   a=sorted(s['all']);v=sorted(s['valid']);longest=cur=0;last=None
   for t in v:
    cur=cur+1 if last is not None and t==last+1 else 1;longest=max(longest,cur);last=t
   details.append({'cell':k,'rows':len(a),'valid':len(v),'span_intervals':a[-1]-a[0]+1,'first':datetime.datetime.fromtimestamp(a[0]*900,datetime.timezone.utc).isoformat(),'last':datetime.datetime.fromtimestamp(a[-1]*900,datetime.timezone.utc).isoformat(),'longest_target_run':longest,'missing_clock_intervals':a[-1]-a[0]+1-len(a)})
  d={'archive_member':f,'rows':rows,'unique_rows_key':sum(len(s['all']) for s in states.values()),'stations':len(set(k[0] for k in states)),'station_sector':len(states),'first':min(tscache),'last':max(tscache),'distinct_dates':len(dates),'date_list':sorted(dates),'valid_target':valid,'missing_target':missing,'missing_fraction':missing/rows,'target_zero':zeros,'target_min':mn,'target_max':mx,'target_gt80':gt80,'target_ge80':ge80,'target_quantiles':{str(q):target_values[int(q*(valid-1))] for q in [0,.5,.9,.95,.99,.999,1]},'either_energy_missing':energy_missing,'all_metrics_missing':allmetrics_missing,'all_metrics_missing_or_zero':allmetrics_missing_zero,'missing_target_with_positive_DL_volume':missing_with_DL_positive,'missing_target_with_positive_traffic_or_active':with_other_traffic,'rows_per_cell':stats([d['rows'] for d in details]),'valid_per_cell':stats([d['valid'] for d in details]),'longest_target_run_per_cell':stats([d['longest_target_run'] for d in details]),'missing_clock_intervals_per_cell':stats([d['missing_clock_intervals'] for d in details]),'per_cell':details}
  res[prefix]=d
  print(json.dumps({k:v for k,v in d.items() if k not in ['per_cell','date_list']},indent=2),flush=True)
with open(str(PROJECT_ROOT / 'audit/dataset_02_audit.json'),'w') as f:json.dump(res,f,indent=2)
