"""Keep replay cleanup in its parent while a permitted sibling GDB collects."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess

PR_SET_PTRACER = 0x59616d61


def allow_parent_debugger():
    parent = os.getppid()
    if parent <= 1:
        raise ValueError('Owned replay has no supervising parent')
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(PR_SET_PTRACER, parent, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'Cannot permit the supervising parent debugger')


def collect_guard(command, environment, out):
    result = subprocess.run(command, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=90)
    for name in ('stdout', 'stderr'):
        raw = getattr(result, name)
        if len(raw) > 65536:
            raise ValueError('Collector output exceeded bounded reserve')
        (out / ('collector.' + name)).write_bytes(raw)
    if result.returncode:
        raise RuntimeError('GDB collector exited with code ' + str(result.returncode))
    path = out / 'guard/guard.json'
    if path.stat().st_size > 65536:
        raise ValueError('Collector receipt exceeded bounded reserve')
    raw = path.read_bytes()
    report = json.loads(raw)
    if report.get('status') != 'failure_throw_captured' or report.get('protected_inputs_preserved') is not True:
        raise ValueError('Collector did not preserve a verified failure capture')
    return dict(status=report['status'], bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
