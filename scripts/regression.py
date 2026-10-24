"""Manifest-driven regression; exit 2 infrastructure, 1 failures, 0 success."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omega_platform.corpus import regression
p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();result=regression(Path(__file__).resolve().parents[1],a.manifest)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='results'}))
raise SystemExit(2 if result['infrastructure_failures'] else 0 if result['valid'] else 1)
