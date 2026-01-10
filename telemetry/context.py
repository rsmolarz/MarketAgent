from contextvars import ContextVar

_current_run = ContextVar("current_run", default=None)

def set_current_run(run):
    _current_run.set(run)

def get_current_run():
    return _current_run.get()
