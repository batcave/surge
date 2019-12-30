import pytest

from surge import util


class recursive_update:
    @pytest.mark.parametrize('other', [
        {},
        {1: 2, 3: 4, 5: 6},
        {1: {2: {3: 4}}},
    ])
    def empty(self, other):
        base = {}
        
        util.recursive_update(base, other)
        
        assert base == other
        assert base is not other
    
    class single:
        def overwrite(self):
            base = {1: 2}
            other = {1: 3}
            
            util.recursive_update(base, other)
            
            assert base == {1: 3}
        
        def preserve(self):
            base = {1: 2}
            other = {1: 3}
            
            util.recursive_update(base, other, preserve=True)
            
            assert base == {1: 2}
        
        class mask:
            def hit(self):
                base = {1: 2}
                other = {1: 3}
                
                util.recursive_update(base, other, mask=True)
                
                assert base == {1: 3}
            
            def miss(self):
                base = {1: 2}
                other = {2: 3}
                
                util.recursive_update(base, other, mask=True)
                
                assert base == {1: 2}
        
        class obliterate:
            def success(self):
                base = {1: 2}
                other = {1: {2: 3}}
                
                util.recursive_update(base, other, obliterate=True)
                
                assert base == {1: {2: 3}}
            
            def fail(self):
                base = {1: 2}
                other = {1: {2: 3}}
                
                with pytest.raises(TypeError):
                    util.recursive_update(base, other)
        
        def condition(self):
            base = {1: 2, 2: None}
            other = {1: 3, 2: 4, 3: 4}
            
            util.recursive_update(base, other, condition=lambda k,b,o: b.get(k) is None)
            
            assert base == {1: 2, 2: 4, 3: 4}, base
    
    class deep:
        def simple(self):
            base = {1: {2: 3, 4: 5}}
            other = {1: {2: 4, 3: 4}}
            
            util.recursive_update(base, other)
            
            assert base == {1: {2: 4, 3: 4, 4: 5}}
