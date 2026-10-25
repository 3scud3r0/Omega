import hashlib,json,time
class Lifecycle:
    def __init__(self):self.versions={};self.latest={}
    def add(self,key,content,expires=None):
        data=json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False)
        digest=hashlib.sha256(data.encode()).hexdigest()
        previous=self.latest.get(key)
        if previous and self.versions[previous]['sha256']==digest:return previous
        version=(key,len([v for v in self.versions if v[0]==key])+1)
        self.versions[version]={'data':json.loads(data),'sha256':digest,'expires':expires,'supersedes':previous};self.latest[key]=version
        return version
    def current(self,key,now=None):
        item=self.versions[self.latest[key]];now=time.time() if now is None else now
        if item['expires'] is not None and now>=item['expires']:raise PermissionError('Memory expired')
        return json.loads(json.dumps(item['data']))
    def obsolete(self):return tuple(version for version in self.versions if self.latest[version[0]]!=version)
