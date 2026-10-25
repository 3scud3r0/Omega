from dataclasses import dataclass
@dataclass(frozen=True)
class Experiment:
    hypothesis: str
    prediction: object
    intervention: object
    success_contract: str
    seed: int
    def __post_init__(self):
        if not self.hypothesis or not self.success_contract:raise ValueError('Falsifiable experiment contract required')
def run(experiment,environment,interpret):
    raw=environment(experiment.intervention,experiment.seed)
    conclusion=interpret(experiment,raw)
    if type(conclusion) is not dict or conclusion.get('status') not in ('supported','refuted','inconclusive'):raise ValueError('Invalid experiment interpretation')
    return {'hypothesis':experiment.hypothesis,'seed':experiment.seed,'observation':raw,'interpretation':conclusion}
