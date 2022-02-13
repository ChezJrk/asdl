import pytest

import asdl_adt


def test_object_is_not_none():
    mod = asdl_adt.ADT('module mod { foo = ( object x ) }')

    assert isinstance(mod.foo(3), mod.foo)
    assert isinstance(mod.foo('bar'), mod.foo)

    with pytest.raises(TypeError, match='expected: object, actual: NoneType'):
        mod.foo(None)


def test_optional_may_be_none():
    mod = asdl_adt.ADT('module mod { foo = ( object? x ) }')
    assert isinstance(mod.foo(None), mod.foo)
