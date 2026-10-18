"""Check the private menu-test server across last-client disconnects."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def inside(expect_retained):
    x11 = ctypes.CDLL('libX11.so.6')
    pointer, word = ctypes.c_void_p, ctypes.c_ulong
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = pointer
    x11.XDefaultRootWindow.argtypes = [pointer]
    x11.XDefaultRootWindow.restype = word
    x11.XInternAtom.argtypes = [pointer, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = word
    x11.XChangeProperty.argtypes = [pointer, word, word, word, ctypes.c_int, ctypes.c_int, pointer, ctypes.c_int]
    x11.XGetWindowProperty.argtypes = [pointer, word, word, ctypes.c_long, ctypes.c_long, ctypes.c_int,
        word, ctypes.POINTER(word), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(word),
        ctypes.POINTER(word), ctypes.POINTER(pointer)]
    x11.XSync.argtypes = [pointer, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [pointer]
    x11.XFree.argtypes = [pointer]
    name = b'LEZAC_PRIVATE_TEST_SERVER_LIFETIME'
    value = b'last-client-boundary-v1'
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Private test display is unavailable')
    try:
        atom = x11.XInternAtom(display, name, 0)
        source = ctypes.create_string_buffer(value)
        x11.XChangeProperty(display, x11.XDefaultRootWindow(display), atom, 31, 8, 0,
                           ctypes.cast(source, pointer), len(value))
        x11.XSync(display, 0)
    finally:
        x11.XCloseDisplay(display)
    # No X client remains during this interval. A default server resets here.
    time.sleep(.25)
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Private display did not reopen after the client boundary')
    data = pointer()
    try:
        atom = x11.XInternAtom(display, name, 1)
        retained = False
        if atom:
            actual_type, count, remaining = word(), word(), word()
            bits = ctypes.c_int()
            result = x11.XGetWindowProperty(display, x11.XDefaultRootWindow(display), atom,
                0, 64, 0, 31, ctypes.byref(actual_type), ctypes.byref(bits), ctypes.byref(count),
                ctypes.byref(remaining), ctypes.byref(data))
            if result != 0:
                raise RuntimeError('Cannot inspect private server lifetime sentinel')
            retained = actual_type.value == 31 and bits.value == 8 and count.value == len(value) and \
                ctypes.string_at(data, count.value) == value
        if retained != expect_retained:
            raise RuntimeError('Private X server lifetime differs: retained=' + str(retained))
        print(json.dumps(dict(retained=retained, expected_retained=expect_retained)))
    finally:
        if data:
            x11.XFree(data)
        x11.XCloseDisplay(display)


def run(xvfb_run, server_args, out):
    out.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='server-lifetime-', dir=out))
    report = dict(status='failed', source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  audio='dummy', private_servers=True, cases=[])
    try:
        for name, arguments, expected in (('retained', server_args, True),
                ('reset-control', '-screen 0 1280x1024x24 -reset', False)):
            command = [xvfb_run, '-a', '-e', str(output / (name + '-server.log')), '-s', arguments,
                       sys.executable, '-S', '-B', str(Path(__file__).resolve()), '--inside', name]
            child = subprocess.Popen(command, env=dict(os.environ, SDL_AUDIODRIVER='dummy'),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                captured, _ = child.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    captured, _ = child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    captured, _ = child.communicate(timeout=5)
                (output / (name + '.log')).write_bytes(captured)
                raise RuntimeError('Owned private-server control timed out')
            (output / (name + '.log')).write_bytes(captured)
            if child.returncode:
                raise RuntimeError('Private-server control failed: ' + name + ': ' + captured.decode(errors='replace'))
            result = json.loads(captured)
            if result != dict(retained=expected, expected_retained=expected):
                raise RuntimeError('Private-server control output differs')
            report['cases'].append(dict(name=name, server_args=arguments, **result))
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('bios_menu_xvfb_lifetime=ok retained=1 reset_control=1 silent=1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', choices=('retained', 'reset-control'))
    parser.add_argument('--xvfb-run')
    parser.add_argument('--server-args')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.inside:
        inside(args.inside == 'retained')
    elif args.xvfb_run and args.server_args and args.out:
        run(args.xvfb_run, args.server_args, args.out)
    else:
        parser.error('Expected private-server launcher, arguments and output directory')
