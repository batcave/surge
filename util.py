from distutils.util import strtobool


def boold_up(kwargs):
    """
    Will convert opt strings of True/False to python True/False.
    Will upcase keys.
    """
    
    fm = {'FALSE': False, 'TRUE': True}
    nd = {}
    
    for k, v in kwargs.items():
        try:
            nk = k.upper()
        except:
            nk = k
        
        try:
            nv = fm.get(v.upper(), v)
        except:
            nv = v
        
        nd[nk] = nv
    
    return nd

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
