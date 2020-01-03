from collections.abc import Mapping
from functools import wraps, partial

from fabric import Task

from surge.util import maybe_bool, Unboolable, recursive_update


def dtask(collection, *args, **kwargs):
    '''
    Wrap a task function in the_works and create a Task of it.
    '''
    
    def inner(f):
        return ntask(collection, *args, **kwargs)(the_works(f))
    
    return inner

def stask(collection, *args, **kwargs):
    '''
    Wrap a task function in the bare minimum and create a Task.
    '''
    
    
    def inner(f):
        return ntask(collection, *args, **kwargs)(tag_original(f))
    
    return inner

def ntask(collection, *args, **kwargs):
    '''
    Create a task and add it to a collection.
    '''
    
    def inner(f):
        to_return = Task(f, *args, **kwargs)
        
        collection.add_task(to_return)
        
        return to_return
    
    return inner

def the_works(f):
    wrapper = show_settings(f)
    wrapper = try_bool(defaults=False)(wrapper)
    wrapper = merge_options(wrapper)
    wrapper = tag_original(wrapper)
    
    return wrapper

def require(name, value, error=False):
    '''
    Require that a value from the config be of a certain value.
    
    :param name: name of kwarg
    :param value: required value
    :param error: whether to raise an error or just skip
    '''
    
    def inner(f):
        @wraps(f)
        def wrapper(c, *a, **kw):
            try:
                actual = c.config.deploy[name]
            except KeyError as e:
                to_raise = MissedRequirement(name, value, e)
                
                if error:
                    raise to_raise
                else:
                    return to_raise.print()
            
            if actual == value:
                return f(c, *a, **kw)
            else:
                to_raise = MissedRequirement(name, value, actual)
                
                if error:
                    raise to_raise
                else:
                    return to_raise.print()
        
        return wrapper
    
    return inner

class MissedRequirement(Exception):
    def __init__(self, name, expected, actual):
        self.name = name
        self.expected = expected
        self.actual = actual
        
        super().__init__(f'Expected {name!r} to be {expected!r}, got {actual!r}.')
    
    def print(self):
        print(self.args[0])

def tag_original(f):
    @wraps(f)
    def wrapper(c, *a, **kw):
        if not hasattr(c, 'called_task'):
            c.called_task = f.__name__
        
        return f(c, *a, **kw)
    
    return wrapper

def merge_options(f):
    """
    Merge kwargs and default config into kwargs for easy consumption.
    
    Order of precedence: kwarg[k] > c.deploy[k] > c[k]]
    """
    
    @wraps(f)
    def wrapper(c, *a, **kw):
        update = lambda *x,**y: recursive_update(kw, *x, mask=True, condition=lambda k,b,o: not b[k], **y)
        
        update(c.config.deploy)
        update(c.config)
        
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
