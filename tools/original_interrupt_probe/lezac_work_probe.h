#include <cstdlib>
#include "vga.h"

// Recovery-only pre-decode observation. Arithmetic flags remain lazy/unclaimed.
struct LezacInterruptProbeState {
    FILE* output;
    const char* path;
    bool initialized, changed;
    Bit16u code, data, vector_cs[2], vector_ip[2];
    Bit32u saved[2];
    Bit64u dispatch;
    unsigned records, remaining, entries[2], changed_entries[2], faults, images;
};
static LezacInterruptProbeState lezac_interrupt_probe = {};

static long long LezacInterruptClock() {
    return (long long)PIC_Ticks * CPU_CycleMax + CPU_CycleMax - CPU_CycleLeft - CPU_Cycles;
}
static void LezacInterruptEmit(const char* kind) {
    LezacInterruptProbeState& p = lezac_interrupt_probe;
    if (!p.output) return;
    if (p.records >= 4096 || ftell(p.output) >= 2 * 1024 * 1024) {
        fprintf(p.output, "cap\n");
        fclose(p.output);
        p.output = 0;
        return;
    }
    const PhysPt data = (PhysPt)p.data * 16;
    fprintf(p.output, "%s,%llu,%lld,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,",
        kind, (unsigned long long)p.dispatch, LezacInterruptClock(), (unsigned long long)PIC_Ticks,
        (unsigned)SegValue(cs), (unsigned)(Bit16u)reg_eip, (unsigned)SegValue(ds),
        (unsigned)SegValue(es), (unsigned)SegValue(ss), (unsigned)reg_sp,
        (unsigned)reg_ax, (unsigned)reg_bx, (unsigned)reg_cx, (unsigned)reg_dx,
        (unsigned)reg_si, (unsigned)reg_di, (unsigned)reg_bp,
        (unsigned)(reg_flags & (FLAG_IF | FLAG_TF | FLAG_DF)),
        (unsigned)mem_readd(0x46c), (unsigned)mem_readw(data + 0x2074),
        (unsigned)mem_readw(data + 0x78c0), (unsigned)CPU_CycleMax);
    for (unsigned i = 0; i < 8; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(SegPhys(cs) + (Bit16u)(reg_eip + i)));
    fprintf(p.output, ",");
    for (unsigned i = 0; i < 64; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(SegPhys(ss) + (Bit16u)(reg_sp + i)));
    fprintf(p.output, ",");
    for (unsigned i = 0; i < 13; ++i) fprintf(p.output, "%02x", (unsigned)mem_readb(data + 0x1b5f + i));
    fprintf(p.output, "\n");
    ++p.records;
}
static void LezacInterruptVga(const char* kind) {
    LezacInterruptProbeState& p = lezac_interrupt_probe;
    if (p.images >= 4 || !p.output) return;
    if (vga.mode != M_VGA || !vga.config.chained || !vga.config.compatible_chain4 || vga.dac.pel_mask != 0xff) {
        LezacInterruptEmit("vga_profile_unsupported");
        return;
    }
    char path[512];
    const int length = snprintf(path, sizeof(path), "%s.vga-%02u.bin", p.path, p.images);
    if (length < 0 || (unsigned)length >= sizeof(path)) return;
    FILE* output = fopen(path, "wbx");
    if (!output) return;
    // Match VGA_ChainedVGA_Handler without guest read-latch side effects.
    for (unsigned i = 0; i < 64000; ++i)
        fputc(vga.mem.linear[((i & ~3u) << 2) + (i & 3u)], output);
    for (unsigned i = 0; i < 256; ++i) {
        fputc(vga.dac.rgb[i].red, output);
        fputc(vga.dac.rgb[i].green, output);
        fputc(vga.dac.rgb[i].blue, output);
    }
    fclose(output);
    LezacInterruptEmit(kind);
    ++p.images;
    fflush(p.output);
}
static void LezacInterruptExit() {
    if (lezac_interrupt_probe.output) {
        // Emulator teardown may already have released guest memory.
        fprintf(lezac_interrupt_probe.output, "end\n");
        fclose(lezac_interrupt_probe.output);
        lezac_interrupt_probe.output = 0;
    }
}
static void LezacWorkProbe() {
    LezacInterruptProbeState& p = lezac_interrupt_probe;
    if (!p.initialized) {
        p.initialized = true;
        p.path = getenv("LEZAC_IRQ_TRACE");
        if (p.path) p.output = fopen(p.path, "wx");
        if (p.output) {
            fprintf(p.output, "kind,dispatch,clock,pic_ticks,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,control_flags,bios_ticks,pending_sound,latched_sound,cycle_max,opcode,stack,adjacent\n");
            atexit(LezacInterruptExit);
        }
    }
    if (!p.output) return;
    ++p.dispatch;
    const Bit16u code = SegValue(cs), ip = (Bit16u)reg_eip;
    if (!p.code && ip == 0x1fc && SegValue(ds) == (Bit16u)(code + 0xaa2)) {
        const Bit8u signature[] = {0x55,0x89,0xe5,0xb8,0x0e,0x00,0x9a,0xdf,0x04};
        bool matches = mem_readw(SegPhys(cs) + ip + 9) == (Bit16u)(code + 0x920);
        for (unsigned i = 0; i < sizeof(signature); ++i)
            matches = matches && mem_readb(SegPhys(cs) + ip + i) == signature[i];
        if (matches) {
            p.code = code;
            p.data = SegValue(ds);
            const PhysPt data = (PhysPt)p.data * 16;
            for (unsigned i = 0; i < 2; ++i) {
                p.vector_ip[i] = mem_readw((i == 0 ? 9 : 0x1c) * 4);
                p.vector_cs[i] = mem_readw((i == 0 ? 9 : 0x1c) * 4 + 2);
                p.saved[i] = mem_readd(data + 0x1b60 + i * 4);
            }
            LezacInterruptEmit("identified");
        }
    }
    if (!p.code) return;
    const PhysPt data = (PhysPt)p.data * 16;
    if (!p.changed && (mem_readd(data + 0x1b60) != p.saved[0] || mem_readd(data + 0x1b64) != p.saved[1])) {
        p.changed = true;
        p.remaining = 128;
        LezacInterruptEmit("saved_target_changed");
    }
    for (unsigned i = 0; i < 2; ++i) {
        if (code != p.vector_cs[i] || ip != p.vector_ip[i]) continue;
        unsigned& count = p.changed ? p.changed_entries[i] : p.entries[i];
        if (++count <= 2) {
            p.remaining = p.changed ? 256 : 128;
            LezacInterruptEmit(i == 0 ? "keyboard_enter" : "timer_enter");
            if (p.changed) LezacInterruptVga(i == 0 ? "vga_after_changed_keyboard" : "vga_after_changed_timer");
        }
    }
    if (p.changed && code == mem_readw(data + 0x1b62) && p.faults < 16 &&
        (ip == mem_readw(data + 0x1b60) || mem_readw(SegPhys(cs) + ip) == 0xffff)) {
        LezacInterruptEmit("changed_keyboard_target");
        if (p.faults == 0) p.remaining = 512;
        if (p.faults == 0 || p.faults == 1) LezacInterruptVga("vga_at_changed_target");
        ++p.faults;
    }
    if (p.remaining) {
        LezacInterruptEmit("instruction");
        --p.remaining;
    }
}
