from functools import wraps
from inspect import signature
from types import SimpleNamespace

import pytest

import surge.decorators as tarmod


class dtask:
    pass

class stask:
    pass

@pytest.mark.skip('This is just shorthand for a series of common decorators.')
class the_works:
    pass

class require:
    pass

class tag_original:
    def plain(self):
        def original_function(c, a, b=None):
            return c
        
        fake_context = SimpleNamespace()
        decorated_function = tarmod.tag_original(original_function)
        
        result = decorated_function(fake_context, 4, b=77)
        
        assert hasattr(result, 'called_task')
        assert result.called_task == 'original_function'
        
        assert signature(decorated_function) == signature(original_function)
    
    def wrapped(self):
        def original_function(c, a, b=None):
            return c
        
        def easy_wrap(f):
            @wraps(f)
            def inner(*a, **kw):
                return f(*a, **kw)
            
            return inner
        
        wrapped_function = easy_wrap(original_function)
        
        fake_context = SimpleNamespace()
        decorated_function = tarmod.tag_original(wrapped_function)
        
        result = decorated_function(fake_context, 4, b=77)
        
        assert hasattr(result, 'called_task')
        assert result.called_task == 'original_function'
        
        assert signature(decorated_function) == signature(original_function)

class merge_options:
    pass

class try_bool:
    pass

class show_settings:
    pass
