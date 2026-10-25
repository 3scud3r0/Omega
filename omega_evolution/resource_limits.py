from omega_platform.quotas import Quota
class EvolutionResources:
    def __init__(self,cycles=32,cpu_seconds=600,proposals=256,processes=4):
        self.total=Quota(cycles=cycles,cpu_seconds=cpu_seconds,proposals=proposals)
        self.concurrent=Quota(processes=processes)
    def begin_cycle(self,proposals,cpu_seconds):self.total.consume(cycles=1,proposals=proposals,cpu_seconds=cpu_seconds)
    def process(self):return self.concurrent.reserve(processes=1)
    def stop(self):self.total.revoke();self.concurrent.revoke()
