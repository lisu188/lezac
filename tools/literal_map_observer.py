"""Bind a stopped-original observation to its privately retained literal buffers.

The observer and its authenticated journal still establish original provenance.
This adapter performs no guest access and delegates storage to the observer.
"""
from __future__ import annotations

import re
import struct
from typing import Any, Callable

import literal_map_buffers as literal
from level1_fidelity import integer, require

SCHEMA = 'lezac-literal-map-observation-v1'


def _context(boundary: dict[str, Any], ds: bytes) -> dict[str, Any]:
    require(isinstance(boundary, dict) and boundary.get('original_observation') is True,
            'literal boundary is not an original observation')
    require(type(ds) is bytes and len(ds) == 65536, 'literal boundary DS extent differs')
    require(integer(boundary.get('tick'), 1, 0xFFFFFFFF) and
            boundary.get('phase') in ('present', 'post_update') and
            integer(boundary.get('sequence'), 1, 0xFFFFFFFF) and
            integer(boundary.get('level'), 1, 255), 'literal boundary identity differs')
    require(boundary.get('ds_sha256') == literal.digest(ds), 'literal boundary DS receipt differs')
    projection = boundary.get('projection')
    require(isinstance(projection, dict) and isinstance(projection.get('mapped'), dict),
            'literal boundary mapped projection differs')
    mapped = projection['mapped']
    frame, rng = struct.unpack_from('<H', ds, 0x78C2)[0], struct.unpack_from('<I', ds, 0x1AFE)[0]
    require(integer(mapped.get('frame'), 0, 65535) and mapped['frame'] == frame and
            integer(mapped.get('rng'), 0, 0xFFFFFFFF) and mapped['rng'] == rng and
            boundary['level'] == ds[0x79B7], 'literal boundary native instant differs')
    planes = {name: mapped.get(name + '_hex') for name in ('tiles', 'words')}
    require(all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                for value in planes.values()), 'literal boundary map receipts differ')
    return dict(tick=boundary['tick'], phase=boundary['phase'], sequence=boundary['sequence'],
                level=boundary['level'], ds_sha256=boundary['ds_sha256'], frame=frame, rng=rng,
                map_sha256=planes)


def _context_digest(context: dict[str, Any]) -> str:
    import json
    return literal.digest((json.dumps(context, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))


def _receipt(context: dict[str, Any], plane_sha256: dict[str, str], blob_sha256: str,
             blob_bytes: int) -> dict[str, Any]:
    return dict(schema=SCHEMA, context_sha256=_context_digest(context),
        bundle=f"literal-{context['tick']}-{context['phase']}.json.gz",
        bundle_bytes=blob_bytes, bundle_sha256=blob_sha256, plane_sha256=plane_sha256,
        original_fidelity_claim=False, full_frame_claim=False, full_guest_ram_export=False)


def retain_literal_buffers(boundary: dict[str, Any], state: dict[str, Any], ds: bytes,
                           dac_hex: str, write_and_read: Callable[[str, bytes], bytes]) -> dict[str, Any]:
    """Return a receipt only after storage readback matches every encoded byte.

    The caller attaches the returned receipt as boundary['literal_buffers'] before
    publishing that boundary. A failed callback leaves the boundary unchanged.
    """
    context = _context(boundary, ds)
    require('literal_buffers' not in boundary, 'literal boundary already has a buffer receipt')
    require(isinstance(dac_hex, str) and re.fullmatch('[0-9a-f]{1536}', dac_hex) is not None,
            'literal boundary DAC extent differs')
    hashes = dict(context['map_sha256'], dac=literal.digest(bytes.fromhex(dac_hex)))
    blob = literal.pack_literal_map_buffers(state, ds, dac_hex, tick=context['tick'],
        phase=context['phase'], role='original_runtime', plane_sha256=hashes)
    receipt = _receipt(context, hashes, literal.digest(blob), len(blob))
    observed = write_and_read(receipt['bundle'], blob)
    require(type(observed) is bytes and observed == blob, 'literal boundary private readback differs')
    require(_context(boundary, ds) == context and 'literal_buffers' not in boundary,
            'literal boundary changed during private retention')
    return receipt


def read_literal_buffers(boundary: dict[str, Any], ds: bytes, blob: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Read against the separately authenticated boundary, never container claims."""
    context = _context(boundary, ds)
    receipt = boundary.get('literal_buffers')
    require(isinstance(receipt, dict), 'literal boundary buffer receipt missing')
    hashes = receipt.get('plane_sha256')
    require(isinstance(hashes, dict) and set(hashes) == {'tiles', 'words', 'dac'} and
            all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) for value in hashes.values()) and
            {name: hashes[name] for name in ('tiles', 'words')} == context['map_sha256'],
            'literal boundary external plane receipts differ')
    require(type(blob) is bytes and integer(receipt.get('bundle_bytes'), 1, literal.MAX_BLOB_BYTES) and
            len(blob) == receipt['bundle_bytes'] and
            receipt == _receipt(context, hashes, literal.digest(blob), len(blob)),
            'literal boundary receipt binding differs')
    require(all(receipt[name] is False for name in
                ('original_fidelity_claim', 'full_frame_claim', 'full_guest_ram_export')),
            'literal boundary claim flags differ')
    return literal.unpack_literal_map_buffers(blob, ds=ds, tick=context['tick'], phase=context['phase'],
        role='original_runtime', plane_sha256=hashes, blob_sha256=receipt['bundle_sha256'])
