"""
For any given type we would like a fixed prefix value to guarantee types match when comparing checksums

We reserve 2 bytes (65536 unique values) for the compact representation of the type tyhat can be looked up against this
table, please observe the following reserved groups:
    \x00: builtin python types that represent individual objects
    \x01: builtin python containers and collections
"""
#
from collections import deque

PREFIX_BYTES = 2

RESERVED_INVALID_PREFIX = b'\xff\xff'

TYPE_TO_PREFIX = {
    # \x00: builtin python types that represent individual objects
    int: b'\x00\x00',
    str: b'\x00\x01',
    bool: b'\x00\x02',
    bytes: b'\x00\x03',
    float: b'\x00\x04',
    complex: b'\x00\x05',
    bytearray: b'\x00\x06',
    type: b'\x00\x07',

    # \x01: builtin python containers and collections
    tuple: b'\x01\x00',
    list: b'\x01\x01',
    deque: b'\x01\x02',
    dict: b'\x01\x03',
}
PREFIX_TO_TYPE = {v: k for k, v in TYPE_TO_PREFIX.items()}
