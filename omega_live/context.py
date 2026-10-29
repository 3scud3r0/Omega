"""Optional audit context for CLI phases, including existing native workflows."""
from contextvars import ContextVar
from pathlib import Path
import time
import uuid
from .store import Store

CURRENT=ContextVar('omega_live_observer',default=None)


class Cancelled(RuntimeError):pass


def emit(kind,payload=None):
    context=CURRENT.get()
    if context:context['store'].event(context['run'],kind,payload or {},context['worker'])


def checkpoint(phase,payload=None):
    context=CURRENT.get()
    if not context:return
    store,run,worker=context['store'],context['run'],context['worker'];started=time.monotonic()
    while True:
        state=store.checkpoint(run,worker,lease_seconds=300)
        if state['status']=='cancelled':raise Cancelled('Operation cancelled at safe checkpoint: '+phase)
        if store.take_step(run,worker):break
        if time.monotonic()-started>300:raise Cancelled('Operation remained paused for the bounded checkpoint timeout')
        time.sleep(.05)
    emit('phase.started',{'phase':phase,**(payload or {})})


def tracked(kind,call,*,directory=None):
    # No arbitrary argv or environment is copied to the history. Inputs which
    # are relevant to a phase are represented by pinned hashes in phase events.
    if CURRENT.get():return call()
    directory=Path(directory) if directory else Path(__file__).resolve().parents[1]/'build/live'
    store=Store(directory);state=store.create(kind=kind,config={'iterations':1});run=state['id'];worker='cli-'+uuid.uuid4().hex
    store.checkpoint(run,worker,lease_seconds=300);token=CURRENT.set({'store':store,'run':run,'worker':worker})
    try:
        checkpoint(kind);code=call()
        state=store.checkpoint(run,worker,lease_seconds=300)
        store.finish(run,worker,status='cancelled' if state['status']=='cancelled' else 'completed' if code in (None,0) else 'failed',result={'exit_code':code})
        return code
    except BaseException as error:
        # Error type is sufficient; raw tool stderr could contain model input
        # or credentials and is not indiscriminately copied into global logs.
        emit('operation.error',{'type':type(error).__name__})
        store.finish(run,worker,status='cancelled' if isinstance(error,(Cancelled,KeyboardInterrupt)) else 'failed',result={'error_type':type(error).__name__})
        raise
    finally:CURRENT.reset(token)
