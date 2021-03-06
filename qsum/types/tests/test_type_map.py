# pylint: disable=missing-function-docstring
import pytest

from qsum import checksum
from qsum.core.constants import BYTES_IN_PREFIX
from qsum.types.type_logic import checksum_to_type
from qsum.types.type_map import TYPE_TO_PREFIX, SPECIAL_PREFIXES


def test_types_prefix_bytes():
    for value in TYPE_TO_PREFIX.values():
        assert len(value) == BYTES_IN_PREFIX


def test_types_prefix_unique():
    prefixes = list(TYPE_TO_PREFIX.values()) + list(SPECIAL_PREFIXES)
    assert len(prefixes) == len(set(prefixes))


@pytest.mark.parametrize('value,expected_type',
                         [(False, bool),
                          ("foo", str),
                          (1, int)])
def test_checksum_types(value, expected_type):
    assert checksum_to_type(checksum(value)) == expected_type
