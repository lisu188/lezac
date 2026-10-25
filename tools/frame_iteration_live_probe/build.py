"""Derive a four-frame stream-only observer without changing frozen producers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from frame_active_live_probe.rebuild import rebuild

BASE_PINS = ('c23ff346b5db1c5c2729863ae9ee3036bfbc626656229617a2d362b123a7fb15',
             '5b654f96f7b248e3c4e4b0ba4e9dc9993f3ae8020fbd3a0556e202c58e98649e')
VGA_PINS = ('8b0af235824c28351e25bfeb0a38f8bfccf650ba53f6b8248b5bb4657fbf64e6',
            '5f1e164d4e6d5ec6cf0e8a81ac0fd9eac9d976f466bdfa8634553aabacec08ec')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

TAIL = r'''
    if (!p.frame_waiting && code == p.code && ip == 0x7903) {
        const PhysPt data = (PhysPt)p.data * 16;
        LezacDeviceObservation d = {};LezacReadDeviceClock(d);
        LezacClockObservation c = {};LezacReadPicClock(c);
        const unsigned frame=mem_readw(data+0x78c2);
        if (p.full_windows || frame<4 || frame>10 || !mem_readb(data+0x79e6) || mem_readb(data+0x79c4)) return;
        if (d.values[17] || d.values[18] || d.values[19] || d.values[20] || c.queue_overflow) return;
        for (unsigned i=0;i<c.queue_count;++i)
            if(c.queue[i].kind<1 || c.queue[i].kind>7 || c.queue[i].kind==2) return;
        p.call=1;p.full_windows=1;p.measurements=0;
        p.windowed=p.frame_waiting=true;
        p.irq_in_window=p.render_seen=p.render_irq=p.post_render_seen=false;
        p.entry_game_vector=true;p.keyboard_class=0;p.keyboard_entry=ip;
        p.stack_ss=SegValue(ss);p.stack_base=static_cast<Bit16u>(reg_sp-80);
        p.return_cs=p.code;p.return_ip=0x7903;p.remaining=2000000;
        if (!LezacStreamMemory("initial")) {
            gzprintf(p.output,"stream_failed\n");gzclose(p.output);p.output=0;return;
        }
        LezacDosTimeEmit("keyboard_enter");
    }
    if (!p.frame_waiting) return;
    if (p.remaining!=2000000 && code==p.code && ip==0x7903 && ++p.measurements==4) {
        if (!LezacStreamMemory("final")) {
            gzprintf(p.output,"stream_failed\n");gzclose(p.output);p.output=0;return;
        }
        p.target_completed=true;LezacDosTimeEmit("keyboard_return");
        gzflush(p.output,Z_SYNC_FLUSH);p.frame_waiting=false;
        const char* path=std::getenv("LEZAC_FRAME_FOREGROUND_TARGET");
        if (path) {FILE* marker=fopen(path,"wx");if(marker){fprintf(marker,"1\n");fclose(marker);}}
        return;
    }
    if (code==p.code && ip==0x7a13) {p.render_seen=true;p.post_render_seen=false;}
    if (code==p.code && ip==0x7a57) p.post_render_seen=true;
    if (code==0xf000 && ip==0xfea5) {
        p.irq_in_window=true;
        if(p.render_seen && !p.post_render_seen) p.render_irq=true;
    }
    if (!p.remaining) {
        LezacDosTimeEmit("window_exhausted");p.frame_waiting=false;return;
    }
    LezacDosTimeEmit("instruction");--p.remaining;
}
'''


def frozen_text(path, pins):
    if sha(path) not in pins:
        raise ValueError('Frozen observer source changed: ' + str(path))
    return path.read_text()


def observer_source():
    base = ROOT / 'tools/frame_active_live_probe/lezac_work_probe.h'
    source = frozen_text(base, BASE_PINS)
    start = source.index('inline bool LezacActiveMemory(')
    end = source.index('inline std::vector<std::string> lezac_active_previous;', start)
    source = source[:start] + '#include "memory_stream.h"\n\n' + source[end:]
    source = source.replace('p.records >= 1000000', 'p.records >= 2000002')
    start = source.index('    if (!p.frame_waiting && code == p.code && ip == 0x7903) {')
    return source[:start] + TAIL


def build(host, retain):
    host = host.resolve(strict=True)
    retain = retain.resolve()
    previous = json.loads((host / 'build.json').read_bytes())
    if previous['schema'] == 'lezac-iteration-stream-observer-v1':
        if not host.is_relative_to(Path('/dev/shm')) or not retain.is_relative_to(Path('/dev/shm')) or retain.exists():
            raise ValueError('Use an owned RAM host and fresh RAM retention directory')
        root = host / 'dosbox-0.74-3'
        if previous['status'] != 'built' or previous['host_sha256'] != sha(root / 'src/dosbox'):
            raise ValueError('Previous stream observer differs')
        for name, digest in {**previous['compiled_source_hashes'], **previous['release_generated_hashes']}.items():
            if sha(root / name) != digest:
                raise ValueError('Previous stream compiler input differs: ' + name)
        if shutil.disk_usage('/dev/shm').free < 512 * 1024**2:
            raise ValueError('RAM reserve is insufficient')
        retain.mkdir()
        for source, name in ((root / 'src/dosbox', 'dosbox'), (host / 'build.json', 'build.json'),
                             (root / 'src/cpu/lezac_work_probe.h', 'lezac_work_probe.h'),
                             (root / 'src/cpu/memory_stream.h', 'memory_stream.h'),
                             (root / 'src/cpu/vga_frame_observation.inc', 'vga_frame_observation.inc')):
            shutil.copyfile(source, retain / name)
            if sha(source) != sha(retain / name):
                raise ValueError('Previous stream retention differs')
    else:
        rebuild(host, retain)
    root = host.resolve(strict=True) / 'dosbox-0.74-3'
    record_path = host / 'build.json'
    record = json.loads(record_path.read_bytes())
    record.update(schema='lezac-iteration-stream-observer-v1', status='building', build_exit=None,
                  frozen_active_probe_sha256=sha(ROOT / 'tools/frame_active_live_probe/lezac_work_probe.h'),
                  frozen_active_probe_lf_sha256=BASE_PINS[0], full_ram_artifacts=0,
                  memory_transport='inherited AF_UNIX SOCK_STREAM, two in-memory 1 MiB endpoints',
                  iteration_builder_sha256=sha(Path(__file__)))
    record['previous_stream_build_sha256'] = sha(retain / 'build.json')
    try:
        (root / 'src/cpu/lezac_work_probe.h').write_text(observer_source())
        helper = Path(__file__).with_name('memory_stream.h')
        shutil.copyfile(helper, root / 'src/cpu/memory_stream.h')
        fragment = ROOT / 'tools/frame_active_live_probe/vga_frame_observation.inc'
        vga_source = frozen_text(fragment, VGA_PINS).replace('!vga.svga.bank_write_full;',
            '!vga.svga.bank_write_full && vga.dac.pel_mask==0xff && vga.dac.bits==6;')
        (root / 'src/cpu/vga_frame_observation.inc').write_text(vga_source)
        record.update(frozen_active_vga_fragment_sha256=sha(fragment),
                      frozen_active_vga_fragment_lf_sha256=VGA_PINS[0],
                      active_vga_fragment_sha256=sha(root / 'src/cpu/vga_frame_observation.inc'))
        record['dac_profile'] = 'observed six-bit DAC, pel mask 255 at both endpoints; all intervening opcodes checked'
        inputs = {str(p.relative_to(root)): sha(p) for parent in ('src', 'include')
                  for p in (root / parent).rglob('*') if p.is_file() and p.suffix in ('.cpp', '.h', '.inc')}
        result = subprocess.run(['make', '-j2'], cwd=root, env=record['build_environment'],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
        (retain / 'iteration-build.log').write_bytes(result.stdout)
        record['build_exit'] = result.returncode
        result.check_returncode()
        if any(sha(root / name) != digest for name, digest in {**inputs, **record['release_generated_hashes']}.items()):
            raise ValueError('Observer source changed during build')
        record.update(status='built', compiled_source_hashes=inputs,
                      probe_sha256=sha(root / 'src/cpu/lezac_work_probe.h'),
                      memory_stream_sha256=sha(helper), host_sha256=sha(root / 'src/dosbox'))
    except BaseException as error:
        record.update(status='failed', error=repr(error))
        raise
    finally:
        record_path.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: record[key] for key in ('status', 'host_sha256', 'full_ram_artifacts')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--retain', type=Path, required=True)
    args = parser.parse_args()
    build(args.host, args.retain)
