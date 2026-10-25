"""Maturity is derived from recorded states and measured outcomes, never LOC."""
import json
from pathlib import Path
def summarize(progress,measurements):
    tasks=progress['tasks'];statuses={}
    for task in tasks:statuses[task['status']]=statuses.get(task['status'],0)+1
    accepted=sum(t['status']=='accepted' for t in tasks)
    return {'tasks':len(tasks),'accepted':accepted,'accepted_fraction':accepted/len(tasks) if tasks else 0,
            'states':statuses,'measurements':measurements,'line_count_is_acceptance':False}
def render(summary):
    lines=['Omega maturity',f"Accepted: {summary['accepted']}/{summary['tasks']}"]
    lines.extend(f'{key}: {value}' for key,value in sorted(summary['states'].items()))
    lines.append(json.dumps(summary['measurements'],sort_keys=True,ensure_ascii=False,allow_nan=False))
    return '\n'.join(lines)
