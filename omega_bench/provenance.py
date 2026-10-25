import hashlib,json,platform,sys
from pathlib import Path
def record(dataset,model,seed,configuration):
    def digest(path):
        h=hashlib.sha256()
        with Path(path).open('rb') as stream:
            while block:=stream.read(65536):h.update(block)
        return h.hexdigest()
    payload={'dataset_sha256':digest(dataset),'model_sha256':digest(model),'seed':seed,'configuration':configuration,
             'python':sys.version.split()[0],'platform':platform.platform()}
    payload['experiment_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return payload
