#include <cstdio>
#include <cstdlib>
#include "cpu.h"
#include "pic.h"

extern Bitu CPU_flag_id_toggle;
struct LezacTimerProbeState {
    FILE* output;
    bool initialized, waiting;
    Bit16u code, data, return_cs, return_ip, stack_base, ss;
    Bit64u dispatch;
    unsigned call, rows, remaining, counts[6];
};
static LezacTimerProbeState lezac_timer_probe = {};

static void LezacTimerEmit(const char* kind) {
    auto& p = lezac_timer_probe;
    if (!p.output) return;
    if (p.rows >= 4096 || ftell(p.output) >= 8 * 1024 * 1024) {
        fprintf(p.output,"cap\n"); fclose(p.output); p.output=0; return;
    }
    const long long clock=(long long)PIC_Ticks*CPU_CycleMax+CPU_CycleMax-CPU_CycleLeft-CPU_Cycles;
    const unsigned long long words[] = {p.call, (unsigned long long)PIC_Ticks,
        SegValue(cs),(Bit16u)reg_eip,SegValue(ds),SegValue(es),SegValue(ss),reg_sp,
        reg_ax,reg_bx,reg_cx,reg_dx,reg_si,reg_di,reg_bp,reg_flags,
        kind[0]=='r' ? ((FMASK_ALL&0xffffu)|CPU_flag_id_toggle|2u) : (FLAG_IF|FLAG_TF|FLAG_DF),
        mem_readd(0x46c),mem_readb(0x440),mem_readb(0x43f),mem_readw(0x70),mem_readw(0x72),
        p.stack_base,p.ss,CPU_flag_id_toggle};
    fprintf(p.output,"%s,%llu,%lld",kind,(unsigned long long)p.dispatch,clock);
    for(unsigned i=0;i<sizeof(words)/sizeof(words[0]);++i)fprintf(p.output,",%llu",words[i]);
    fprintf(p.output,",%lld,%lld",(long long)CPU_Cycles,(long long)CPU_CycleLeft);
    fprintf(p.output,",");
    for(unsigned i=0;i<8;++i)fprintf(p.output,"%02x",(unsigned)mem_readb(SegPhys(cs)+(Bit16u)(reg_eip+i)));
    fprintf(p.output,",");
    for(unsigned i=0;i<128;++i)fprintf(p.output,"%02x",(unsigned)mem_readb((PhysPt)p.ss*16+(Bit16u)(p.stack_base+i)));
    const PhysPt data=(PhysPt)p.data*16;
    fprintf(p.output,",");
    for(unsigned i=0;i<2;++i)fprintf(p.output,"%02x",(unsigned)mem_readb(data+0x78c0+i));
    for(unsigned i=0;i<3;++i)fprintf(p.output,"%02x",(unsigned)mem_readb(data+0x79a0+i));
    for(unsigned i=0;i<5;++i)fprintf(p.output,"%02x",(unsigned)mem_readb(data+0x79c0+i));
    fprintf(p.output,",");
    if(kind[0]=='e') {
        const PhysPt bank=(PhysPt)mem_readw(data+0x79c2)*16+mem_readw(data+0x79c0);
        for(unsigned i=0;i<780;++i)fprintf(p.output,"%02x",(unsigned)mem_readb(bank+i));
    }
    fprintf(p.output,"\n"); ++p.rows;
}
static void LezacTimerExit() {
    if(lezac_timer_probe.output){fprintf(lezac_timer_probe.output,"end\n");fclose(lezac_timer_probe.output);lezac_timer_probe.output=0;}
}
static void LezacWorkProbe() {
    auto& p=lezac_timer_probe;
    if(!p.initialized) {
        p.initialized=true;
        const char* path=getenv("LEZAC_TIMER_IRQ_TRACE");
        if(path)p.output=fopen(path,"wx");
        if(p.output){
            fprintf(p.output,"kind,dispatch,clock,call,pic_ticks,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,flags,defined_flags,bios_ticks,motor,drive,int1c_ip,int1c_cs,stack_base,stack_ss,id_toggle,cpu_cycles,cpu_cycle_left,opcode,stack,globals,bank\n");
            atexit(LezacTimerExit);
        }
    }
    if(!p.output)return;
    ++p.dispatch;
    const Bit16u code=SegValue(cs),ip=(Bit16u)reg_eip;
    if(!p.code && ip==0x7783 && SegValue(ds)==(Bit16u)(code-16) &&
       SegValue(ss)==(Bit16u)(code+0x1711) && reg_sp==0x4000) {
        const Bit16u offsets[]={0,0x072d,0,0x0111},segments[]={0x0920,0x08ac,0x084a,0x082d};
        bool matches=true;
        for(unsigned i=0;i<4;++i){const PhysPt at=SegPhys(cs)+ip+i*5;
            matches=matches && mem_readb(at)==0x9a && mem_readw(at+1)==offsets[i] && mem_readw(at+3)==(Bit16u)(code+segments[i]);}
        if(matches){p.code=code;p.data=(Bit16u)(code+0xaa2);p.ss=SegValue(ss);p.stack_base=reg_sp;LezacTimerEmit("identified");}
    }
    if(!p.code)return;
    if(code==0xf000 && ip==0xfea5 && mem_readw(0x70)==0x0fbe && mem_readw(0x72)==p.code) {
        const PhysPt data=(PhysPt)p.data*16;
        unsigned category=0;
        if(mem_readb(data+0x79c4)) {
            if(mem_readw(data+0x78c0)>0xea60)category=1;
            else if((Bit8u)(mem_readb(data+0x79a0)+1)==mem_readb(data+0x79a2))category=2;
            else if((Bit8u)(mem_readb(data+0x79a0)+1)==mem_readb(data+0x79a1))category=3;
            else category=4;
        }
        const unsigned limit=category==1 || category==2 ? 4 : 2;
        if(!p.waiting && p.counts[category]<limit){
            ++p.counts[category]; ++p.call;p.waiting=true;p.remaining=256;
            p.ss=SegValue(ss);p.stack_base=(Bit16u)(reg_sp-64);
            p.return_ip=mem_readw(SegPhys(ss)+reg_sp);p.return_cs=mem_readw(SegPhys(ss)+(Bit16u)(reg_sp+2));
            LezacTimerEmit("enter");
        }
    }
    if(p.waiting && code==p.return_cs && ip==p.return_ip){LezacTimerEmit("returned");p.waiting=false;}
    if(p.waiting){if(!p.remaining){LezacTimerEmit("window_exhausted");p.waiting=false;}
        else {LezacTimerEmit("instruction");--p.remaining;}}
}
