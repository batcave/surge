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

def needs_django(f):
    """
    A decorator on a task to ensure the task is not run if
    DJANGO_PROJECT = False
    """
    
    ###FIXME: special case of @require
    
    @wraps(f)
    def django_check(c, *args, **kwargs):
        if c.deploy.DJANGO_PROJECT: ###FIXME: broken
            return f(c, *args, **kwargs)
        else:
            # If this was not called from another surge task then complain
            if c.called_task == f.__name__:
                print(red("This deployment is not configured as a DJANGO_PROJECT"))
            return None
    
    return django_check

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

def skip_if_not(setting, value=True):
    """
    When called from a surge task make sure the supplied `setting` is set
    to `value` before running the decorated task.
    """
    
    ###FIXME: skip looking at c.config, since it's already been merged into kwargs
    ###TODO: refactor to @requires(error=True)
    
    def requires(f):
        @wraps(f)
        def wrapper(c, *args, **kwargs):
            if kwargs.get(setting, c.config.deploy[setting]) == value:
                return f(c, *args, **kwargs)
        
        return wrapper
    
    return requires

###TODO: @promote_to_env(*args, **kwargs) - names of configs to promote to envvar; args is straight, kwargs maps config to envvar name
###TODO: @chown_target - generalizable?
