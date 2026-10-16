from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import zipfile,io,csv,collections,json,hashlib
out={}
with zipfile.ZipFile(str(PROJECT_ROOT / 'data/raw/Dataset_02.zip')) as z:
 for f in z.namelist():
  if not f.endswith('.csv'):continue
  signatures={}; rowhashes=set();conflicting=set();counts=collections.Counter();samples={};duplicate_rows=0;conflicting_encounters=0
  with z.open(f) as raw:
   rr=csv.reader(io.TextIOWrapper(raw));cols=next(rr)
   for row in rr:
    key=tuple(row[:3]); sig=hashlib.blake2b(repr(row[3:]).encode(),digest_size=12).digest(); fullsig=hashlib.blake2b(repr(row).encode(),digest_size=12).digest();rowhashes.add(fullsig); counts[key]+=1
    if key in signatures:
     duplicate_rows+=1
     if signatures[key]!=sig:
      conflicting.add(key);conflicting_encounters+=1
      if len(samples)<5:samples[key]=[]
    else:signatures[key]=sig
  if samples:
   with z.open(f) as raw:
    rr=csv.reader(io.TextIOWrapper(raw));next(rr)
    for row in rr:
     if tuple(row[:3]) in samples and len(samples[tuple(row[:3])])<10:samples[tuple(row[:3])].append(row)
  d={'file':f,'unique_keys':len(counts),'duplicate_key_extra_rows':duplicate_rows,'unique_complete_rows':len(rowhashes),'duplicate_full_rows':sum(counts.values())-len(rowhashes),'keys_with_multiple_rows':sum(c>1 for c in counts.values()),'conflicting_keys':len(conflicting),'conflicting_encounters_vs_first':conflicting_encounters,'key_multiplicity':dict(collections.Counter(counts.values())),'conflict_samples':[{'key':k,'rows':v} for k,v in samples.items()],'columns':cols}
  print(json.dumps(d,indent=2),flush=True);out[f]=d
  del counts,signatures,rowhashes,conflicting,samples
with open(str(PROJECT_ROOT / 'audit/dataset_02_duplicates.json'),'w') as f:json.dump(out,f,indent=2)
