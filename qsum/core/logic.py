import functools
import inspect
import types
import typing

from qsum.core.cache import is_sub_class
from qsum.core.constants import BYTES_IN_PREFIX, CONTAINER_TYPES, MAPPABLE_CONTAINER_TYPES, DEFAULT_HASH_ALGO, \
    UNORDERED_CONTAINER_TYPES, HashAlgoType, CHECKSUM_CLASS_NAME, ChecksumCollection, ChecksumType, \
    DEFAULT_ALLOW_UNREGISTERED, DependsOnType, ALL_SUBCLASS_TYPES
from qsum.core.dependency import resolve_dependencies
from qsum.core.exceptions import QSumUnhandledContainerType, QSumInvalidChecksum
from qsum.data import data_checksum
from qsum.types.type_logic import checksum_to_type, type_to_prefix
from qsum.types.type_map import TYPE_TO_PREFIX, UNREGISTERED_TYPE_PREFIX


def checksum(obj: typing.Any, hash_algo: HashAlgoType = DEFAULT_HASH_ALGO,
             allow_unregistered: bool = DEFAULT_ALLOW_UNREGISTERED, depends_on: DependsOnType = None) -> bytes:
    """Generate a checksum for a given object based on it's type and contents

    Args:
        obj: object to generate a checksum of
        hash_algo: the hash algorithm to use to convert the bytes to a message digest
        allow_unregistered: as long as the logic can handle it allow unregistered types to be checksummed,
            currently the main purpose of this is to allow subclasses of supported containers to be checksummed
        depends_on: collection of dependencies, strings represent python package distributions,
            adding 'python' will include the python version in the hash

    Returns:
        checksum bytes representing the object's type and a message digest of the data

    >>> from qsum import checksum
    >>> checksum('a nice word').hex()
    '000177bdb96414925834c784c7497b14ca73a7ecead6d0542a5666bcb0598813bf9d'
    >>> checksum(('a', 'nice', 'word')).hex()
    '010086eb00a39e1bd72ae55e30fc9638b12803a495b0e45f54fba9438d60e3310e9a'
    >>> checksum({'a': 1, 'nice': 2, 'word': 3}).hex()
    '0103ed71fada8381439167d30ca1310e87af60e8f41e1fa320e0f626775f5b8cd908'
    """
    obj_type = type(obj)
    return _checksum(obj, obj_type, obj_type, hash_algo, allow_unregistered=allow_unregistered, depends_on=depends_on)


def _checksum(obj: typing.Any, obj_type: typing.Type, checksum_type: typing.Type, hash_algo: HashAlgoType,
              allow_unregistered: bool, depends_on: DependsOnType = None) -> bytes:
    """Checksum the given obj, assuming it's of obj_type and return a checksum of type checksum_type

    Args:
        obj: object to checksum
        obj_type:
            the type of logic to use for checksumming the data,
            useful to aliasing one type to another's checksum methodology while maintaining the correct prefix
        checksum_type:
            the type to use for the checksum prefix, useful when the process of checksumming one object involves
            transforming the data to another type but we want to return the original object type
        hash_algo: the hash algorithm to use to convert the bytes to a message digest
        allow_unregistered: as long as the logic can handle it allow unregistered types to be checksummed,
            currently the main purpose of this is to allow subclasses of supported containers to be checksummed
        depends_on: collection of dependencies, strings represent python package distributions

    Returns:
        checksum bytes

    """
    # bind the args that won't change with internal recursive calls
    _checksum_w_args = functools.partial(_checksum, hash_algo=hash_algo, allow_unregistered=allow_unregistered)

    # if depends_on is specified then we need to combine the hash of the resolved dependencies with the hash of obj
    # note recursive calls to _checksum never pass depends_on since it always handled in the first call from checksum
    if depends_on is not None:
        resolved_deps = resolve_dependencies(depends_on)
        return _checksum_w_args(obj=(obj, resolved_deps), obj_type=tuple,
                                checksum_type=obj_type)  # we have handled the depends_on so don't pass it again

    # Handle containers with multiple objects that need to be individual checksummed and then combined
    if is_sub_class(obj_type, CONTAINER_TYPES):
        if is_sub_class(obj_type, MAPPABLE_CONTAINER_TYPES):
            checksum_bytes = bytearray()
            if is_sub_class(obj_type, tuple(UNORDERED_CONTAINER_TYPES)):
                # compute the checksums and sort the checksums as we don't trust native python sorting across types
                checksum_bytes = checksum_bytes.join(
                    sorted([_checksum_w_args(obj_item, type(obj_item), type(obj_item)) for obj_item in obj]))
            else:
                # compute the checksums of the elements of the mappable collection and build up a byte array
                # we are capturing the type and data checksums of all of the elements here
                # container types that hit this logic should have a predicable iteration order
                for obj_item in obj:
                    obj_item_type = type(obj_item)
                    checksum_bytes += _checksum_w_args(obj_item, obj_item_type, obj_item_type)
            # let's use the container type for the type_checksum but tell the data_checksum to use the bytes logic
            prefix = type_to_prefix(checksum_type, allow_unregistered=allow_unregistered)
            # if we are using an unregistered type prefix then checksum_type needs to be included in the data checksum
            return prefix + data_checksum(checksum_bytes, bytes, hash_algo,
                                          checksum_type=checksum_type if prefix == UNREGISTERED_TYPE_PREFIX else None)

        if is_sub_class(obj_type, dict):
            # obj.items() returns dict_items which appear list like but in fact we don't want to trust the stability
            # of the order of the items, so let's treat it like an unordered set (no need to actually make it a set,
            # in fact that may cause issues if the values aren't hashable, i.e. dict of dicts) and use the sort of the
            # checksums as our method for stabilizing the overall checksum of the object
            # for python 3.7 this means that even though dicts are ordered, we will ignore that order, this is a design
            # decision and may need to be re-visited/potentially have an option to pick the methodology
            return _checksum_w_args(obj=obj.items(), obj_type=set, checksum_type=obj_type)

        raise QSumUnhandledContainerType(
            "{} has no checksumming implementation available".format(obj_type))  # pragma: no cover

    # handle functions (which are a mini collection of python objects themselves)
    if is_sub_class(obj_type, types.FunctionType):
        # removing leading and trailing whitespace (note this is not a proper solution as individual lines
        # can still have whitespace differences that cause the same function to checksum differently
        # TODO: evenly remove whitespace from each line
        source_code = inspect.getsource(obj).strip()
        function_attributes = obj.__dict__
        # choosing to use the module name here and not the module, but may revisit at some point or make an option
        module_name = inspect.getmodule(obj).__name__
        # combine in to a tuple and use the standard logic for combining the elements but then mark as a function
        return _checksum_w_args((source_code, function_attributes, module_name), tuple, obj_type)

    # For a simple object combine the type with the data checksum
    prefix = type_to_prefix(checksum_type)
    # if we are using an unregistered type prefix then checksum_type needs to be included in the data checksum
    return prefix + data_checksum(obj, obj_type, hash_algo=hash_algo,
                                  checksum_type=checksum_type if prefix == UNREGISTERED_TYPE_PREFIX else None)


def checksum_hex(obj: typing.Any, hash_algo: HashAlgoType = DEFAULT_HASH_ALGO):
    """Generate a checksum hex for a given object based on it's type and contents

    Args:
        obj: object to generate a checksum of
        hash_algo: the hash algorithm to use to convert the bytes to a message digest

    Returns:
        checksum string representing the object's type and a message digest of the data
    >>> from qsum import checksum
    >>> checksum_hex('a nice word')
    '000177bdb96414925834c784c7497b14ca73a7ecead6d0542a5666bcb0598813bf9d'
    >>> checksum_hex(('a', 'nice', 'word'))
    '010086eb00a39e1bd72ae55e30fc9638b12803a495b0e45f54fba9438d60e3310e9a'
    >>> checksum_hex({'a': 1, 'nice': 2, 'word': 3})
    '0103ed71fada8381439167d30ca1310e87af60e8f41e1fa320e0f626775f5b8cd908'
    """
    return checksum(obj=obj, hash_algo=hash_algo).hex()


def _checksum_to_bytes(checksum_obj: ChecksumType) -> bytes:
    """Convert a checksum like object to bytes

    Args:
        checksum_obj: a checksum like object

    Returns:
        checksum bytes
    """
    if isinstance(checksum_obj, bytes):
        return checksum_obj
    if isinstance(checksum_obj, str):
        return bytes.fromhex(checksum_obj)
    if isinstance(checksum_obj, Checksum):
        return checksum_obj.checksum_bytes
    raise QSumInvalidChecksum("Specified is_checksum but didn't pass a checksum like object")


class Checksum:
    """Class for working with checksums

    All manipulations of checksums should utilize this class
    >>> Checksum('foo').hex()
    '00012c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'
    >>> Checksum.from_checksum(checksum('foo')).hex()
    '00012c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'
    >>> Checksum('foo') == '00012c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'
    True
    """

    @classmethod
    def checksum(cls, obj: typing.Any, **kwargs) -> CHECKSUM_CLASS_NAME:
        """Create a checksum class from a given object with the given kwawrgs passed to the checksum function"""
        return Checksum(obj, is_checksum=False, **kwargs)

    @classmethod
    def from_checksum(cls, obj) -> CHECKSUM_CLASS_NAME:
        """Wrap an existing checksum bytes in an object"""
        return Checksum(obj, is_checksum=True)

    def __init__(self, obj: typing.Any, is_checksum: bool = False, **kwargs):
        """Checksum the given obj using the given kwargs and set the result to checksum bytes

        Args:
            obj: object to checksum
            is_checksum: whether the obj being passed is already a checksum
            **kwargs: kwargs to pass to checksum
        """

        # if the obj is already a checksum
        if is_checksum:
            self._checksum_bytes = _checksum_to_bytes(obj)
        else:
            # compute the checksum with the given args
            self._checksum_bytes = checksum(obj, **kwargs)

    @property
    def type(self) -> typing.Type:
        """type of the checksum"""
        return checksum_to_type(self._checksum_bytes)

    @property
    def checksum_bytes(self) -> bytes:
        """The raw bytes of the checksum"""
        return self._checksum_bytes

    def hex(self) -> str:
        """The hex representation of the checksum"""
        return self._checksum_bytes.hex()

    def __repr__(self) -> str:
        """Use the hexdigest as repr is a string so the bytes are actually a less efficient representation"""
        return "Checksum('{}',is_checksum=True)".format(self.hex())

    def __eq__(self, other) -> bool:
        """Equality is determined by comparing the raw bytes of the checksum"""
        if isinstance(other, bytes):
            # if comparing to raw bytes then just compare to the checksum_bytes
            return self._checksum_bytes == other
        if isinstance(other, str):
            # if comparing to a string use the hex
            return self.hex() == other

        # otherwise assume we have been given a Checksum like object and try to pull the checksum_bytes from it
        return self._checksum_bytes == other.checksum_bytes

    def __str__(self) -> str:
        """Use the hex digest and get the type name for the nicer representation"""
        # The first BYTES_IN_PREFIX * 2 (since we're going from bytes to hex) are the type prefix
        # we remove this prefix from the hexdigest as we're displaying the human readable version beforehand
        return 'Checksum({}:{})'.format(checksum_to_type(self._checksum_bytes).__name__,
                                        self.hex()[BYTES_IN_PREFIX * 2:])

    def __add__(self, other: CHECKSUM_CLASS_NAME):
        """Combine two checksum objects together

        Args:
            other: another instance of a Checksum object

        Returns:
            Checksum object with _checksum_bytes having the special Checksum prefix type

        """
        return Checksum.from_checksum(
            _checksum(self._checksum_bytes + other.checksum_bytes, obj_type=bytes, checksum_type=ChecksumCollection,
                      hash_algo=DEFAULT_HASH_ALGO, allow_unregistered=DEFAULT_ALLOW_UNREGISTERED))


def is_supported_type(the_type: type) -> bool:
    """
    Determine if the given type is supported by checking against the prefix map
    Args:
        the_type: type to check

    Returns:
        Whether the given type is checksummable
    """
    # first the quick lookup and then check subclasses
    return the_type in TYPE_TO_PREFIX or is_sub_class(the_type, ALL_SUBCLASS_TYPES)
