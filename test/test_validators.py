"""
Tests of validator edge cases
"""

# pylint: disable=no-member
import re
from enum import Enum
from typing import Type, List

import pytest

import asdl_adt
from asdl_adt.validators import ValidationError, instance_of


def test_object_is_not_none():
    """
    Test that "object"-typed fields may not be none
    """
    test_adt = asdl_adt.ADT("module test_adt { foo = ( object x ) }")

    assert isinstance(test_adt.foo(3), test_adt.foo)
    assert isinstance(test_adt.foo("bar"), test_adt.foo)

    with pytest.raises(TypeError, match="expected: object, actual: NoneType"):
        test_adt.foo(None)


def test_optional_may_be_none():
    """
    Test that _optional_ "object"-typed fields _may_ be none
    """
    test_adt = asdl_adt.ADT("module test_adt { foo = ( object? x ) }")
    assert isinstance(test_adt.foo(None), test_adt.foo)


def test_subclass_validator():
    class Parent:
        pass

    class Child(Parent):
        pass

    test_adt = asdl_adt.ADT(
        "module test_adt { foo = ( parent x ) }",
        ext_types={"parent": Type[Parent]},
    )

    assert isinstance(test_adt.foo(Parent), test_adt.foo)
    assert isinstance(test_adt.foo(Child), test_adt.foo)

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo(Parent())

    assert exc_info.value.expected == Type[Parent]
    assert exc_info.value.actual == Parent


def test_adhoc_validator():
    def _valid_name(name):
        if name in ('foo', 'bar'):
            return name
        raise ValidationError('foo or bar', name)

    test_adt = asdl_adt.ADT(
        "module test_adt { foo = ( name x ) }",
        ext_types={"name": _valid_name}
    )

    assert isinstance(test_adt.foo('foo'), test_adt.foo)
    assert isinstance(test_adt.foo('bar'), test_adt.foo)

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo('baz')

    assert exc_info.value.expected == 'foo or bar'
    assert exc_info.value.actual == 'baz'


def test_string_subset():
    class Identifier(str):
        _valid_re = re.compile(r"^(?:_\w|[a-zA-Z])\w*$")

        def __new__(cls, name):
            name = str(name)
            if Identifier._valid_re.match(name):
                return super().__new__(cls, name)
            raise ValidationError(Identifier._valid_re.pattern, name)

    test_adt = asdl_adt.ADT(
        "module test_adt { foo = ( iden x ) }",
        ext_types={"iden": instance_of(Identifier, convert=True)}
    )

    assert isinstance(test_adt.foo('valid'), test_adt.foo)
    assert isinstance(test_adt.foo('valid_0'), test_adt.foo)
    assert isinstance(test_adt.foo('_01valid'), test_adt.foo)
    assert isinstance(test_adt.foo('_0vAlId'), test_adt.foo)
    assert isinstance(test_adt.foo(Identifier('_0vAlId')), test_adt.foo)

    assert test_adt.foo('_0vAlId') == test_adt.foo(Identifier('_0vAlId'))

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo('_')

    assert exc_info.value.expected == Identifier._valid_re.pattern
    assert exc_info.value.actual == '_'

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo('01num')

    assert exc_info.value.expected == Identifier._valid_re.pattern
    assert exc_info.value.actual == '01num'


def test_custom_list():
    def _valid_name(name):
        if name in ('foo', 'bar'):
            return name
        raise ValidationError('foo or bar', str)

    test_adt = asdl_adt.ADT(
        "module test_adt { foo = ( name* x ) }",
        ext_types={"name": _valid_name}
    )

    assert isinstance(test_adt.foo(['foo', 'bar', 'bar']), test_adt.foo)

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo('foo')

    assert exc_info.value.expected == list
    assert exc_info.value.actual == str

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo(['baz'])

    assert exc_info.value.expected == List['foo or bar']
    assert exc_info.value.actual == List[str]


def test_enum_type():
    class FooOrBar(Enum):
        foo = 'foo'
        bar = 'bar'

    test_adt = asdl_adt.ADT(
        "module test_adt { foo = ( name* x ) }",
        ext_types={"name": instance_of(FooOrBar, convert=True)}
    )

    foo_obj = test_adt.foo(['foo', 'bar', 'bar'])
    assert isinstance(foo_obj, test_adt.foo)
    assert foo_obj.x == [FooOrBar.foo, FooOrBar.bar, FooOrBar.bar]


def test_bad_validator():
    with pytest.raises(ValueError, match='Unknown validator type'):
        asdl_adt.ADT(
            "module test_adt { foo = ( name* x ) }",
            ext_types={"name": 3}
        )
