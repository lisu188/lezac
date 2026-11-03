"""Bounded in-memory endpoints. This module never opens an artifact file."""
import struct

HEADER = struct.Struct('<8sIB3sI')
MEMORY_BYTES = 1048576


def receive(sock):
    def exact(size):
        result = bytearray()
        while len(result) < size:
            block = sock.recv(min(65536, size - len(result)))
            if not block:
                raise ValueError('Truncated in-memory endpoint stream')
            result.extend(block)
        return bytes(result)

    endpoints = []
    for phase in (0, 1):
        magic, call, actual_phase, reserved, size = HEADER.unpack(exact(HEADER.size))
        if (magic, call, actual_phase, reserved, size) != (b'LZMEMS01', 1, phase, b'\0' * 3, MEMORY_BYTES):
            raise ValueError('In-memory endpoint header differs')
        endpoints.append(exact(size))
    if sock.recv(1):
        raise ValueError('Unexpected extra endpoint data')
    return endpoints
