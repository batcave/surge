from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from distutils.util import strtobool
from operator import setitem


class Unboolable(ValueError): pass

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

def maybe_bool(value, error=False):
    if isinstance(value, str):
        if value.lower() in ('true', 'yes'):
            return True
        elif value.lower() in ('false', 'no'):
            return False
        else:
            if error:
                raise Unboolable
            else:
                return value
    else:
        return value

def recursive_update(base_dict, other_dict, preserve=False, obliterate=False, mask=False, condition=lambda k,b,o: True):
    '''
    :param preserve: Forbid overwriting non-mapping at all.
    :param obliterate: Allow overwriting non-mapping with mapping.
    :param mask: Only allow updating when the key exists in the base.
    :param condition: Function that determines when an overwrite occurs.
                      Function params: (key, base, other)
    '''
    
    recurse = lambda k,v: recursive_update(base_dict[k], v, preserve=preserve, obliterate=obliterate)
    assign = lambda k,v: condition(k, base_dict, other_dict) and setitem(base_dict, k, deepcopy(v))
    
    for k,v in other_dict.items():
        if k in base_dict:
            if isinstance(v, Mapping):
                if isinstance(base_dict[k], MutableMapping):
                    recurse(k, v)
                elif isinstance(base_dict[k], Mapping):
                    base_dict[k] = dict(base_dict[k])
                    recurse(k, v)
                else:
                    if obliterate:
                        assign(k, v)
                    else:
                        raise TypeError(f'Cannot overwrite non-mapping with mapping at {k}')
            else:
                if preserve:
                    pass ###intentional
                else:
                    assign(k, v)
        else:
            if mask:
                pass ###intentional
            else:
                assign(k, v)

