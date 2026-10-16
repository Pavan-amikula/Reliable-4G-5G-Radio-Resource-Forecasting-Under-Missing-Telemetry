from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import zipfile,csv,io,collections,json
out={}
with zipfile.ZipFile(str(PROJECT_ROOT / 'data/raw/Dataset_02.zip')) as z:
 for f in z.namelist():
  if not f.endswith('.csv'):continue
  counters=collections.Counter();valid_vals={};n=0;conflict=0;radio_different=0;seen={}
  with z.open(f) as raw:
   rr=csv.DictReader(io.TextIOWrapper(raw));target=[c for c in rr.fieldnames if c.endswith('RB utilization')][0]
   for r in rr:
    k=(r['Base station'],r['Sector'],r['Timestamp'])
    if r[target]:
     n+=1;counters[k]+=1
     if k in valid_vals and valid_vals[k]!=r[target]:conflict+=1
     valid_vals[k]=r[target]
  d={'target':target,'valid_rows':n,'unique_valid_keys':len(counters),'keys_with_multiple_valid_rows':sum(c>1 for c in counters.values()),'valid_conflict_encounters':conflict,'max_valid_multiplicity':max(counters.values()),'sites_with_target':len(set(k[0] for k in counters)),'station_sector_with_target':len(set(k[:2] for k in counters))}
  print(json.dumps(d),flush=True);out[f]=d
with open(str(PROJECT_ROOT / 'audit/dataset_02_valid_keys.json'),'w') as f:json.dump(out,f,indent=2)
