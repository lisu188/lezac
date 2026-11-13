#include <cstdlib>

// Host-only observation before normal-core decode; guest state is read-only.
struct LezacPacingProbeState {
    FILE* output;
    bool initialized;
    Bit16u code, data;
    Bit64u dispatch;
    unsigned records;
};
static LezacPacingProbeState lezac_pacing_probe = {};

static void LezacPacingEmit(const char* kind) {
    LezacPacingProbeState& p = lezac_pacing_probe;
    if (!p.output) return;
    if (p.records >= 10000 || ftell(p.output) >= 2 * 1024 * 1024) {
        fprintf(p.output, "cap\n");
        fclose(p.output);
        p.output = 0;
        return;
    }
    const PhysPt data = (PhysPt)p.data * 16;
    const long long clock = (long long)PIC_Ticks * CPU_CycleMax +
        CPU_CycleMax - CPU_CycleLeft - CPU_Cycles;
    fprintf(p.output, "%s,%llu,%lld,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
        kind, (unsigned long long)p.dispatch, clock, (unsigned long long)PIC_Ticks,
        (unsigned)SegValue(cs), (unsigned)(Bit16u)reg_eip, (unsigned)SegValue(ds),
        (unsigned)SegValue(ss), (unsigned)reg_sp, (unsigned)mem_readw(data + 0x78c2),
        (unsigned)mem_readw(data + 0x2074), (unsigned)mem_readw(data + 0x78cc),
        (unsigned)mem_readw(data + 0x78ca), (unsigned)mem_readw(data + 0x78d0),
        (unsigned)mem_readw(data + 0x78ce), (unsigned)mem_readb(data + 0x79a4),
        (unsigned)mem_readb(data + 0x79a8), (unsigned)mem_readb(data + 0x79a9),
        (unsigned)mem_readb(data + 0x79aa), (unsigned)mem_readb(data + 0x79ab),
        (unsigned)mem_readb(data + 0x79ac), (unsigned)mem_readw(data + 0x78c6),
        (unsigned)mem_readw(data + 0x78c8), (unsigned)mem_readb(data + 0x79b5));
    ++p.records;
}

static void LezacPacingExit() {
    if (lezac_pacing_probe.output) {
        // Guest memory may already be released during emulator shutdown.
        fprintf(lezac_pacing_probe.output, "end\n");
        fclose(lezac_pacing_probe.output);
        lezac_pacing_probe.output = 0;
    }
}

static void LezacWorkProbe() {
    LezacPacingProbeState& p = lezac_pacing_probe;
    if (!p.initialized) {
        p.initialized = true;
        const char* path = getenv("LEZAC_PACING_TRACE");
        if (path) p.output = fopen(path, "wx");
        if (p.output) {
            fprintf(p.output, "kind,dispatch,clock,pic_ticks,cs,ip,ds,ss,sp,frame_counter,measured_word,delay,minimum,auxiliary,character,previous_minute,previous_second,previous_hundredth,current_minute,current_second,current_hundredth,word_78c6,word_78c8,byte_79b5\n");
            atexit(LezacPacingExit);
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
            LezacPacingEmit("identified");
        }
    }
    if (!p.code || code != p.code) return;
    switch (ip) {
        case 0x7903: LezacPacingEmit("frame_before"); break;
        case 0x7919: LezacPacingEmit("time_begin"); break;
        case 0x792a: LezacPacingEmit("time_result"); break;
        case 0x7966: LezacPacingEmit("measurement"); break;
        case 0x799a: LezacPacingEmit("adjust_begin"); break;
        case 0x79cd: LezacPacingEmit("adjust_end"); break;
        case 0x79df: LezacPacingEmit("delay_before"); break;
        case 0x79e8: LezacPacingEmit("delay_after"); break;
    }
}
