from collections.abc import Mapping
from functools import wraps

from fabric import Task

from surge.util import maybe_bool, Unboolable


def dtask(*args, **kwargs):
    '''
    Roll in originally-called task's name so chained tasks can tell when they're directly called.
    '''
    
    def inner(f):
        return Task(the_works(f), *args, **kwargs)
    
    return inner

def the_works(f):
    @wraps(f)
    @tag_original
    @show_settings
    @try_bool(defaults=False)
    @merge_options
    def wrapper(c, *a, **kw):
        return f(c, *a, **kw)
    
    return wrapper

def require(name, value, error=False):
    '''
    Require that a kwarg be of a certain value.
    
    :param name: name of kwarg
    :param value: required value
    :param error: whether to raise an error or just skip
    '''
    
    def inner(f):
        @wraps(f)
        def wrapper(c, *a, **kw):
            ###NOTE: assumes that name exists in kw, since the dev wouldn't require it otherwise
            
            if kw[name] == value:
                return f(c, *a, **kw)
            else:
                if _error:
                    raise MissedRequirement(name, value, kw[name])
                else:
                    print(f'skipping {kw["called_task"]} - {name} must be {value}')
        
        return wrapper
    
    return inner

class MissedRequirement(Exception):
    def __init__(self, name, expected, actual):
        self.name = name
        self.expected = expected
        self.actual = actual
        
        super().__init__(f'Expected {name!r} to be {expected!r}, got {actual!r}.')

def tag_original(f):
    @wraps(f)
    def wrapper(c, *a, **kw):
        c.called_task = f.__name__
        
        return f(c, *a, **kw)
    
    return wrapper

def merge_options(f):
    """
    Merge kwargs and default config into kwargs for easy consumption.
    
    Order of precedence: kwarg[k] > c.deploy[k] > c[k]
    """
    
    @wraps(f)
    def wrapper(c, *a, **kw):
        kw = {k: try_bool(k, v or c.deploy[k] or c[k]) for k,v in kw.items()}
        
        return f(c, *a, **kw)
    
    return wrapper

def try_bool(which=True, defaults=None):
    '''
    Try to cast args and kwargs to bool.
    '''
    
    def default(name):
        if defaults is None:
            raise
        elif isinstance(defaults, Mapping):
            return defaults[name]
        elif callable(defaults):
            return defaults(name)
        else:
            return defaults
    
    def cast(name, value):
        try:
            if auto_bool is True:
                return maybe_bool(value, error=True)
            elif auto_bool is False:
                return value
            else:
                if name in auto_bool:
                    return maybe_bool(value, error=True)
                else:
                    return value
        except Unboolable:
            return default(name)
    
    def inner(f):
        @wraps(f)
        def wrapper(c, *a, **kw):
            kw = {k: cast(k,v) for k,v in kw.items()}
            
            return f(c, *a, **kw)
        
        return wrapper
    
    return inner

def show_settings(f):
    '''
    Show settings prior to running.
    '''
    
    @wraps(f)
    def wrapper(c, *args, **kwargs):
        ###TODO: this isn't really a great way to do this, see below
        if show_settings:
            from surge.tasks import show_settings as ss
            ss(c)
        
        return f(c, *args, **kwargs)
        
    ###TODO: Invoke doesn't support late-binding pre-run tasks (yet)
    # if show_settings:
    #     ###NOTE: this is a small break from the base API, which prohibits
    #     ###      *args and pre being passed at the same time
    #     kwargs['pre'] = ['show_settings'] + (list(args) or []) + (list(kwargs['pre']) or [])
    
    return wrapper

###TODO: @promote_to_env(*args, **kwargs) - names of configs to promote to envvar; args is straight, kwargs maps config to envvar name
###TODO: @chown_target - generalizable?
