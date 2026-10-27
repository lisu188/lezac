"""Retain actual REA/Ghidra observations for the original post-render prefix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess

EXE_SHA='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
INSTRUCTIONS=(0x7a57,0x7a7b,0x7aa7,0x7b13,0x7b28,0x7b5c,0x7c29,0x7c3d,0x7c54,0x7e8a,0x7ebb)
CALLS={0x7b28:0x12f9f,0x7b5c:0x1a5a8,0x7c29:0x106ab}
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()

def run(repo,out,rea_script,ghidra,java):
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    binary=repo/'LEZAC.EXE'
    if sha(binary)!=EXE_SHA:raise ValueError('Canonical MZ differs')
    package=rea_script.parent.parent/'package.json'
    if json.loads(package.read_text())['version']!='6.7.0':raise ValueError('REA package version differs')
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():raise ValueError('Use fresh RAM-only output')
    out.mkdir()
    for name in ('home','tmp','cache'):(out/name).mkdir()
    env=dict(os.environ,HOME=str(out/'home'),TMPDIR=str(out/'tmp'),TMP=str(out/'tmp'),TEMP=str(out/'tmp'),
        XDG_CACHE_HOME=str(out/'cache'),GHIDRA_INSTALL_DIR=str(ghidra),JAVA_HOME=str(java),
        REA_ANALYSIS_PROVIDER='ghidra',SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy')
    report=dict(status='failed',target_sha256=EXE_SHA,rea_version='6.7.0',host='WSL Ubuntu',calls=[],
        source_sha256=sha(Path(__file__)),guest_execution=False,guest_ram_exported=False,core_dump_limit=0)
    process=None;opened=False;identifier=0
    def expired(*unused):raise TimeoutError('REA audit deadline elapsed')
    previous=signal.signal(signal.SIGALRM,expired);signal.alarm(900)
    with (out/'server.stderr').open('xb') as stderr:
        try:
            process=subprocess.Popen(['node',str(rea_script),'--mcp'],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=stderr,text=True,env=env)
            def request(method,params):
                nonlocal identifier
                identifier+=1
                process.stdin.write(json.dumps(dict(jsonrpc='2.0',id=identifier,method=method,params=params))+'\n')
                process.stdin.flush()
                while True:
                    raw=process.stdout.readline()
                    if not raw:raise RuntimeError('REA transport closed')
                    value=json.loads(raw)
                    if value.get('id')==identifier:return value
            def call(name,arguments,label):
                response=request('tools/call',dict(name=name,arguments=arguments))
                (out/(label+'.json')).write_text(json.dumps(response,indent=2)+'\n')
                result=response.get('result',{})
                failed=bool(response.get('error') or result.get('isError'))
                report['calls'].append(dict(name=name,label=label,is_error=failed))
                print('rea_prefix_call='+label+' error='+str(failed),flush=True)
                if failed:raise RuntimeError('REA call failed: '+label)
                return result.get('structuredContent',{})
            initialize=request('initialize',dict(protocolVersion='2024-11-05',capabilities={},
                clientInfo=dict(name='lezac-prefix-recovery',version='1')))
            (out/'initialize.json').write_text(json.dumps(initialize,indent=2)+'\n')
            process.stdin.write(json.dumps(dict(jsonrpc='2.0',method='notifications/initialized'))+'\n');process.stdin.flush()
            call('open_binary',dict(path=str(binary),provider_id='ghidra'),'open');opened=True
            image=call('inspect_native_load_image',{},'load-image')
            if image['normalized_result']['status']!='verified' or image['provider']['version']!='12.1.4':
                raise ValueError('Ghidra image/provider verification differs')
            for offset in INSTRUCTIONS:
                value=call('inspect_native_instruction',dict(address=hex(0x10000+offset)),f'instruction-{offset:04x}')
                if value['normalized_result']['status']!='decoded':raise ValueError('Instruction boundary not decoded')
            for offset,target in CALLS.items():
                value=call('resolve_native_call_targets',dict(address=hex(0x10000+offset)),f'call-{offset:04x}')
                result=value['normalized_result']
                if result['status']!='direct' or [r['address'] for r in result['targets']]!=[hex(target)]:
                    raise ValueError('Original direct call target differs')
            for offset in (0x2f9f,0x6ab):
                value=call('procedure_pseudo_code',dict(procedure=hex(0x10000+offset)),f'decompile-{offset:04x}')
                if not isinstance(value['normalized_result'],str):raise ValueError('Missing advisory decompilation')
            call('close_binary',{},'close');opened=False
            if sha(binary)!=EXE_SHA or sha(Path(__file__))!=report['source_sha256']:raise ValueError('Audit input changed')
            report.update(status='completed',target_preserved=True,session_closed=True,provider=image['provider'])
        except Exception as error:
            report['error']=str(error)
            raise
        finally:
            if process is not None:
                if opened and process.poll() is None:
                    signal.alarm(30)
                    try:call('close_binary',{},'failure-close')
                    except Exception as error:report['close_error']=str(error)
                process.stdin.close()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=15)
                report['server_exit_code']=process.returncode
            signal.alarm(0);signal.signal(signal.SIGALRM,previous)
            (out/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','out','rea-script','ghidra','java-home'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    run(args.repo.resolve(),args.out,args.rea_script.resolve(),args.ghidra.resolve(),args.java_home.resolve())
