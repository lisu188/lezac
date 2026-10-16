#pragma once
#include <cstdio>
#include <cstdlib>
#include "cpu.h"
#include "pic.h"

extern Bitu CPU_flag_id_toggle;

// Recovery-only observation; no guest writes or lazy-flag materialization.
struct LezacDosTimeProbeState {
    FILE* output;
    bool initialized, waiting, windowed;
    Bit16u code, data, psp, vector_cs, vector_ip, return_cs, return_ip;
    Bit64u dispatch;
    unsigned records, call, remaining;
};
inline LezacDosTimeProbeState lezac_dos_time_probe = {};

inline void LezacDosTimeEmit(const char* kind) {
    auto& p = lezac_dos_time_probe;
    if (!p.output) return;
    if (p.records >= 10000 || ftell(p.output) >= 2 * 1024 * 1024) {
        fprintf(p.output, "cap\n");
        fclose(p.output);
        p.output = 0;
        return;
    }
    const long long clock = (long long)PIC_Ticks * CPU_CycleMax +
        CPU_CycleMax - CPU_CycleLeft - CPU_Cycles;
    const bool returned = kind[0] == 'r';
    const unsigned long long values[] = {
        p.call, p.windowed, (unsigned long long)PIC_Ticks,
        SegValue(cs), (Bit16u)reg_eip, SegValue(ds), SegValue(es), SegValue(ss), reg_sp,
        reg_ax, reg_bx, reg_cx, reg_dx, reg_si, reg_di, reg_bp, reg_flags,
        returned ? ((FMASK_ALL & 0xffffu) | CPU_flag_id_toggle | 2u) :
                   (FLAG_IF | FLAG_TF | FLAG_DF),
        mem_readd(0x46c), p.psp, p.psp ? mem_readd((PhysPt)p.psp * 16 + 0x2e) : 0,
        p.return_ip, p.return_cs, p.vector_cs, p.vector_ip, CPU_CycleMax, CPU_flag_id_toggle
    };
    fprintf(p.output, "%s,%llu,%lld", kind, (unsigned long long)p.dispatch, clock);
    for (unsigned i = 0; i < sizeof(values)/sizeof(values[0]); ++i)
        fprintf(p.output, ",%llu", values[i]);
    fprintf(p.output, ",");
    for (unsigned i = 0; i < 8; ++i)
        fprintf(p.output, "%02x", (unsigned)mem_readb(SegPhys(cs) + (Bit16u)(reg_eip + i)));
    fprintf(p.output, ",");
    for (unsigned i = 0; i < 64; ++i)
        fprintf(p.output, "%02x", (unsigned)mem_readb(SegPhys(ss) + (Bit16u)(reg_sp + i)));
    fprintf(p.output, ",");
    for (unsigned i = 0; i < 15; ++i)
        fprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)p.vector_cs * 16 + (Bit16u)(p.vector_ip + i)));
    fprintf(p.output, "\n");
    ++p.records;
}

inline void LezacDosTimeExit() {
    if (lezac_dos_time_probe.output) {
        fprintf(lezac_dos_time_probe.output, "end\n");
        fclose(lezac_dos_time_probe.output);
        lezac_dos_time_probe.output = 0;
    }
}

inline void LezacDosTimeCallback(const char* kind, Bit16u psp) {
    auto& p = lezac_dos_time_probe;
    if (!p.output || !p.code || reg_ah != 0x2c) return;
    p.psp = psp;
    LezacDosTimeEmit(p.waiting ? kind : "unexpected_service");
}

inline void LezacWorkProbe() {
    auto& p = lezac_dos_time_probe;
    if (!p.initialized) {
        p.initialized = true;
        const char* path = getenv("LEZAC_DOS_TIME_TRACE");
        if (path) p.output = fopen(path, "wx");
        if (p.output) {
            fprintf(p.output, "kind,dispatch,clock,call,windowed,pic_ticks,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,flags,defined_flags,bios_ticks,psp,psp_stack,return_ip,return_cs,vector_cs,vector_ip,cycle_max,id_toggle,opcode,stack,vector_stub\n");
            atexit(LezacDosTimeExit);
        }
    }
    if (!p.output) return;
    ++p.dispatch;
    const Bit16u code = SegValue(cs), ip = (Bit16u)reg_eip;
    if (!p.code && ip == 0x7783 && SegValue(ds) == (Bit16u)(code - 16) &&
            SegValue(ss) == (Bit16u)(code + 0x1711) && reg_sp == 0x4000) {
        const Bit16u offsets[] = {0x0000, 0x072d, 0x0000, 0x0111};
        const Bit16u segments[] = {0x0920, 0x08ac, 0x084a, 0x082d};
        bool matches = true;
        for (unsigned i = 0; i < 4; ++i) {
            const PhysPt at = SegPhys(cs) + ip + i * 5;
            matches = matches && mem_readb(at) == 0x9a && mem_readw(at + 1) == offsets[i] &&
                mem_readw(at + 3) == (Bit16u)(code + segments[i]);
        }
        if (matches) {
            p.code = code;
            p.data = (Bit16u)(code + 0xaa2);
            p.vector_ip = mem_readw(0x84);
            p.vector_cs = mem_readw(0x86);
            LezacDosTimeEmit("identified");
        }
    }
    if (!p.code && ip == 0x1fc && SegValue(ds) == (Bit16u)(code + 0xaa2)) {
        const Bit8u signature[] = {0x55,0x89,0xe5,0xb8,0x0e,0x00,0x9a,0xdf,0x04};
        bool matches = mem_readw(SegPhys(cs) + ip + 9) == (Bit16u)(code + 0x920);
        for (unsigned i = 0; i < sizeof(signature); ++i)
            matches = matches && mem_readb(SegPhys(cs) + ip + i) == signature[i];
        if (matches) {
            p.code = code;
            p.data = SegValue(ds);
            p.vector_ip = mem_readw(0x84);
            p.vector_cs = mem_readw(0x86);
            LezacDosTimeEmit("identified");
        }
    }
    if (!p.code) return;
    if (code == p.vector_cs && ip == (Bit16u)(p.vector_ip + 1) && reg_ah == 0x2c) {
        if (p.waiting) LezacDosTimeEmit("nested_service");
        ++p.call;
        p.waiting = true;
        p.windowed = p.call <= 8;
        p.remaining = 4096;
        p.return_ip = mem_readw(SegPhys(ss) + reg_sp);
        p.return_cs = mem_readw(SegPhys(ss) + (Bit16u)(reg_sp + 2));
        LezacDosTimeEmit("callback_enter");
    }
    if (p.waiting && code == p.return_cs && ip == p.return_ip) {
        LezacDosTimeEmit("returned");
        p.waiting = false;
    }
    if (p.waiting && p.windowed) {
        if (!p.remaining) {
            LezacDosTimeEmit("window_exhausted");
            p.windowed = false;
        } else {
            LezacDosTimeEmit("instruction");
            --p.remaining;
        }
    }
}
