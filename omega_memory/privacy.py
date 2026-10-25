import time
class PrivacyPolicy:
    def __init__(self,authorize):self.authorize=authorize
    def require(self,record,purpose,principal,consent):
        if purpose not in {'retrieve','train','export'}:raise ValueError('Unknown memory purpose')
        if record.get('expires') is not None and time.time()>=record['expires']:raise PermissionError('Data retention expired')
        if record.get('sensitive',False) and self.authorize(record['owner'],principal,purpose,record['id'],consent) is not True:
            raise PermissionError('Sensitive data consent absent')
        if purpose in {'train','export'} and self.authorize(record['owner'],principal,purpose,record['id'],consent) is not True:
            raise PermissionError('Reuse permission absent')
        return True


class PrivateMemory:
    """Expose this facade to agents; keep raw database access in the host."""
    def __init__(self,store,policy,principal):self.store=store;self.policy=policy;self.principal=principal
    def get(self,id,*,purpose='retrieve',consent=None):
        record=self.store.get(id)
        self.policy.require(record,purpose,self.principal,consent)
        return record
    def for_training(self,ids,consents):
        return tuple(self.get(id,purpose='train',consent=consents.get(id)) for id in ids)
