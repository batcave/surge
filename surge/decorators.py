from functools import wraps

from fabric import Task


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

def mtask(*args, show_settings=True, **kwargs):
    """
    Roll in originally-called task's name so chained tasks can tell when they're directly called.
    Merge kwargs and default config into kwargs for easy consumption.
    """
    
    def inner(f):
        @wraps(f)
        def wrapper(c, *a, **kw):
            ###TODO: auto-bool
            
            c.called_task = f.__name__
            kw = {k: v or c.deploy[k] or c[k] for k,v in kw.items()}
            
            
            return f(c, *a, **kw)
        
        if show_settings:
            from surge.tasks import show_settings as ss
            
            ###NOTE: this is a small break from the base API, which prohibits
            ###      *args and pre being passed at the same time
            kwargs['pre'] = [ss] + (list(args) or []) + (list(kwargs['pre']) or [])
        
        return Task(wrapper, **kwargs)
    
    return inner

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
