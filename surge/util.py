from distutils.util import strtobool


def bool_opt(opt, kwargs, default=False):
    """
    Will convert opt strings to python True/False, if it exists in kwargs.
    Or, will return what is in the deploy_settings if it exists there.
    Finally, will return the default if it doesn't exist in either.
    """

    default = kwargs.get(opt.lower(), getattr(env.deploy_settings, opt.upper(), default))
    
    if isinstance(default, str):
        return strtobool(default)
    else:
        return default

def maybe_bool(value):
    if isinstance(value, str):
        if value.lower() in ('true', 'yes'):
            return True
        elif value.lower() in ('false', 'no'):
            return False
        else:
            return value
    else:
        return value
