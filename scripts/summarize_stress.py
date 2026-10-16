"""Paired fallback comparison from saved forecasts; no inference or tuning."""
from collections import defaultdict
import csv
import gzip
import json
import stress_telemetry as s


def main():
    accum=defaultdict(lambda:[0,0.,0.])
    with gzip.open(s.OUT/'forecasts.csv.gz','rt',newline='') as f:
        for row in csv.DictReader(f):
            if row['operational_point_pct']=='':continue
            key=(row['scenario'],row['role'],row['technology'],int(row['horizon_minutes']))
            y=float(row['actual_pct'])
            z=accum[key];z[0]+=1
            z[1]+=abs(float(row['unrestricted_point_pct'])-y)
            z[2]+=abs(float(row['operational_point_pct'])-y)
    result=[dict(zip(('scenario','role','technology','horizon_minutes'),k))|
            {'common_point_rows':v[0],'unrestricted_mae_pp_same_rows':v[1]/v[0],
             'fallback_mae_pp_same_rows':v[2]/v[0]} for k,v in sorted(accum.items())]
    s.r.b.dump(s.OUT/'paired_fallback.json',result)
    for row in result:
        if row['scenario']=='synthetic_drop10' and row['role']=='development' and row['technology']=='LTE' and row['horizon_minutes']==15:
            print(row)


if __name__=='__main__':main()
