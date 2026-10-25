"""Read episodic memory through the consent facade, never through a raw DB."""
from .contracts import Contract, Tool
from omega_memory.privacy import PrivateMemory


def register_memory(adapter, memory, consent_resolver):
    if type(memory) is not PrivateMemory or memory.principal != adapter.principal or not callable(consent_resolver):
        raise ValueError('Private memory and a host consent resolver required')

    def retrieve(arguments):
        id = arguments['id']
        if not 0 < len(id) <= 256:
            raise ValueError('Bounded episode identity required')
        consent = consent_resolver(id, adapter.principal)
        return {'episode': memory.get(id, purpose='retrieve', consent=consent), 'authority': False}

    adapter.register(Tool('memory.retrieve', 'memory.retrieve',
                          Contract({'id': str}, frozenset({'id'}), 4096),
                          Contract({'episode': dict, 'authority': bool},
                                   frozenset({'episode', 'authority'}), 2 * 1024**2), retrieve))
