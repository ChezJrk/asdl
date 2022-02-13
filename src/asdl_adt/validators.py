"""
Common validators for custom types.
"""
from functools import lru_cache
from typing import Type


class ValidationError(TypeError):
    """
    An error to raise due to an argument validation issue in an ASDL ADT field.
    """

    def __init__(self, expected, actual):
        super().__init__()

        self.expected = expected
        self.actual = actual

    def __str__(self):
        expected, actual = self.expected, self.actual
        if isinstance(expected, type):
            expected = expected.__qualname__
        if isinstance(actual, type):
            actual = actual.__qualname__
        return f"expected: {expected}, actual: {actual}"


@lru_cache(maxsize=0)
def instance_of(typ, *, convert=False):
    """
    Return a validator that checks if an object is an instance of the given type
    """

    def _validator(obj):
        if obj is not None:
            if isinstance(obj, typ):
                return obj

            if convert:
                return typ(obj)

        raise ValidationError(typ, type(obj))

    return _validator


@lru_cache(maxsize=0)
def subclass_of(typ):
    """
    Return a validator that checks if an object is a type inheriting from the given
    type.
    """

    def _validator(obj):
        if obj is not None and isinstance(obj, type) and issubclass(obj, typ):
            return obj

        raise ValidationError(Type[typ], type(obj))

    return _validator
