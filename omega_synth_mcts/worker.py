"""Fixed resource-bounded proposal worker; host verification is mandatory."""
import json
from pathlib import Path
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omega_synth_mcts.search import search


def main():
    path=Path(sys.argv[1])
    if path.stat().st_size>1024*1024:raise ValueError('Worker input budget exceeded')
    data=json.loads(path.read_text())
    result=search(data['spec'],verify=False,**data.get('limits',{}))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
