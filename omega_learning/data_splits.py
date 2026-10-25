import hashlib,json
class DataSplits:
    def __init__(self,train,validation,heldout):
        self.splits={'train':tuple(train),'validation':tuple(validation),'heldout':tuple(heldout)};ids=set();digests=set()
        for name,rows in self.splits.items():
            for row in rows:
                if 'id' not in row or 'input' not in row:raise ValueError('Dataset identity/input required')
                digest=hashlib.sha256(json.dumps(row['input'],sort_keys=True,allow_nan=False).encode()).hexdigest()
                if row['id'] in ids or digest in digests:raise ValueError('Dataset split contamination')
                ids.add(row['id']);digests.add(digest)
    def get(self,split):return tuple(json.loads(json.dumps(r)) for r in self.splits[split])
