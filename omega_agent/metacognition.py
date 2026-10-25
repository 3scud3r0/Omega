from enum import Enum
class Decision(str,Enum):
    CONTINUE='continue'
    EVIDENCE='gather_evidence'
    HELP='ask_for_help'
    STOP='stop'
def decide(*,remaining,contradictions,unknown_domain,expected_gain,cost,help_available=True):
    if remaining<=0:return Decision.STOP
    if contradictions:return Decision.EVIDENCE
    if unknown_domain:return Decision.HELP if help_available else Decision.STOP
    if expected_gain<=cost:return Decision.STOP
    return Decision.CONTINUE
