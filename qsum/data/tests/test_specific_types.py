# pylint: disable=redefined-outer-name,missing-function-docstring,wildcard-import,unused-wildcard-import

"""Some type specific tests that are hard to do in test_by_type"""
from copy import deepcopy

from qsum.core.constants import ChecksumCollection, DEFAULT_BYTES_IN_CHECKSUM
from qsum.core.exceptions import QSumInvalidDataTypeException
# noinspection PyUnresolvedReferences
from qsum.tests.helpers import *


def test_integers_generate_unique_checksums(range_2_16):
    value_checksums = set(map(checksum, range_2_16))
    assert len(value_checksums) == len(range_2_16)


def test_str_uniqueness(range_2_16):
    str_values = map(str, range_2_16)
    value_checksums = set(map(checksum, str_values))
    assert len(value_checksums) == len(range_2_16)


def test_float_uniqueness(range_2_16):
    float_values = map(float, range_2_16)
    value_checksums = set(map(checksum, float_values))
    assert len(value_checksums) == len(range_2_16)


def test_complex_uniqueness(range_2_16):
    complex_values = [complex(re, im) for re, im in zip(range_2_16, reversed(range_2_16))]
    complex_checksums = set(map(checksum, complex_values))
    assert len(complex_checksums) == len(range_2_16)


def test_float_0_0_equality():
    assert checksum(0.0) == checksum(-0.0)
    assert checksum(-0.0) == checksum(0.0)


def test_tuple_changes():
    assert checksum((0, 1, 2)) != checksum((-1, 1, 2))
    assert checksum((0, 1, 2)) != checksum((2, 1, 0))


def test_list_changes():
    example_list = [1, 2, 3]
    c_1 = checksum(example_list)
    example_list.append(4)
    c_2 = checksum(example_list)
    assert c_1 != c_2


def test_nested_dict():
    my_dict = {'a': {'b': {'c': 1}}}
    assert Checksum.checksum(my_dict).type == dict


def test_unsorted_set():
    set_1 = {'a', 'b', 'c'}
    set_2 = {'b', 'a', 'c'}
    set_3 = {'c', 'a', 'b'}
    assert checksum(set_1) == checksum(set_2) == checksum(set_3)


def test_unsorted_dict():
    dict_1 = {'a': 1, 'b': 2, 'c': 3}
    dict_2 = {'b': 2, 'a': 1, 'c': 3}
    dict_3 = {'c': 3, 'a': 1, 'b': 2}
    assert checksum(dict_1) == checksum(dict_2) == checksum(dict_3)


def test_nested_changing_dict():
    dict_1 = {'a': {'b': 2}}
    dict_2 = {'a': {'b': 3}}
    assert checksum(dict_1) != checksum(dict_2)


def test_multi_key_type_dict_comparison():
    dict_1 = {'a': 10, 2: 20, 3.0: 30}
    dict_2 = {2: 20, 3.0: 30, 'a': 10}
    assert checksum(dict_1) == checksum(dict_2)


def test_different_singleton_types_unequal():
    assert checksum(None) != checksum(Ellipsis)


@pytest.mark.parametrize('obj', [None, Ellipsis])
def test_singleton_constant(obj):
    assert checksum(obj) == checksum(obj)


@pytest.mark.xfail(raises=QSumInvalidDataTypeException, strict=True)
def test_checksum_collection():
    checksum_collection = ChecksumCollection()
    checksum(checksum_collection)


# keep this right near the limit of the current depth so we know when we've made the stock more complex
# note older minor versions of python 3.x are the limiting factor
@pytest.mark.parametrize('depth', range(0, 90))
def test_deep_nested_dict(depth):
    """Ensure deeply nested dicts can be checksummed"""
    nested_dict = {'foo': 'abc'}
    for key in range(0, depth):
        nested_dict = {key: deepcopy(nested_dict)}
    assert len(checksum(nested_dict)) == DEFAULT_BYTES_IN_CHECKSUM


def test_long_list(range_2_16):
    long_list = list(range_2_16)
    checksum(long_list)
