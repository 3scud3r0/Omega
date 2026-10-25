from omega_selfhost.statement_binding import verify as verify_binding
class MathematicsOracle:
    def __init__(self,statements,checker,checker_id,dependencies):
        self.statements=dict(statements);self.checker=checker;self.checker_id=checker_id;self.dependencies=tuple(dependencies)
    def verify(self,id,envelope):
        return verify_binding(self.statements[id],envelope,self.checker,checker_id=self.checker_id,dependencies=self.dependencies)
def summarize(records):
    if not records:return {'cases':0,'correct':0,'verification_seconds':0}
    return {'cases':len(records),'correct':sum(r['valid'] is True for r in records),'verification_seconds':sum(r['verification_seconds'] for r in records)}
