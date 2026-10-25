import json,re
from pathlib import Path
from omega_platform.sandbox import run,trusted
from omega_platform.budget import BUILD_BUDGET
def inspect(repository,operation,*,capability,verifier,principal):
    repository=Path(repository).resolve(strict=True);verifier.require(capability,principal,'git.read',path=repository)
    commands={'status':['status','--porcelain'],'diff':['diff','--no-ext-diff','--no-textconv'],
              'log':['log','-20','--format=%H %s']}
    if operation not in commands:raise PermissionError('Read-only Git operation required')
    return run(['/usr/bin/git','--no-pager','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-C',repository,*commands[operation]],
               readonly=[repository,'/usr/bin','/bin'],budget=BUILD_BUDGET,check=True).stdout
def ci_runs(repository,*,capability,verifier,principal):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',repository):raise ValueError('Invalid GitHub repository')
    verifier.require(capability,principal,'github.ci.read')
    result=trusted(['gh','run','list','--repo',repository,'--limit','20','--json','databaseId,headSha,status,conclusion'],budget=BUILD_BUDGET,check=True)
    return json.loads(result.stdout)
