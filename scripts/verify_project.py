"""Verify included artifacts and installed versions without training or changing them."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def verify():
    checks=[]
    def check(relative,expected):
        path=ROOT/relative
        if not path.is_file() or digest(path)!=expected:
            raise RuntimeError(f'Missing or changed artifact: {relative}')
        checks.append(str(relative).replace('\\','/'))
    cohort=json.loads((ROOT/'data/processed/manifest_v1.json').read_text())
    check('data/raw/Dataset_02.zip',cohort['archive_sha256'])
    check('data/processed/observed_v1.sqlite',cohort['database_sha256'])
    summary=json.loads((ROOT/'data/processed/supervised_v1/summary.json').read_text())
    for name,expected in summary['files'].items():check(Path('data/processed/supervised_v1')/name,expected)
    for manifest in sorted(ROOT.glob('outputs/*/run_manifest.json')):
        payload=json.loads(manifest.read_text())
        for name,expected in payload.get('artifacts_sha256',{}).items():
            check(manifest.parent.relative_to(ROOT)/name,expected)
    for name in ('api_v1','dashboard_v1'):
        path=ROOT/'outputs'/name/'validation.json'
        if not path.exists():raise RuntimeError(f'Missing evidence: {path}')
    packages={}
    for line in (ROOT/'requirements-ml-lock.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):continue
        name,expected=line.split('==');actual=version(name)
        if actual!=expected:raise RuntimeError(f'{name}: expected {expected}, found {actual}')
        packages[name]=actual
    # Validate that the saved models and their metadata can still be loaded.
    sys.path.insert(0,str(ROOT))
    from networkprb.inference import ForecastEngine
    engine=ForecastEngine(ROOT)
    result=engine.predict(engine.example())
    if result['status']!='fresh_model' or len(result['forecasts'])!=3:
        raise RuntimeError('Saved model smoke check failed')
    return {'status':'passed','python':platform.python_version(),'platform':platform.platform(),
            'artifact_hash_checks':len(checks),'checked_files':checks,'packages':packages,
            'forecast_groups_loaded':len(engine.models),'cohort_series':len(engine.series),
            'scope':'File integrity, installed package versions and saved-model smoke check; no training, full audit or clean-machine installation.'}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',type=Path,help='Optional new JSON report path; never overwrites an existing report')
    args=parser.parse_args()
    if args.record and args.record.exists():raise SystemExit('Report exists; preserve it and choose a new path.')
    report=verify()
    if args.record:
        args.record.parent.mkdir(parents=True,exist_ok=True)
        args.record.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='checked_files'},indent=2))
