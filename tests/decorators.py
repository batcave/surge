from functools import wraps
from inspect import signature

from invoke import MockContext
import pytest

import surge.decorators as tarmod #target module


class dtask:
    pass

class stask:
    pass

@pytest.mark.skip('This is just shorthand for a series of common decorators.')
class the_works:
    pass

class require:
    def good(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg')(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blah': 'blarg'}
        
        result = decorated_function(context)
        
        assert result is return_value
    
    def bad_error(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg', error=True)(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blah': 'blam'}
        
        with pytest.raises(tarmod.MissedRequirement):
            decorated_function(context)
    
    def bad_skip(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg', error=False)(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blah': 'blam'}
        context.called_task = 'something'
        
        result = decorated_function(context)
        
        assert result is None
    
    def bad_skip_no_tag(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg', error=False)(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blah': 'blam'}
        
        with pytest.raises(AttributeError, match='called_task'):
            decorated_function(context)
    
    def missing_error(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg', error=True)(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blam': 'blarge'}
        
        with pytest.raises(tarmod.MissedRequirement):
            decorated_function(context)
    
    def missing_skip(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg', error=False)(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blam': 'blarg'}
        context.called_task = 'something'
        
        result = decorated_function(context)
        
        assert result is None
    
    def missing_skip_no_tag(self):
        return_value = object()
        decorated_function = tarmod.require('blah', 'blarg', error=False)(lambda c: return_value)
        context = MockContext()
        context.deploy = {'blam': 'blarg'}
        
        with pytest.raises(AttributeError, match='called_task'):
            decorated_function(context)

class tag_original:
    def plain(self):
        def original_function(c, a, b=None):
            return c
        
        fake_context = MockContext()
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
            def wrapper(*a, **kw):
                return f(*a, **kw)
            
            return wrapper
        
        wrapped_function = easy_wrap(original_function)
        
        fake_context = MockContext()
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
