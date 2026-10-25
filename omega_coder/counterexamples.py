from dataclasses import dataclass
@dataclass(frozen=True)
class Counterexample:
    statement_digest: str
    assignment: dict
    failed_property: str
    verifier: str
    def __post_init__(self):
        if not self.statement_digest or not self.failed_property or not self.verifier:raise ValueError('Incomplete counterexample')
def correction_task(counterexample,reproduce):
    if reproduce(counterexample.assignment) is not False:raise ValueError('Counterexample does not reproduce')
    return {'requirement':'Repair '+counterexample.failed_property,'regression_input':counterexample.assignment,
            'statement_sha256':counterexample.statement_digest,'evidence_source':counterexample.verifier}
