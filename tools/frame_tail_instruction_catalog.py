"""Check tail instruction boundaries and structural IRQ progress catalogs."""
from collections import defaultdict, deque
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BEGIN='    // BEGIN CHECKED TAIL INSTRUCTION CATALOG\n'
END='    // END CHECKED TAIL INSTRUCTION CATALOG\n'
INPUTS=('src/core/frame_tail.hpp','src/core/frame_spawner.hpp',
    'src/core/actor_terrain.hpp','src/core/timer_irq.hpp')


def cases(text):
    labels=re.findall(r'\bcase\s+([^:]+):',text)
    if any(not re.fullmatch(r'(0[xX][0-9a-fA-F]+|[0-9]+)',value.strip()) for value in labels):
        raise ValueError('Instruction catalog requires numeric dispatch labels')
    return {int(value.strip(),0) for value in labels}


def irq_blocks(text):
    bios=text.split('if (state_.biosWrapper && r.cs == state_.biosSegment) {',1)[1]
    bios,crt=bios.split('if (r.cs == state_.crtSegment) {',1)
    crt,game=crt.split('if (r.cs != state_.gameSegment)',1)
    result={}
    for domain,section in (('bios',bios),('crt',crt),('game',game)):
        section=section.split('default:',1)[0]
        matches=list(re.finditer(r'\bcase\s+(0[xX][0-9a-fA-F]+)\s*:',section))
        if len(matches)!=len(cases(section)):
            raise ValueError('Unrecognized timer dispatch labels')
        for n,match in enumerate(matches):
            ip=int(match[1],16)
            key=(domain,ip)
            if key in result:
                raise ValueError('Duplicate timer instruction')
            result[key]=section[match.end():matches[n+1].start() if n+1<len(matches) else len(section)]
    return result


def irq_progress(text):
    blocks=irq_blocks(text)
    pending=deque([('bios',0xfea5,(),0)])
    seen=set()
    counts=defaultdict(set)
    while pending:
        domain,ip,stack,count=pending.popleft()
        state=(domain,ip,stack,count)
        if state in seen:
            continue
        seen.add(state)
        if count>=128 or len(seen)>100000:
            raise ValueError('Timer control-flow reserve exceeded')
        body=blocks[(domain,ip)]
        counts[(domain,ip)].add(count)
        if domain=='bios' and ip==0xfeb6:
            if stack:
                raise ValueError('Timer terminal has pending calls')
            continue
        if domain=='bios' and ip==0xfeac:
            successors=[('game',0xfbe,stack+(('bios',0xfeae),))]
        elif (domain=='game' and ip==0x1090) or 'farReturn(bus,' in body:
            if not stack:
                raise ValueError('Timer return lacks a caller')
            target,next_ip=stack[-1]
            successors=[(target,next_ip,stack[:-1])]
        elif 'farCall(bus,' in body:
            call=re.search(r'farCall\(bus, (0x[0-9a-f]+), (0x[0-9a-f]+)\)',body)
            if not call:
                raise ValueError('Unrecognized timer call')
            successors=[('crt',int(call[1],16),stack+((domain,int(call[2],16)),))]
        else:
            assignment=re.search(r'r\.ip\s*=\s*([^;]+);',body)
            if assignment:
                targets=re.findall(r'0x[0-9a-f]+',assignment[1])
                if len(targets) not in (1,2):
                    raise ValueError('Unrecognized timer branch')
                successors=[(domain,int(target,16),stack) for target in targets]
            elif '++r.ip' in body:
                successors=[(domain,ip+1,stack)]
            else:
                raise ValueError('Unrecognized timer instruction control flow')
        for target,next_ip,frames in successors:
            if (target,next_ip) not in blocks:
                raise ValueError('Timer control flow left its instruction catalog')
            pending.append((target,next_ip,frames,count+1))
    if set(counts)!=set(blocks) or min(counts[('bios',0xfeb6)])!=35:
        raise ValueError('Timer progress coverage differs')
    return counts


def completion_model(lengths):
    minimum=min(lengths)
    extras=sorted({length-minimum for length in lengths if length>minimum})
    period=max(extras)
    if not 0<period<=128:
        raise ValueError('Timer completion period exceeds reserve')
    coins=[0]+[65535]*4096
    for value in range(1,len(coins)):
        coins[value]=min((coins[value-extra]+1 for extra in extras
            if extra<=value and coins[value-extra]!=65535),default=65535)
    # One full period of recurrence proves every later reduction by induction.
    cutoff=next((start for start in range(len(coins)-2*period)
        if all(coins[n]!=65535 and coins[n+period]==coins[n]+1
            for n in range(start,start+period))),None)
    if cutoff is None or cutoff+period>1024:
        raise ValueError('Timer completion table exceeds reserve')
    return minimum,period,cutoff,coins[:cutoff+period]


def render(sources):
    instruction=sources[INPUTS[0]].split('    void instruction(',1)[1]
    graphics,main=instruction.split('        switch (r.ip) {',1)[1].split('        switch (r.ip) {',1)
    game=cases(main)|{ip for ip in cases(sources[INPUTS[2]]) if 0x370e<=ip<=0x3a53}
    library={ip for ip in cases(sources[INPUTS[1]]) if
        0x4df<=ip<=0x4f4 or 0x13a8<=ip<=0x13bb or 0x13f7<=ip<=0x142c}
    video=cases(graphics)
    counts=irq_progress(sources[INPUTS[3]])
    minimum,period,cutoff,coins=completion_model({n+1 for n in counts[('bios',0xfeb6)]})
    lines=[BEGIN.rstrip(),'    static bool completedTimerWork(uint64_t instructions,uint64_t deliveries) {',
        '        if (deliveries>instructions/'+str(minimum)+'u) return false;',
        '        const auto extra=instructions-deliveries*'+str(minimum)+'u;',
        '        // Shortest IRQs pad the delivery count; the table counts nonzero excesses.',
        '        constexpr std::array<uint16_t,'+str(len(coins))+'> coins{']
    for at in range(0,len(coins),16):
        lines.append('            '+','.join(map(str,coins[at:at+16]))+',')
    lines.extend(['        };','        if (extra<'+str(cutoff)+'u) {',
        '            const auto count=coins[static_cast<size_t>(extra)];',
        '            return count!=0xffffu && count<=deliveries;',
        '        }',
        '        const auto cycles=(extra-'+str(cutoff)+'u)/'+str(period)+'u;',
        '        const auto index='+str(cutoff)+'u+(extra-'+str(cutoff)+'u)%'+str(period)+'u;',
        '        return cycles+coins[static_cast<size_t>(index)]<=deliveries;',
        '    }','    bool foregroundBoundary() const {',
        '        const auto& r=state_.registers;'])
    for condition,addresses in (('r.cs==state_.gameSegment',game),
            ('r.cs==library()',library),('r.cs==graphics()',video)):
        values=sorted(addresses)
        lines.extend(['        if ('+condition+') {',
            '            constexpr std::array<uint16_t,'+str(len(values))+'> ips{'])
        for at in range(0,len(values),10):
            lines.append('                '+','.join('0x'+format(ip,'04x') for ip in values[at:at+10])+',')
        lines.extend(['            };','            return std::binary_search(ips.begin(),ips.end(),r.ip);','        }'])
    lines.extend(['        return false;','    }',
        '    bool timerProgress(const TimerIrqSnapshot& irq) const {',
        '        struct Point { uint16_t ip;uint64_t low,high; };',
        '        const auto count=irq.dispatchedInstructions;',
        '        if (count>=128) return false;',
        '        const auto matches=[&](const auto& points) {',
        '            const auto at=std::lower_bound(points.begin(),points.end(),irq.registers.ip,',
        '                [](const Point& point,uint16_t ip) { return point.ip<ip; });',
        '            return at!=points.end() && at->ip==irq.registers.ip &&',
        '                ((count<64 ? at->low>>count : at->high>>(count-64))&1u)!=0;',
        '        };'])
    for domain,condition in (('bios','irq.registers.cs==irq.biosSegment'),
            ('game','irq.registers.cs==state_.gameSegment'),('crt','irq.registers.cs==irq.crtSegment')):
        addresses=sorted(ip for d,ip in counts if d==domain)
        lines.extend(['        if ('+condition+') {',
            '            constexpr std::array<Point,'+str(len(addresses))+'> points{{'])
        for ip in addresses:
            mask=sum(1<<n for n in counts[(domain,ip)])
            lines.append('                {0x'+format(ip,'04x')+',0x'+format(mask&((1<<64)-1),'x')+
                'ull,0x'+format(mask>>64,'x')+'ull},')
        lines.extend(['            }};','            return matches(points);','        }'])
    lines.extend(['        return false;','    }',END.rstrip()])
    return '\n'.join(lines)+'\n'


def check_sources(sources):
    text=sources[INPUTS[0]]
    if text.count(BEGIN)!=1 or text.count(END)!=1:
        raise ValueError('Tail instruction catalog markers differ')
    actual=BEGIN+text.split(BEGIN,1)[1].split(END,1)[0]+END
    if actual!=render(sources):
        raise ValueError('Tail instruction or timer progress catalog is stale')
    return True


def check(root=ROOT):
    return check_sources({name:(root/name).read_text(encoding='utf-8') for name in INPUTS})


if __name__=='__main__':
    check()
    print('frame_tail_instruction_catalog=ok')
