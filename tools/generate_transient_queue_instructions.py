"""Transcribe pinned 16-bit queue operands into explicit C++ instruction cases."""
import argparse
import hashlib
from pathlib import Path
import re
import struct

import capstone
from capstone.x86 import X86_OP_REG, X86_OP_IMM, X86_OP_MEM

EXE_SHA='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
CUTS=((0x3a7e,0x3eda),(0x45fa,0x4d3c))
BYTE_REGS={'al':('ax',0),'ah':('ax',8),'bl':('bx',0),'bh':('bx',8),
           'cl':('cx',0),'ch':('cx',8),'dl':('dx',0),'dh':('dx',8)}

def stack_catalog(md,body):
    profiles=[];calls={};summaries={};active=set()
    delegated={(0,0x3eda):2,(0,0x452a):6,(0,0x458d):6,(0x920,0x945):4}
    # These existing Real48 owners use BP as arithmetic scratch and a data-dependent stack.
    delegated.update({(0x920,pc):4 for pc in (0xee9,0xefb,0xf01,0xf0b,0xf0f,0xf13,0x1021,0x1034)})
    def visit(entry):
        if entry in summaries:
            return summaries[entry]
        if entry in delegated:
            return delegated[entry],(0,0)
        if entry in active:
            raise ValueError('Recursive queue call graph')
        active.add(entry);segment,start=entry
        todo=[(start,0,(0,0),())];seen={};returns=set()
        while todo:
            pc,sp,bp,saved=todo.pop();state=(sp,bp,saved)
            if (segment,pc)==(0x920,0xe2):
                continue
            if pc in seen:
                if seen[pc]!=state:
                    raise ValueError('Ambiguous queue stack profile '+str((entry,hex(pc),seen[pc],state)))
                continue
            seen[pc]=state
            ins=next(md.disasm(body[segment*16+pc:segment*16+pc+15],pc,count=1))
            op=ins.operands;m=ins.mnemonic;n=pc+ins.size;stack=dict(saved)
            profiles.append((segment,start,pc,sp,*bp))
            reg=lambda operand:md.reg_name(operand.reg) if operand.type==X86_OP_REG else ''
            def push(value):
                nonlocal sp
                sp-=2
                if value[0]!=2:
                    stack[sp]=value
                else:
                    stack.pop(sp,None)
            def pop():
                nonlocal sp
                value=stack.pop(sp,(2,0));sp+=2;return value
            if m in ('push','pushf'):
                push(bp if reg(op[0])=='bp' else (2,0))
            elif m in ('pop','popf'):
                value=pop()
                if reg(op[0])=='bp': bp=value
            elif m=='leave':
                if bp[0]!=1: raise ValueError('Unknown LEAVE stack base')
                sp=bp[1];bp=pop()
            elif m=='mov' and reg(op[0])=='bp':
                bp=(1,sp) if reg(op[1])=='sp' else (2,0)
            elif m=='mov' and reg(op[0])=='sp':
                if reg(op[1])!='bp' or bp[0]!=1: raise ValueError('Unknown MOV stack base')
                sp=bp[1]
            elif m in ('add','sub') and reg(op[0])=='sp':
                if op[1].type!=X86_OP_IMM: raise ValueError('Dynamic queue stack arithmetic')
                sp+=op[1].imm*(1 if m=='add' else -1)
            elif op and reg(op[0])=='bp' and m not in ('cmp','test'):
                bp=(2,0)
            if m in ('call','lcall'):
                target=(segment,op[0].imm) if m=='call' else tuple(o.imm for o in op)
                width=2 if m=='call' else 4
                calls[(segment,pc)]=(target[0],target[1],n,width)
                delta,result_bp=visit(target);sp+=delta-width
                if result_bp[0]!=0: bp=(2,0)
            elif m.startswith('ret'):
                returns.add((sp+(4 if m=='retf' else 2)+(op[0].imm if op else 0),bp));continue
            next_state=(sp,bp,tuple(sorted((k,v) for k,v in stack.items() if k>=sp)))
            if m=='jmp':
                if op[0].type!=X86_OP_IMM: raise ValueError('Indirect queue branch')
                todo.append((op[0].imm,*next_state));continue
            todo.append((n,*next_state))
            if m.startswith('j') or m=='loop': todo.append((op[0].imm,*next_state))
        if len(returns)!=1:
            raise ValueError('Queue return stack contract differs '+str((entry,returns)))
        summaries[entry]=returns.pop();active.remove(entry);return summaries[entry]
    visit((0,0x45fa))
    rows='\n'.join('    {'+','.join(str(v) for v in row)+'},' for row in sorted(profiles))
    call_rows='\n'.join('    {'+','.join(str(v) for v in (*key,*value))+'},' for key,value in sorted(calls.items()))
    return '''
struct TransientQueueStackProfile {uint16_t segment,entry,ip;int16_t sp;uint16_t bpKind;int16_t bp;};
inline constexpr std::array<TransientQueueStackProfile,PROFILE_COUNT> kTransientStackProfiles{{
PROFILE_ROWS
}};
struct TransientQueueCall {uint16_t segment,ip,targetSegment,target,next,width;};
inline constexpr std::array<TransientQueueCall,CALL_COUNT> kTransientCalls{{
CALL_ROWS
}};
'''.replace('PROFILE_COUNT',str(len(profiles))).replace('PROFILE_ROWS',rows).replace('CALL_COUNT',str(len(calls))).replace('CALL_ROWS',call_rows)

def generate(root,out):
    raw=(root/'LEZAC.EXE').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXE_SHA or capstone.__version__!='5.0.3':
        raise ValueError('Queue transcription inputs differ')
    mz=struct.unpack_from('<14H',raw);body=raw[mz[4]*16:]
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);md.detail=True
    instructions=[]
    for lo,hi in CUTS:
        rows=list(md.disasm(body[lo:hi],lo))
        if not rows or rows[0].address!=lo or rows[-1].address+rows[-1].size!=hi:
            raise ValueError('Incomplete queue decode')
        instructions.extend(rows)
    def name(reg):
        return md.reg_name(reg)
    def memory(op):
        m=op.mem
        segment=name(m.segment) if m.segment else 'ss' if name(m.base)=='bp' else 'ds'
        terms=[]
        for reg,scale in ((m.base,1),(m.index,m.scale)):
            if reg:
                terms.append('r.'+name(reg)+(('*'+str(scale)+'u') if scale!=1 else ''))
        terms.append(hex(m.disp&65535)+'u')
        return 'r.'+segment,'static_cast<uint16_t>('+ '+'.join(terms)+')'
    def get(op):
        if op.type==X86_OP_REG:
            reg=name(op.reg)
            if reg in BYTE_REGS:
                word,shift=BYTE_REGS[reg]
                return '(r.'+word+('>>8' if shift else '&255u')+')'
            return 'r.'+reg
        if op.type==X86_OP_IMM:
            return hex(op.imm&((1<<(8*op.size))-1))+'u'
        if op.type==X86_OP_MEM and op.size in (1,2):
            segment,offset=memory(op)
            return 'bus.read'+('Byte' if op.size==1 else 'Word')+'('+segment+','+offset+')'
        raise ValueError('Unsupported queue operand')
    def put(op,value):
        if op.type==X86_OP_REG:
            reg=name(op.reg)
            if reg in BYTE_REGS:
                word,shift=BYTE_REGS[reg]
                v='(('+value+')&255u)'
                return 'r.'+word+'=static_cast<uint16_t>((r.'+word+('&255u)|('+v+'<<8));' if shift else '&0xff00u)|'+v+');')
            return 'r.'+reg+'=static_cast<uint16_t>('+value+');'
        if op.type==X86_OP_MEM and op.size in (1,2):
            segment,offset=memory(op)
            return 'bus.write'+('Byte' if op.size==1 else 'Word')+'('+segment+','+offset+','+\
                'static_cast<'+('uint8_t' if op.size==1 else 'uint16_t')+'>('+value+'));'
        raise ValueError('Unsupported queue destination')
    conditions={'je':'flag(0x40)','jne':'!flag(0x40)','ja':'!flag(1)&&!flag(0x40)',
        'jae':'!flag(1)','jb':'flag(1)','jbe':'flag(1)||flag(0x40)',
        'jge':'!less()','jle':'flag(0x40)||less()'}
    cases=[]
    for ins in instructions:
        op=ins.operands;m=ins.mnemonic;n=hex(ins.address+ins.size)
        tail='r.ip='+n+';'
        # Raw 98/99 are CBW/CWD in this pinned 16-bit body, regardless of alias spelling.
        if bytes(ins.bytes)==b'\x98':
            code='r.ax=static_cast<uint16_t>((r.ax&255u)|((r.ax&128u) ? 0xff00u : 0u));'+tail
        elif bytes(ins.bytes)==b'\x99':
            code='r.dx=r.ax&0x8000u ? 65535 : 0;'+tail
        elif m=='mov':
            code=put(op[0],get(op[1]))+tail
        elif m in ('add','sub','adc','sbb','cmp'):
            value='arithmetic('+get(op[0])+','+get(op[1])+','+str(m in ('sub','sbb','cmp')).lower()+','+str(op[0].size==1).lower()+','+str(m in ('adc','sbb')).lower()+')'
            code=(value+';' if m=='cmp' else put(op[0],value))+tail
        elif m in ('and','or','xor','test'):
            symbol={'and':'&','or':'|','xor':'^','test':'&'}[m]
            value='logic('+get(op[0])+symbol+get(op[1])+','+str(op[0].size==1).lower()+')'
            code=(value+';' if m=='test' else put(op[0],value))+tail
        elif m in ('inc','dec'):
            code=put(op[0],'increment('+get(op[0])+','+str(m=='dec').lower()+','+str(op[0].size==1).lower()+')')+tail
        elif m in ('shl','shr'):
            code=put(op[0],'shift('+get(op[0])+','+get(op[1])+','+str(m=='shr').lower()+')')+tail
        elif m=='neg':
            code=put(op[0],'arithmetic(0,'+get(op[0])+',true)')+tail
        elif m=='push':
            code='push(static_cast<uint16_t>('+get(op[0])+'));'+tail
        elif m=='pop':
            code=put(op[0],'pop()')+tail
        elif m=='lea':
            code=put(op[0],memory(op[1])[1])+tail
        elif m=='les':
            segment,offset=memory(op[1])
            code='{ const auto s='+segment+',o='+offset+';const auto value=bus.readWord(s,o);const auto segment=bus.readWord(s,static_cast<uint16_t>(o+2u));'+put(op[0],'value')+'r.es=segment;'+tail+' }'
        elif m=='mul':
            code='multiply(static_cast<uint16_t>('+get(op[0])+'));'+tail
        elif m=='imul' and len(op)==3:
            code=put(op[0],'signedMultiply(static_cast<uint16_t>('+get(op[1])+'),std::bit_cast<int16_t>(static_cast<uint16_t>('+get(op[2])+')))')+tail
        elif m in ('div','idiv'):
            code=('signedDivide' if m=='idiv' else 'divide')+'(static_cast<uint16_t>('+get(op[0])+'));'+tail
        elif m=='xchg':
            code='{ const auto temporary=static_cast<uint16_t>('+get(op[0])+');'+put(op[0],get(op[1]))+put(op[1],'temporary')+tail+' }'
        elif m=='call':
            code='push('+n+');r.ip='+get(op[0])+';'
        elif m=='lcall':
            if ins.size!=5 or op[0].imm!=0x920 or not 0<=op[1].imm<=65535:
                raise ValueError('Unexpected queue far-call profile')
            code='push(r.cs);push('+n+');r.cs=static_cast<uint16_t>(game+0x920);r.ip='+hex(op[1].imm)+';'
        elif m=='jmp':
            code='r.ip='+get(op[0])+';'
        elif m in conditions:
            code='r.ip=('+conditions[m]+') ? '+get(op[0])+' : '+n+';'
        elif m=='loop':
            code='r.cx=static_cast<uint16_t>(r.cx-1u);r.ip=r.cx ? '+get(op[0])+' : '+n+';'
        elif m=='leave':
            code='r.sp=r.bp;r.bp=pop();'+tail
        elif m=='ret':
            code='r.ip=pop();'+('r.sp=static_cast<uint16_t>(r.sp+'+get(op[0])+');' if op else '')
        else:
            raise ValueError('Unsupported queue instruction: '+str((hex(ins.address),m,ins.op_str)))
        cases.append('    case '+hex(ins.address)+':'+code+'break;')
    addresses=[ins.address for ins in instructions]
    catalog='\n'.join('    '+','.join(hex(a) for a in addresses[i:i+12])+',' for i in range(0,len(addresses),12))
    owners=('actor_finish.hpp','actor_terrain.hpp','actor_contact.hpp','actor_real48.hpp',
            'frame_spawner.hpp','frame_display.hpp','actor_animation.hpp','boss_links.hpp')
    labels=set()
    for owner in owners:
        labels.update(int(value,16) for value in re.findall(r'\bcase\s+(0x[0-9a-fA-F]+)\s*:',
            (root/'src/core'/owner).read_text()))
    game_labels=sorted(v for v in labels if 0x165a<=v<0x167e or 0x370e<=v<0x3a7e or 0x3fa6<=v<0x432a)
    library_labels=sorted(v for v in labels if v<0x1820 and not 0x945<=v<=0x9b0)
    def borrowed_catalog(name,values):
        items='\n'.join('    '+','.join(hex(a) for a in values[i:i+12])+',' for i in range(0,len(values),12))
        return 'inline constexpr std::array<uint16_t,'+str(len(values))+'> '+name+'{{\n'+items+'\n}};\n'
    borrowed=borrowed_catalog('kTransientBorrowedGame',game_labels)+borrowed_catalog('kTransientBorrowedLibrary',library_labels)+stack_catalog(md,body)
    text='''#pragma once

#include "core/actor_finish.hpp"
#include <algorithm>
#include <array>

namespace lezac::core {
class TransientQueueDivideFault final : public std::domain_error {
public:
    TransientQueueDivideFault():std::domain_error("Transient queue divide fault") {}
};

inline constexpr std::array<uint16_t,COUNT> kTransientQueueInstructions{{
CATALOG
}};
inline bool transientQueueInstructionBoundary(uint16_t ip) {
    return std::binary_search(kTransientQueueInstructions.begin(),kTransientQueueInstructions.end(),ip);
}
BORROWED
inline bool transientQueueBorrowedBoundary(uint16_t cs,uint16_t ip,uint16_t game) {
    if (cs==game) return std::binary_search(kTransientBorrowedGame.begin(),kTransientBorrowedGame.end(),ip);
    return cs==static_cast<uint16_t>(game+0x920) &&
        std::binary_search(kTransientBorrowedLibrary.begin(),kTransientBorrowedLibrary.end(),ip);
}

// Explicit unchanged MZ operands for 3A7E..3ED9 and 45FA..4D3B.
// Generated by tools/generate_transient_queue_instructions.py; not a runtime decoder.
inline bool advanceTransientQueueInstruction(DosGetTimeRegisters& r,uint16_t game,const TimerIrqBus& bus) {
    if (r.cs!=game) return false;
    const auto flag=[&](uint32_t bit) { return (r.flags&bit)!=0; };
    const auto valueFlags=[](uint16_t v,bool byte=false) {
        return (v==0 ? 0x40u : 0u)|(v&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(v))%2==0 ? 4u : 0u);
    };
    const auto logic=[&](uint16_t v,bool byte=false) {
        v=static_cast<uint16_t>(v&(byte ? 255u : 65535u));
        r.flags=(r.flags&~uint32_t{0x8d5})|valueFlags(v,byte);return v;
    };
    const auto arithmetic=[&](uint16_t a,uint16_t b,bool subtract=false,bool byte=false,bool carry=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u,extra=carry && flag(1) ? 1u : 0u;
        const uint32_t wide=subtract ? uint32_t{a}-b-extra : uint32_t{a}+b+extra;
        const auto v=static_cast<uint16_t>(wide&mask);uint32_t f=valueFlags(v,byte)|((a^b^v)&16u);
        if (subtract ? uint32_t{a}<uint32_t{b}+extra : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^v)&sign) : (~(a^b)&(a^v)&sign)) f|=0x800;
        r.flags=(r.flags&~uint32_t{0x8d5})|f;return v;
    };
    const auto increment=[&](uint16_t v,bool subtract=false,bool byte=false) {
        const auto cf=r.flags&1u;v=arithmetic(v,1,subtract,byte);r.flags=(r.flags&~uint32_t{1})|cf;return v;
    };
    const auto shift=[&](uint16_t v,unsigned n,bool right=false) {
        for (unsigned i=0;i<n;++i) {
            const auto old=v,cf=static_cast<uint16_t>(right ? v&1u : v>>15);
            v=static_cast<uint16_t>(right ? v>>1 : v<<1);
            r.flags=(r.flags&~uint32_t{0x8d5})|valueFlags(v)|16u|cf|
                (right ? (old&0x8000u ? 0x800u : 0u) : ((old^v)&0x8000u ? 0x800u : 0u));
        }
        return v;
    };
    const auto push=[&](uint16_t v) {r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,v);};
    const auto pop=[&] {const auto v=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return v;};
    const auto less=[&] {return flag(0x80)!=flag(0x800);};
    const auto multiply=[&](uint16_t v) {
        const uint32_t product=uint32_t{r.ax}*v;r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
        r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
    };
    const auto signedMultiply=[&](uint16_t v,int16_t factor) {
        const int32_t product=int32_t{std::bit_cast<int16_t>(v)}*factor;
        r.flags=(r.flags&~uint32_t{0x801})|((product < -32768 || product > 32767) ? 0x801u : 0u);
        return static_cast<uint16_t>(product);
    };
    const auto divide=[&](uint16_t v) {
        const uint32_t value=(uint32_t{r.dx}<<16)|r.ax;
        if (!v || value/v>65535) throw TransientQueueDivideFault();
        r.ax=static_cast<uint16_t>(value/v);r.dx=static_cast<uint16_t>(value%v);
    };
    const auto signedDivide=[&](uint16_t v) {
        const int64_t value=std::bit_cast<int32_t>((uint32_t{r.dx}<<16)|r.ax);const auto factor=std::bit_cast<int16_t>(v);
        if (!factor || value/factor < -32768 || value/factor > 32767) throw TransientQueueDivideFault();
        r.ax=static_cast<uint16_t>(value/factor);r.dx=static_cast<uint16_t>(value%factor);
    };
    switch (r.ip) {
CASES
    default:return false;
    }
    return true;
}
} // namespace lezac::core
'''.replace('COUNT',str(len(cases))).replace('CATALOG',catalog).replace('CASES','\n'.join(cases)).replace('BORROWED',borrowed)
    out.write_text(text)
    print('transient_queue_transcription=ok instructions='+str(len(cases))+' sha256='+hashlib.sha256(text.encode()).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
