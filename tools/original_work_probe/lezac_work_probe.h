#include <cstdlib>
#include "vga.h"

// Recovery-only host instrumentation. No guest registers or memory are written.
struct LezacProbeIrq {
    Bit16u cs, ip, ss, return_sp;
    unsigned number;
    Bit64u dispatch;
    long long clock;
};
struct LezacProbeState {
    FILE* output;
    bool initialized, capped, delay_active;
    Bit16u code, data, vector_cs[2], vector_ip[2];
    unsigned page, records, depth;
    Bit64u dispatch, irq_dispatch;
    long long irq_clock;
    LezacProbeIrq irq[8];
    Bit16u delay_cs, delay_ip, delay_ss, delay_sp, delay_argument, delay_calibration;
};
static LezacProbeState lezac_probe = {};

static long long LezacProbeClock() {
    return (long long)PIC_Ticks * CPU_CycleMax + CPU_CycleMax - CPU_CycleLeft - CPU_Cycles;
}
static void LezacProbeEmit(const char* kind, bool frame) {
    LezacProbeState& p = lezac_probe;
    if (!p.output) return;
    if (p.records >= 22000 || ftell(p.output) >= 6 * 1024 * 1024) {
        fprintf(p.output, "cap\n");
        fflush(p.output);
        fclose(p.output);
        p.output = 0;
        p.capped = true;
        return;
    }
    const long long clock = LezacProbeClock();
    Bit64u excluded_dispatch = p.irq_dispatch;
    long long excluded_clock = p.irq_clock;
    if (p.depth) {
        excluded_dispatch += p.dispatch - p.irq[0].dispatch;
        excluded_clock += clock - p.irq[0].clock;
    }
    const PhysPt at = SegPhys(ss) + (Bit16u)(reg_bp - 14);
    const unsigned index = frame ? mem_readw(at + 4) : 0;
    const unsigned destination = frame ? mem_readw(at + 2) : 0;
    const int fraction = frame ? (Bit16s)mem_readw(at + 12) : 0;
    const unsigned phase = frame ? mem_readw(at) : 0;
    const unsigned h = frame ? mem_readw(at + 8) : 0;
    const unsigned v = frame ? mem_readw(at + 6) : 0;
    char dac[43] = {};
    for (unsigned i = 0; i < 7; ++i) {
        const auto& color = vga.dac.rgb[176 + i];
        sprintf(dac + i * 6, "%02x%02x%02x", (unsigned)color.red, (unsigned)color.green, (unsigned)color.blue);
    }
    fprintf(p.output, "%s,%u,%llu,%lld,%llu,%lld,%llu,%u,%u,%u,%u,%u,%u,%u,%d,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%s,%u,%u\n",
        kind, p.page, (unsigned long long)p.dispatch, clock,
        (unsigned long long)(p.dispatch - excluded_dispatch), clock - excluded_clock,
        (unsigned long long)PIC_Ticks, (unsigned)SegValue(cs), (unsigned)(Bit16u)reg_eip,
        (unsigned)SegValue(ss), (unsigned)reg_sp, (unsigned)reg_bp, frame ? 1u : 0u,
        index, fraction, phase, destination, h, v, (unsigned)reg_ax, (unsigned)reg_cx,
        (unsigned)reg_dx, (unsigned)reg_di, p.depth, (unsigned)CPU_CycleMax, dac,
        (unsigned)p.delay_argument, (unsigned)p.delay_calibration);
    ++p.records;
}
static void LezacProbeExit() {
    if (lezac_probe.output) {
        LezacProbeEmit("end", false);
        if (lezac_probe.output) {
            fflush(lezac_probe.output);
            fclose(lezac_probe.output);
            lezac_probe.output = 0;
        }
    }
}
static void LezacWorkProbe() {
    LezacProbeState& p = lezac_probe;
    if (!p.initialized) {
        p.initialized = true;
        const char* path = getenv("LEZAC_WORK_TRACE");
        if (path) p.output = fopen(path, "wx");
        if (p.output) {
            fprintf(p.output, "kind,page,dispatch,clock,exclusive_dispatch,exclusive_clock,pic_ticks,cs,ip,ss,sp,bp,frame_valid,index,fraction,phase,destination,h,v,ax,cx,dx,di,irq_depth,cycle_max,dac,delay_argument,delay_calibration\n");
            atexit(LezacProbeExit);
        }
    }
    if (!p.output) return;
    ++p.dispatch;
    const Bit16u cs_value = SegValue(cs), ip = (Bit16u)reg_eip;
    if (!p.code && ip == 0x1fc && SegValue(ds) == (Bit16u)(cs_value + 0xaa2)) {
        const Bit8u signature[] = {0x55,0x89,0xe5,0xb8,0x0e,0x00,0x9a,0xdf,0x04};
        bool matches = true;
        for (unsigned i = 0; i < sizeof(signature); ++i)
            matches = matches && mem_readb(SegPhys(cs) + ip + i) == signature[i];
        matches = matches && mem_readw(SegPhys(cs) + ip + 9) == (Bit16u)(cs_value + 0x920);
        if (matches) {
            p.code = cs_value;
            p.data = SegValue(ds);
            for (unsigned i = 0; i < 2; ++i) {
                p.vector_ip[i] = mem_readw((8 + i) * 4);
                p.vector_cs[i] = mem_readw((8 + i) * 4 + 2);
            }
            LezacProbeEmit("identified", false);
        }
    }
    if (!p.code) return;
    while (p.depth) {
        const LezacProbeIrq& irq = p.irq[p.depth - 1];
        if (cs_value != irq.cs || ip != irq.ip || SegValue(ss) != irq.ss || reg_sp != irq.return_sp) break;
        const LezacProbeIrq closed = irq;
        --p.depth;
        if (!p.depth) {
            p.irq_dispatch += p.dispatch - closed.dispatch;
            p.irq_clock += LezacProbeClock() - closed.clock;
        }
        LezacProbeEmit(closed.number == 8 ? "irq8_return" : "irq9_return", false);
    }
    for (unsigned i = 0; i < 2; ++i) {
        if (cs_value != p.vector_cs[i] || ip != p.vector_ip[i]) continue;
        if (p.depth >= 8) { LezacProbeEmit("irq_overflow", false); return; }
        const PhysPt stack = SegPhys(ss) + reg_sp;
        LezacProbeIrq& irq = p.irq[p.depth++];
        irq.cs = mem_readw(stack + 2);
        irq.ip = mem_readw(stack);
        irq.ss = SegValue(ss);
        irq.return_sp = (Bit16u)(reg_sp + 6);
        irq.number = 8 + i;
        irq.dispatch = p.dispatch;
        irq.clock = LezacProbeClock();
        LezacProbeEmit(i == 0 ? "irq8_enter" : "irq9_enter", false);
    }
    if (p.delay_active && cs_value == p.delay_cs && ip == p.delay_ip &&
        SegValue(ss) == p.delay_ss && reg_sp == p.delay_sp) {
        LezacProbeEmit("delay_end", false);
        p.delay_active = false;
    }
    if (cs_value == (Bit16u)(p.code + 0x84a) && ip == 0x29c) {
        if (p.delay_active) { LezacProbeEmit("delay_overlap", false); return; }
        const PhysPt stack = SegPhys(ss) + reg_sp;
        p.delay_ip = mem_readw(stack);
        p.delay_cs = mem_readw(stack + 2);
        p.delay_argument = mem_readw(stack + 4);
        p.delay_ss = SegValue(ss);
        p.delay_sp = (Bit16u)(reg_sp + 6);
        p.delay_calibration = mem_readw((PhysPt)p.data * 16 + 0x7f68);
        p.delay_active = true;
        LezacProbeEmit("delay_begin", false);
    }
    if (cs_value != p.code) return;
    if (ip == 0x1fc) { ++p.page; LezacProbeEmit("begin", false); return; }
    if (ip == 0x219) { LezacProbeEmit("clear_return", false); return; }
    if (ip == 0x247) { LezacProbeEmit("palette_ready", false); return; }
    if (ip == 0x309) { LezacProbeEmit("finish", true); return; }
    const Bit16u index = mem_readw(SegPhys(ss) + (Bit16u)(reg_bp - 10));
    if (index % 320 > 1 && index < 63998) return;
    switch (ip) {
        case 0x251: LezacProbeEmit("horizontal", true); break;
        case 0x264: LezacProbeEmit("row_check", true); break;
        case 0x273: LezacProbeEmit("row_work", true); break;
        case 0x2e1: LezacProbeEmit("color", true); break;
        case 0x2f9: LezacProbeEmit("write", true); break;
        case 0x2fc: LezacProbeEmit("after_write", true); break;
        case 0x2ff: LezacProbeEmit("tail", true); break;
    }
}
