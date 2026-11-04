"""Bounded, receipt-checked transport for literal map and DAC observations.

This module does not launch a guest or attest where caller-supplied bytes came
from. Original provenance still requires an authenticated observer and receipts.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import struct
import zlib
from typing import Any

from level1_fidelity import EvidenceError, integer, require, strict_json

SCHEMA = 'lezac-literal-map-buffers-v1'
MAX_BLOB_BYTES = 256 * 1024
MAX_DOCUMENT_BYTES = 256 * 1024
BUFFER_NAMES = ('tiles', 'words', 'dac')
ROLES = ('original_runtime', 'synthetic_control')
GZIP_HEADER = bytes.fromhex('1f8b08000000000002ff')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: Any, size: int, label: str) -> bytes:
    require(isinstance(value, str) and len(value) == size * 2 and
            re.fullmatch('[0-9a-f]*', value) is not None, label + ' hex extent differs')
    return bytes.fromhex(value)


def _hashes(value: Any) -> dict[str, str]:
    require(isinstance(value, dict) and set(value) == {'tiles', 'words', 'dac'},
            'literal plane receipt names differ')
    require(all(isinstance(item, str) and re.fullmatch('[0-9a-f]{64}', item)
                for item in value.values()), 'literal plane receipt digest differs')
    return dict(value)


def _layout(ds: bytes) -> tuple[int, int, dict[str, dict[str, int]]]:
    require(type(ds) is bytes and len(ds) == 65536, 'literal map DS extent differs')
    width = struct.unpack_from('<H', ds, 0xC204)[0]
    height = struct.unpack_from('<H', ds, 0x2096)[0] // 8 + 21
    cells = width * height
    require(width > 0 and 0 < cells <= 32768, 'literal map dimensions exceed a far span')
    pointers = {}
    for name, at, length in (('tiles', 0xC1E0, cells), ('words', 0x6612, cells * 2)):
        offset, segment = struct.unpack_from('<HH', ds, at)
        require(0 < segment < 0xA000 and offset + length <= 65536 and
                (segment << 4) + offset + length <= 0xA0000,
                'literal map far pointer differs: ' + name)
        pointers[name] = dict(ds_pointer_offset=at, offset=offset, segment=segment, bytes=length)
    return width, height, pointers


def _metadata(ds: bytes, tick: int, phase: str, role: str,
              plane_sha256: dict[str, str]) -> dict[str, Any]:
    require(integer(tick, 1, 0xFFFFFFFF), 'literal map route tick differs')
    require(phase in ('present', 'post_update'), 'literal map phase differs')
    require(role in ROLES, 'literal map observation role differs')
    hashes = _hashes(plane_sha256)
    width, height, pointers = _layout(ds)
    return dict(schema=SCHEMA, route_tick=tick, phase=phase, role=role,
        native_frame=struct.unpack_from('<H', ds, 0x78C2)[0],
        native_level=ds[0x79B7], rng=struct.unpack_from('<I', ds, 0x1AFE)[0],
        dimensions=[width, height], ds_sha256=digest(ds), pointers=pointers,
        buffers={name: dict(bytes=width * height * (2 if name == 'words' else 1)
                            if name != 'dac' else 768, sha256=hashes[name])
                 for name in ('tiles', 'words', 'dac')},
        dac_source='resident_vga_dac_shadow', full_guest_ram_export=False,
        original_fidelity_claim=False, full_frame_claim=False)


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')


def _compress(document: bytes) -> bytes:
    require(len(document) <= MAX_DOCUMENT_BYTES, 'literal map document exceeds size limit')
    stream = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0, compresslevel=9) as output:
        output.write(document)
    result = stream.getvalue()
    require(len(result) <= MAX_BLOB_BYTES, 'literal map bundle exceeds size limit')
    return result


def pack_literal_map_buffers(state: dict[str, Any], ds: bytes, dac_hex: str, *,
                             tick: int, phase: str, role: str,
                             plane_sha256: dict[str, str]) -> bytes:
    """Pack unchanged buffers already read from one stopped-child instant."""
    metadata = _metadata(ds, tick, phase, role, plane_sha256)
    require(isinstance(state, dict), 'literal map state differs')
    require(integer(state.get('frame'), 0, 65535) and state['frame'] == metadata['native_frame'] and
            integer(state.get('rng'), 0, 0xFFFFFFFF) and state['rng'] == metadata['rng'],
            'literal map state/DS instant differs')
    buffers = {name: _hex(state.get(name), metadata['buffers'][name]['bytes'], name)
               for name in ('tiles', 'words')}
    buffers['dac'] = _hex(dac_hex, 768, 'dac')
    require(all(value <= 63 for value in buffers['dac']), 'literal DAC range differs')
    for name, data in buffers.items():
        require(digest(data) == plane_sha256[name], 'literal plane receipt differs: ' + name)
    packed = _compress(_json(dict(metadata=metadata,
        data_hex={name: data.hex() for name, data in buffers.items()})))
    observed, decoded = unpack_literal_map_buffers(packed, ds=ds, tick=tick, phase=phase,
        role=role, plane_sha256=plane_sha256, blob_sha256=digest(packed))
    require(observed == metadata and decoded == buffers, 'literal map complete pack readback differs')
    return packed


def unpack_literal_map_buffers(blob: bytes, *, ds: bytes, tick: int, phase: str,
                               role: str, plane_sha256: dict[str, str],
                               blob_sha256: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Verify external receipts and the entire bundle before returning literals.

    The digest arguments must come from the separately authenticated observation
    journal, not from metadata inside the bundle being checked.
    """
    require(type(blob) is bytes and 0 < len(blob) <= MAX_BLOB_BYTES, 'literal map bundle extent differs')
    require(isinstance(blob_sha256, str) and re.fullmatch('[0-9a-f]{64}', blob_sha256) is not None and
            digest(blob) == blob_sha256, 'literal map external bundle receipt differs')
    expected = _metadata(ds, tick, phase, role, plane_sha256)
    require(blob.startswith(GZIP_HEADER), 'literal map gzip header differs')
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = decoder.decompress(blob, MAX_DOCUMENT_BYTES + 1)
        require(len(raw) <= MAX_DOCUMENT_BYTES and decoder.eof and
                not decoder.unconsumed_tail and not decoder.unused_data,
                'literal map compressed extent differs')
        document = strict_json(raw.decode('ascii'))
        require(isinstance(document, dict) and set(document) == {'metadata', 'data_hex'},
                'literal map document fields differ')
        metadata, encoded = document['metadata'], document['data_hex']
        require(metadata == expected and _json(metadata) == _json(expected), 'literal map metadata binding differs')
        require(isinstance(encoded, dict) and set(encoded) == set(BUFFER_NAMES), 'literal map buffer names differ')
        buffers = {name: _hex(encoded[name], expected['buffers'][name]['bytes'], name) for name in BUFFER_NAMES}
        require(raw == _json(dict(metadata=expected, data_hex={name: data.hex() for name, data in buffers.items()})),
                'literal map canonical document differs')
    except (OSError, ValueError, RuntimeError, zlib.error) as error:
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError('invalid literal map bundle: ' + str(error)) from error
    for name, data in buffers.items():
        require(len(data) == expected['buffers'][name]['bytes'] and digest(data) == plane_sha256[name],
                'literal map complete buffer differs: ' + name)
    require(all(value <= 63 for value in buffers['dac']), 'literal DAC range differs')
    return metadata, buffers
