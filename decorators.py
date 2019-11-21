from functools import wraps


def needs_django(f):
    """
    A decorator on a task to ensure the task is not run if
    DJANGO_PROJECT = False
    """
    
    @wraps(f)
    def django_check(*args, **kwargs):
        if getattr(env.deploy_settings, 'DJANGO_PROJECT', False):
            return f(*args, **kwargs)
        else:
            # If this was not called from another surge task then complain
            if not env.surge_stack:
                print(red("This deployment is not configured as a DJANGO_PROJECT"))
            return None
    
    return django_check

def surge_stack(f):
    """
    A surge_stack decorator on a task sets a 'surge_stack' attribute on the
    environment that is used to signal to other tasks that they were called
    as part of a sequence of other tasks and to not behave the same as they
    might if called alone.

    A surge_stack task can always override settings with it's kwargs
    """
    
    @wraps(f)
    def stash_surge_task(*args, **kwargs):
        env['surge_stack'] = f.__name__
        env.deploy_settings.update(kwargs)
        show_settings()
        return f(*args, **kwargs)

    return stash_surge_task

def skip_if_not(setting, what=True):
    """
    When called from a surge_stack task make sure the supplied setting is set
    to what (True or False) before running the decorated task.
    """
    
    def requires(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if env['surge_stack'] and not getattr(env.deploy_settings, setting, not what) == what:
                return
            else:
                return f(*args, **kwargs)
        
        return wrapper
    
    return requires

def can_override_settings(f):
    """
    A task that when called command line can have its kwargs override the settings of the deploy
    """
    
    @wraps(f)
    def override(*args, **kwargs):
        if not env['surge_stack']:
            env.deploy_settings.update(kwargs)
        
        return f(*args, **kwargs)
    
    return override
