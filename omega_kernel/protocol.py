"""Data-only request snapshots and independent artifact boundary checks."""
from __future__ import annotations

from fractions import Fraction
import hashlib
from pathlib import Path
import re
import struct

from omega_security.encoding import canonical, decode

MAX_BYTES = 4 * 1024**2
ARCHITECTURES = {"x86_64": 62, "aarch64": 183, "riscv64": 243}
NATIVE_OPERATIONS = frozenset({"verify", "batch", "tensor", "graph", "capabilities"})
OMEGA_OPERATIONS = frozenset({"verify-omega", "parse", "compile-source", "compile-ir",
                              "evaluate", "tensor-reference", "engine"})


def plain(value, depth=0, meter=None):
    """Reject floats/bools/null, cycles, oversized strings and expanded aliases."""
    if meter is None:
        meter = [60000, MAX_BYTES]
    meter[0] -= 1
    if depth > 40 or meter[0] < 0:
        raise ValueError("Kernel request structure budget")
    kind = type(value)
    if kind is Fraction:
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
            raise ValueError("Rational input bit budget")
        return str(value)
    if kind is int:
        if value.bit_length() > 4096:
            raise ValueError("Integer input bit budget")
        return value
    if kind is str:
        if len(value) > meter[1] or "\x00" in value:
            raise ValueError("Kernel input string budget/NUL")
        meter[1] -= len(value.encode("utf-8"))
        if meter[1] < 0:
            raise ValueError("Kernel request byte budget")
        return value
    if kind is list:
        if len(value) > meter[0]:
            raise ValueError("Kernel list budget")
        return [plain(child, depth + 1, meter) for child in value]
    if kind is dict:
        if 2 * len(value) > meter[0] or any(type(key) is not str for key in value):
            raise ValueError("Kernel object keys/budget")
        return {plain(key, depth + 1, meter): plain(child, depth + 1, meter)
                for key, child in value.items()}
    raise ValueError("Kernel inputs are exact integers/rationals, strings, lists and objects")


def envelope(operation, request):
    if operation not in NATIVE_OPERATIONS | OMEGA_OPERATIONS or type(request) is not dict:
        raise ValueError("Known kernel operation and request object required")
    result = {"operation": operation, "request": plain(request)}
    data = canonical(result, max_bytes=MAX_BYTES, max_nodes=60000, max_depth=44)
    if operation in NATIVE_OPERATIONS:
        # The tiny allocation-free C protocol intentionally excludes escaped
        # and non-ASCII strings. Numeric tokens are signed 64-bit integers.
        if any(c > 126 or c < 32 for c in data) or b"\\" in data:
            raise ValueError("Native protocol accepts unescaped ASCII strings only")
    return data


def read_document(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    return decode(data, max_bytes=MAX_BYTES, max_nodes=60000, max_depth=44)


def elf_bytes(document):
    """Validate generated ELF independently of the Omega emitter.

    This is structural validation, not an instruction verifier. Execution
    always requires the external OS sandbox, even after this check succeeds.
    """
    if type(document) is not dict or document.get("format") != "omega-direct-elf-1":
        raise ValueError("Direct ELF result required")
    architecture = document.get("architecture")
    if architecture not in ARCHITECTURES:
        raise ValueError("Unknown ELF architecture")
    text = document.get("elf_hex")
    if (type(text) is not str or len(text) < 8192 or len(text) > 270336 or
            len(text) % 2 or not re.fullmatch("[0-9a-f]+", text)):
        raise ValueError("ELF hexadecimal encoding/size")
    data = bytes.fromhex(text)
    if data[:16] != b"\x7fELF\x02\x01\x01" + bytes(9):
        raise ValueError("ELF identification")
    header = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    if header != (2, ARCHITECTURES[architecture], 1, 0x401000, 64, 0, 0,
                  64, 56, 3, 0, 0, 0):
        raise ValueError("ELF header outside the declared Linux ABI")
    expected = (
        (1, 5, 0, 0x400000, 0x400000, len(data), len(data), 4096),
        (1, 6, 0, 0x600000, 0x600000, 0, 4096, 4096),
        (0x6474E551, 6, 0, 0, 0, 0, 0, 16),
    )
    for index, wanted in enumerate(expected):
        if struct.unpack_from("<IIQQQQQQ", data, 64 + 56 * index) != wanted:
            raise ValueError("ELF segment permissions/layout")
    if any(data[232:4096]):
        raise ValueError("Unexpected data before machine code")
    code_bytes = document.get("machine_code_bytes")
    if code_bytes != len(data) - 4096 or code_bytes <= 0:
        raise ValueError("ELF machine-code length")
    return data


def input_bytes(values, count):
    if type(values) is not list or len(values) != count or count > 16:
        raise ValueError("Direct ELF argument count")
    if any(type(x) is not int or not -(1 << 63) <= x < (1 << 63) for x in values):
        raise ValueError("Signed 64-bit integer arguments required")
    return b"".join(struct.pack("<q", value) for value in values)


def decode_execution(stdout, returncode):
    if type(stdout) is not str or not re.fullmatch("[0-4][0-9A-F]{16}\n", stdout):
        raise ValueError("Malformed direct ELF result")
    status = int(stdout[0])
    if returncode != status:
        raise ValueError("Direct ELF status/exit code disagreement")
    value = int(stdout[1:17], 16)
    if value >= 1 << 63:
        value -= 1 << 64
    if status and value:
        raise ValueError("Error result must not carry an ambiguous value")
    return {"status": status, "value": value, "accepted": status == 0,
            "verified": False, "semantics": "checked-i64-exact-division-v1"}


def matrix_values(value):
    """Decode common-denominator output without relying on cached mpq values."""
    rows = int(value["rows"])
    columns = int(value["columns"])
    if rows <= 0 or columns <= 0 or rows * columns > 1048576:
        raise ValueError("Matrix output shape")
    denominator = int(value["denominator"])
    numbers = value["numerators"]
    if denominator <= 0 or len(numbers) != rows * columns:
        raise ValueError("Matrix output denominator/size")
    return [Fraction(int(number), denominator) for number in numbers]


def sha256(data):
    return hashlib.sha256(data).hexdigest()
