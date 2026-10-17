#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <zlib.h>
#include "cpu.h"
#include "pic.h"
#include "lezac_clock_observation.h"
#include "keyboard_irq_api.h"

extern Bitu CPU_flag_id_toggle;

struct LezacKeyboardIrqProbe {
    gzFile output;
    bool initialized, armed, active, completed;
    Bit16u code, data, return_ip, return_cs, initial_sp, stack_base, stack_ss;
    Bit64u dispatch;
    unsigned window, records, scan;
    unsigned seen[256];
};
inline LezacKeyboardIrqProbe lezac_keyboard_irq = {};

inline void LezacKeyboardIrqEmit(const char* kind) {
    auto& p = lezac_keyboard_irq;
    if (!p.output) return;
    if (p.records++ >= 25000 || gztell(p.output) >= 32 * 1024 * 1024) {
        gzprintf(p.output, "cap\n"); gzclose(p.output); p.output = 0; return;
    }
    const unsigned long long values[] = {p.window, (unsigned long long)p.dispatch,
        SegValue(cs), (Bit16u)reg_eip, SegValue(ds), SegValue(es), SegValue(ss), reg_sp,
        reg_ax, reg_bx, reg_cx, reg_dx, reg_si, reg_di, reg_bp, reg_flags, CPU_flag_id_toggle,
        p.code, p.data, p.return_ip, p.return_cs, p.initial_sp, p.stack_base, p.stack_ss,
        p.scan, (unsigned)mem_readw((PhysPt)p.data * 16 + 0x78c2),
        (unsigned)mem_readb((PhysPt)p.data * 16 + 0x79b7)};
    gzprintf(p.output, "%s", kind);
    for (unsigned i = 0; i < sizeof(values) / sizeof(values[0]); ++i)
        gzprintf(p.output, ",%llu", values[i]);
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 8; ++i)
        gzprintf(p.output, "%02x", (unsigned)mem_readb(SegPhys(cs) + (Bit16u)(reg_eip + i)));
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 128; ++i)
        gzprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)p.stack_ss * 16 + (Bit16u)(p.stack_base + i)));
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 152; ++i) gzprintf(p.output, "%02x", (unsigned)mem_readb(0x400 + i));
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 10; ++i)
        gzprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)p.data * 16 + 0x1b78 + i));
    const PhysPt chain = (PhysPt)p.data * 16 + 0x1b60;
    const Bit16u chain_ip = mem_readw(chain), chain_cs = mem_readw(chain + 2);
    const Bit16u bios15_ip = mem_readw(0x54), bios15_cs = mem_readw(0x56);
    gzprintf(p.output, ",%u,%u,%u,%u,", chain_ip, chain_cs, bios15_ip, bios15_cs);
    for (unsigned i = 0; i < 21; ++i)
        gzprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)chain_cs * 16 + (Bit16u)(chain_ip + i)));
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 5; ++i)
        gzprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)bios15_cs * 16 + (Bit16u)(bios15_ip + i)));
    LezacKeyboardHardwareObservation hardware = {}; LezacReadKeyboardHardware(hardware);
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 32; ++i) gzprintf(p.output, "%02x", (unsigned)hardware.buffer[i]);
    gzprintf(p.output, ",");
    for (unsigned i = 0; i < 13; ++i)
        gzprintf(p.output, "%s%llu", i ? ";" : "", (unsigned long long)hardware.values[i]);
    LezacClockObservation clock = {}; LezacReadPicClock(clock); LezacReadPit0(clock);
    gzprintf(p.output, ",%lld,%lld,%lld,%llu,%llu,%llu,%llu,%llu,%llu\n",
        (long long)CPU_Cycles, (long long)CPU_CycleLeft, (long long)CPU_IODelayRemoved,
        (unsigned long long)PIC_Ticks, (unsigned long long)clock.active, (unsigned long long)clock.pending,
        (unsigned long long)clock.active_lines, (unsigned long long)clock.inservice_lines,
        (unsigned long long)clock.masked_lines);
}

inline void LezacDosTimeExit() {
    auto& p = lezac_keyboard_irq;
    if (p.output) {gzprintf(p.output, "end\n"); gzclose(p.output); p.output = 0;}
}
inline void LezacDosTimeCallback(const char*, Bit16u) {}

inline void LezacWorkProbe() {
    auto& p = lezac_keyboard_irq;
    if (!p.initialized) {
        p.initialized = true;
        const char* path = getenv("LEZAC_KEYBOARD_IRQ_TRACE");
        if (path) p.output = gzopen(path, "wb1");
        if (p.output) {
            gzprintf(p.output, "kind,window,dispatch,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,flags,id_toggle,game,data,return_ip,return_cs,initial_sp,stack_base,stack_ss,scan,frame,level,opcode,stack,bios,held,chain_ip,chain_cs,bios15_ip,bios15_cs,chain_stub,bios15_stub,hardware_buffer,hardware,cpu_cycles,cpu_left,io_delay_removed,pic_ticks,pic_active,pic_pending,active_lines,inservice_lines,masked_lines\n");
            atexit(LezacDosTimeExit);
        }
    }
    if (!p.output || p.completed) return;
    ++p.dispatch;
    const Bit16u code = SegValue(cs), ip = (Bit16u)reg_eip;
    if (!p.active && ip == 0x1091 && mem_readw(0x24) == ip && mem_readw(0x26) == code &&
        mem_readw((PhysPt)code * 16 + 0x109d) == (Bit16u)(code + 0xaa2)) {
        const Bit8u signature[] = {0x50,0x53,0x51,0x52,0x56,0x57,0x1e,0x06,0x55,0x89,0xe5,0xb8};
        for (unsigned i = 0; i < sizeof(signature); ++i)
            if (mem_readb((PhysPt)code * 16 + ip + i) != signature[i]) return;
        if (!p.armed) {
            const char* path = getenv("LEZAC_KEYBOARD_IRQ_ARMED");
            FILE* marker = path ? fopen(path, "r") : 0;
            if (!marker) return;
            fclose(marker); p.armed = true;
        }
        p.code = code; p.data = (Bit16u)(code + 0xaa2);
        p.initial_sp = reg_sp; p.stack_ss = SegValue(ss); p.stack_base = (Bit16u)(reg_sp - 96);
        p.return_ip = mem_readw(SegPhys(ss) + reg_sp); p.return_cs = mem_readw(SegPhys(ss) + (Bit16u)(reg_sp + 2));
        LezacKeyboardHardwareObservation hardware = {}; LezacReadKeyboardHardware(hardware);
        p.scan = (unsigned)hardware.values[7]; ++p.window; p.active = true;
        LezacKeyboardIrqEmit("irq_enter"); return;
    }
    if (!p.active) return;
    if (code == p.return_cs && ip == p.return_ip && reg_sp == (Bit16u)(p.initial_sp + 6)) {
        ++p.seen[p.scan]; LezacKeyboardIrqEmit("irq_return"); p.active = false;
        if (p.output) gzflush(p.output, Z_SYNC_FLUSH);
        const unsigned needed[] = {0x2c,0x2d,0x32,0x31,0x2e,0x4b,0x4d,0x52,0x48,0x50,
            0xac,0xad,0xb2,0xb1,0xae,0xcb,0xcd,0xd2,0xc8,0xd0,0xe0,0x12,0x13,0x1e};
        bool complete = p.seen[0x2c] >= 2;
        for (unsigned i = 0; i < sizeof(needed) / sizeof(needed[0]); ++i) complete = complete && p.seen[needed[i]];
        if (complete) {
            p.completed = true;
            const char* path = getenv("LEZAC_KEYBOARD_IRQ_TARGET");
            FILE* marker = path ? fopen(path, "wx") : 0;
            if (marker) {fprintf(marker, "1\n"); fclose(marker);}
        }
        return;
    }
    LezacKeyboardIrqEmit("instruction");
}
