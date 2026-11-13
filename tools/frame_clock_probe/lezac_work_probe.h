#pragma once
#include <cstdio>
#include <cstdlib>
#include "cpu.h"
#include "pic.h"
#include "lezac_clock_observation.h"

extern Bitu CPU_flag_id_toggle;

// Recovery-only observation; no guest writes or lazy-flag materialization.
struct LezacDosTimeProbeState {
    FILE* output;
    bool initialized, waiting, windowed, frame_waiting;
    Bit16u code, data, psp, vector_cs, vector_ip, return_cs, return_ip, stack_base, stack_ss;
    Bit64u dispatch;
    unsigned records, call, remaining;
    unsigned full_windows;
    bool irq_in_window, entry_game_vector, target_completed, frame_control_seen;
};
inline LezacDosTimeProbeState lezac_dos_time_probe = {};

inline void LezacDosTimeEmit(const char* kind) {
    auto& p = lezac_dos_time_probe;
    if (!p.output) return;
    LezacClockObservation observation = {};
    LezacReadPicClock(observation);
    LezacReadPit0(observation);
    if (p.records >= 10000 || ftell(p.output) >= 4 * 1024 * 1024) {
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
    for (unsigned i = 0; i < 128; ++i)
        fprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)p.stack_ss * 16 + (Bit16u)(p.stack_base + i)));
    fprintf(p.output, ",");
    for (unsigned i = 0; i < 15; ++i)
        fprintf(p.output, "%02x", (unsigned)mem_readb((PhysPt)p.vector_cs * 16 + (Bit16u)(p.vector_ip + i)));
    fprintf(p.output, ",%u,%u,%u,%u,%u,%u,", (unsigned)mem_readb(0x440), (unsigned)mem_readb(0x43f),
        (unsigned)mem_readw(0x70), (unsigned)mem_readw(0x72), (unsigned)p.stack_base, (unsigned)p.stack_ss);
    const PhysPt data = (PhysPt)p.data * 16;
    for (unsigned i = 0; i < 2; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(data + 0x78c0 + i));
    for (unsigned i = 0; i < 3; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(data + 0x79a0 + i));
    for (unsigned i = 0; i < 5; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(data + 0x79c0 + i));
    fprintf(p.output, ",");
    if (kind[0] == 'c') {
        const PhysPt bank = (PhysPt)mem_readw(data + 0x79c2) * 16 + mem_readw(data + 0x79c0);
        for (unsigned i = 0; i < 780; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(bank + i));
    }
    fprintf(p.output, ",%lld,%lld,%lld,%llu,%llu,%llu,%llu,%llu,%u,%u,%llu,%u,%llu,%u,%u,%llu,%u,",
        (long long)CPU_Cycles, (long long)CPU_CycleLeft, (long long)CPU_IODelayRemoved,
        (unsigned long long)observation.active, (unsigned long long)observation.pending,
        (unsigned long long)observation.active_lines, (unsigned long long)observation.inservice_lines,
        (unsigned long long)observation.masked_lines, observation.special ? 1u : 0u,
        observation.auto_eoi ? 1u : 0u, (unsigned long long)observation.irq0_vector,
        (unsigned)observation.pit_delay_bits, (unsigned long long)observation.pit_count,
        (unsigned)observation.pit_mode, observation.pit_update ? 1u : 0u,
        (unsigned long long)observation.pit_start_bits, observation.queue_overflow ? 1u : 0u);
    for (unsigned i = 0; i < observation.queue_count; ++i) {
        if (i) fprintf(p.output, ";");
        fprintf(p.output, "%08x:%llu:%llu", (unsigned)observation.queue[i].index_bits,
            (unsigned long long)observation.queue[i].kind, (unsigned long long)observation.queue[i].value);
    }
    fprintf(p.output, ",%u,%u,", p.irq_in_window ? 1u : 0u, p.target_completed ? 1u : 0u);
    for (unsigned i = 0; i < 2; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(data + 0x2074 + i));
    for (unsigned i = 0; i < 9; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(data + 0x79a4 + i));
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
    if (!p.output || !p.code || p.target_completed || reg_ah != 0x2c) return;
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
            fprintf(p.output, "kind,dispatch,clock,call,windowed,pic_ticks,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,flags,defined_flags,bios_ticks,psp,psp_stack,return_ip,return_cs,vector_cs,vector_ip,cycle_max,id_toggle,opcode,stack,vector_stub,motor,drive,int1c_ip,int1c_cs,stack_base,stack_ss,globals,bank,cpu_cycles,cpu_left,io_delay_removed,pic_active,pic_pending,active_lines,inservice_lines,masked_lines,pic_special,pic_auto_eoi,irq0_vector,pit0_delay_bits,pit0_count,pit0_mode,pit0_update,pit0_start_bits,queue_overflow,queue,irq_in_window,target_completed,frame_globals\n");
            atexit(LezacDosTimeExit);
        }
    }
    if (!p.output) return;
    if (p.target_completed) return;
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
            p.psp = (Bit16u)(code - 16);
            p.stack_ss = SegValue(ss);
            p.stack_base = (Bit16u)(reg_sp - 80);
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
            p.psp = (Bit16u)(code - 16);
            p.stack_ss = SegValue(ss);
            p.stack_base = (Bit16u)(reg_sp - 80);
            LezacDosTimeEmit("identified");
        }
    }
    if (!p.code) return;
    if (code == p.vector_cs && ip == (Bit16u)(p.vector_ip + 1) && reg_ah == 0x2c) {
        if (p.waiting) LezacDosTimeEmit("nested_service");
        ++p.call;
        p.waiting = true;
        p.irq_in_window = false;
        p.entry_game_vector = mem_readw(0x70) == 0x0fbe && mem_readw(0x72) == p.code;
        LezacClockObservation observation = {};
        LezacReadPicClock(observation);
        bool near = (observation.pending & 1) != 0;
        const Bits now = PIC_TickIndexND();
        for (unsigned i = 0; i < observation.queue_count; ++i) {
            if (observation.queue[i].kind != 1) continue;
            float index = 0;
            std::memcpy(&index, &observation.queue[i].index_bits, sizeof(index));
            const float distance = index * CPU_CycleMax - now;
            if (distance >= 0 && distance <= 512) near = true;
        }
        const bool frame_control = p.entry_game_vector && !p.frame_control_seen &&
            mem_readw(SegPhys(ss) + reg_sp) == 0x791e &&
            mem_readw(SegPhys(ss) + (Bit16u)(reg_sp + 2)) == p.code;
        p.windowed = p.full_windows < 8 && (p.call <= 2 || frame_control || (p.entry_game_vector && near));
        if (frame_control) p.frame_control_seen = true;
        if (p.windowed) ++p.full_windows;
        p.remaining = 4096;
        p.stack_ss = SegValue(ss);
        p.stack_base = (Bit16u)(reg_sp - 80);
        p.return_ip = mem_readw(SegPhys(ss) + reg_sp);
        p.return_cs = mem_readw(SegPhys(ss) + (Bit16u)(reg_sp + 2));
        p.frame_waiting = p.windowed && p.return_cs == p.code && p.return_ip == 0x791e;
        LezacDosTimeEmit("callback_enter");
    }
    if (p.waiting && code == p.return_cs && ip == p.return_ip) {
        LezacDosTimeEmit("returned");
        if (p.output) fflush(p.output);
        p.waiting = false;
    }
    if (p.frame_waiting && !p.waiting && code == p.code && ip == 0x7966) {
        p.target_completed = p.entry_game_vector && p.irq_in_window;
        LezacDosTimeEmit("frame_elapsed_return");
        if (p.output) fflush(p.output);
        p.frame_waiting = false;
    }
    if ((p.waiting || p.frame_waiting) && code == 0xf000 && ip == 0xfea5) p.irq_in_window = true;
    if ((p.waiting || p.frame_waiting) && p.windowed) {
        if (!p.remaining) {
            LezacDosTimeEmit("window_exhausted");
            p.windowed = false;
        } else {
            LezacDosTimeEmit("instruction");
            --p.remaining;
        }
    }
}
