"""Retain bounded oracle failure metadata without exporting guest RAM."""
import hashlib
import json

MAX_BYTES=65536
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def _bounded(value,limit):
    raw=json.dumps(value,sort_keys=True,ensure_ascii=True).encode('ascii')
    return value if len(raw)<=limit else dict(truncated=True,bytes=len(raw),sha256=sha(raw))


def _memory(raw):
    return None if raw is None else dict(bytes=len(raw),sha256=sha(raw))


def write_failure(out,error,*,case,profile,sources,initial=None,endpoints=(),current=None,
                  trace=(),writes=(),projection=None):
    report=dict(status='failed',case=case,error_type=type(error).__name__,error=str(error)[:1024],
        profile=_bounded(profile,8192),source_sha256=_bounded(sources,8192),
        initial=_memory(initial),endpoints=[],current=None,
        trace_tail=[list(row[:14]) for row in trace[-16:]],
        write_tail=[list(row[:3]) for row in writes[-16:]],
        projection=_memory(projection),guest_memory_bytes_written=0)
    for registers,memory,fault in endpoints[-2:]:
        report['endpoints'].append(dict(registers=list(registers[:14]),memory=_memory(memory),fault=fault))
    if current is not None:
        try:
            report['current']=_memory(current.mem_read(0,1048576))
        except Exception as unavailable:
            report['current']=dict(unavailable=str(unavailable)[:256])
    raw=(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode('ascii')
    if len(raw)>MAX_BYTES:
        raise ValueError('Oracle failure metadata exceeds bounded reserve')
    with (out/'failed.json').open('xb') as stream:
        stream.write(raw)
    return report
