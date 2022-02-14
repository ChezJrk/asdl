"""
Tests of validator edge cases
"""

# pylint: disable=no-member
import re
from enum import Enum
from typing import Type, List, Literal

import pytest

import asdl_adt
from asdl_adt.validators import ValidationError, instance_of


def test_object_is_not_none():
    """
    Test that "object"-typed fields may not be none
    """
    test_adt = asdl_adt.ADT("module test_object_is_not_none { foo = ( object x ) }")

    assert isinstance(test_adt.foo(3), test_adt.foo)
    assert isinstance(test_adt.foo("bar"), test_adt.foo)

    with pytest.raises(TypeError, match="expected: object, actual: NoneType"):
        test_adt.foo(None)


def test_optional_may_be_none():
    """
    Test that _optional_ "object"-typed fields _may_ be none
    """
    test_adt = asdl_adt.ADT("module test_optional_may_be_none { foo = ( object? x ) }")
    assert isinstance(test_adt.foo(None), test_adt.foo)
    assert test_adt.foo(None).x is None


def test_subclass_validator():
    """
    Test that Type[X] accepts class values which are subtypes of X.
    """

    # pylint: disable=too-few-public-methods,missing-class-docstring
    class Parent:
        pass

    class Child(Parent):
        pass

    test_adt = asdl_adt.ADT(
        "module test_subclass_validator { foo = ( parent x ) }",
        ext_types={"parent": Type[Parent]},
    )

    assert isinstance(test_adt.foo(Parent), test_adt.foo)
    assert isinstance(test_adt.foo(Child), test_adt.foo)

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo(Parent())

    assert exc_info.value.expected == Type[Parent]
    assert exc_info.value.actual == Parent


def test_adhoc_validator():
    """
    Test that user-defined functions may be used as ad-hoc validators, as long as they
    return the normalized value or raise a ValidationError.
    """

    def _valid_name(name):
        if name in ("foo", "bar"):
            return name
        raise ValidationError(Literal["foo", "bar"], str)

    test_adt = asdl_adt.ADT(
        "module test_adhoc_validator { foo = ( name x ) }",
        ext_types={"name": _valid_name},
    )

    assert isinstance(test_adt.foo("foo"), test_adt.foo)
    assert isinstance(test_adt.foo("bar"), test_adt.foo)

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo("baz")

    assert exc_info.value.expected == Literal["foo", "bar"]
    assert exc_info.value.actual == str


def test_string_subset():
    """
    Test that instance_of(..., convert=True) works with str subtypes.
    """

    # pylint: disable=missing-class-docstring
    class Identifier(str):
        valid_re = re.compile(r"^(?:_\w|[a-zA-Z])\w*$")

        def __new__(cls, name):
            name = str(name)
            if Identifier.valid_re.match(name):
                return super().__new__(cls, name)
            raise ValidationError(Identifier.valid_re.pattern, name)

    test_adt = asdl_adt.ADT(
        "module test_string_subset { foo = ( iden x ) }",
        ext_types={"iden": instance_of(Identifier, convert=True)},
    )

    assert isinstance(test_adt.foo("valid"), test_adt.foo)
    assert isinstance(test_adt.foo("valid_0"), test_adt.foo)
    assert isinstance(test_adt.foo("_01valid"), test_adt.foo)
    assert isinstance(test_adt.foo("_0vAlId"), test_adt.foo)
    assert isinstance(test_adt.foo(Identifier("_0vAlId")), test_adt.foo)

    assert test_adt.foo("_0vAlId") == test_adt.foo(Identifier("_0vAlId"))

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo("_")

    assert exc_info.value.expected == Identifier.valid_re.pattern
    assert exc_info.value.actual == "_"

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo("01num")

    assert exc_info.value.expected == Identifier.valid_re.pattern
    assert exc_info.value.actual == "01num"


def test_custom_list():
    """
    Test that adhoc validators work in conjunction with lists
    """

    def _valid_name(name):
        if name in ("foo", "bar"):
            return name
        raise ValidationError(Literal["foo", "bar"], str)

    test_adt = asdl_adt.ADT(
        "module test_custom_list { foo = ( name* x ) }", ext_types={"name": _valid_name}
    )

    assert isinstance(test_adt.foo(["foo", "bar", "bar"]), test_adt.foo)

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo("foo")

    assert exc_info.value.expected == list
    assert exc_info.value.actual == str

    with pytest.raises(ValidationError) as exc_info:
        test_adt.foo(["baz"])

    assert exc_info.value.expected == List[Literal["foo", "bar"]]
    assert exc_info.value.actual == List[str]


def test_enum_type():
    """
    Test that enumerated Python types play nicely with the validation system
    """

    # pylint: disable=missing-class-docstring,disallowed-name
    class FooOrBar(Enum):
        foo = "foo"
        bar = "bar"

    test_adt = asdl_adt.ADT(
        "module test_enum_type { foo = ( name* x ) }",
        ext_types={"name": instance_of(FooOrBar, convert=True)},
    )

    foo_obj = test_adt.foo(["foo", "bar", "bar"])
    assert isinstance(foo_obj, test_adt.foo)
    assert foo_obj.x == [FooOrBar.foo, FooOrBar.bar, FooOrBar.bar]


def test_bad_validator():
    """
    Test that an error is raised when proving an invalid validator type.
    """

    with pytest.raises(ValueError, match="Unknown validator type"):
        asdl_adt.ADT(
            "module test_bad_validator { foo = ( name* x ) }",
            ext_types={"name": 3},
        )
