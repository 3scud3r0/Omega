import base64,hashlib
from .worker import invoke
from omega_platform.budget import Budget
def extract(document,kind,*,budget=Budget()):
    if len(document.content)>8*1024**2:raise ValueError('Document byte budget exceeded')
    result=invoke('document_worker',{'kind':kind,'data':base64.b64encode(document.content).decode()},budget=budget)
    if type(result) is not dict or type(result.get('pages')) is not list:raise ValueError('Document worker protocol mismatch')
    return {'source':document.source,'observed_at':document.observed_at,'sha256':document.digest,'pages':result['pages'],'authority':False}
