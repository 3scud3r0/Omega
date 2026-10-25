"""Tool implementations are supplied by the host; documents cannot register tools."""
class CapabilityAdapter:
    def __init__(self,verifier,principal,audit):self.verifier=verifier;self.principal=principal;self.audit=audit;self.tools={}
    def register(self,tool):
        if tool.name in self.tools:raise ValueError('Duplicate tool')
        self.tools[tool.name]=tool
    def call(self,name,arguments,capability):
        if name not in self.tools:raise PermissionError('Unknown tool')
        tool=self.tools[name];tool.arguments.check(arguments)
        claim=self.verifier.require(capability,self.principal,tool.action)
        result=tool.invoke(arguments)
        tool.response.check(result)
        self.audit.append({'tool':name,'principal':self.principal,'capability_id':claim['id'],'status':'completed'})
        return result
