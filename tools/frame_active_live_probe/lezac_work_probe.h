#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <vector>
#include <cstdarg>
#include <string>
#include <zlib.h>
#include "cpu.h"
#include "pic.h"
#include "lezac_clock_observation.h"

extern Bitu CPU_flag_id_toggle;

// Recovery-only observation; no guest writes or lazy-flag materialization.
struct LezacDosTimeProbeState {
    gzFile output;
    bool initialized, waiting, windowed, frame_waiting;
    Bit16u code, data, psp, vector_cs, vector_ip, return_cs, return_ip, stack_base, stack_ss;
    Bit64u dispatch;
    unsigned records, call, remaining;
    unsigned full_windows, measurements;
    unsigned keyboard_class, keyboard_entry, categories;
    bool irq_in_window, entry_game_vector, target_completed, frame_control_seen;
    bool render_seen, render_irq;
};
inline LezacDosTimeProbeState lezac_dos_time_probe = {};
inline LezacRenderPaletteObservation lezac_previous_palette = {};
inline bool lezac_previous_palette_valid = false;

bool LezacReadFrameVga(unsigned char* result);

inline bool LezacActiveMemory(const char* phase) {
    const auto& p=lezac_dos_time_probe;
    const char* prefix=getenv("LEZAC_ACTIVE_MEMORY_PREFIX");
    if (!prefix) return false;
    char path[512];
    const int length=std::snprintf(path,sizeof(path),"%s-%u-%s.ram.gz",prefix,p.call,phase);
    if (length<0 || (unsigned)length>=sizeof(path)) return false;
    std::vector<unsigned char> bytes(MemBase,MemBase+1048576);
    if (!LezacReadFrameVga(bytes.data()+0xa0000)) return false;
    gzFile output=gzopen(path,"wb1");
    if (!output) return false;
    const int written=gzwrite(output,bytes.data(),(unsigned)bytes.size());
    const int closed=gzclose(output);
    return written==(int)bytes.size() && closed==Z_OK;
}

inline std::vector<std::string> lezac_active_previous;

inline void LezacActivePrintf(std::string& line,const char* format,...) {
    char buffer[2048];
    va_list arguments;va_start(arguments,format);
    const int count=std::vsnprintf(buffer,sizeof(buffer),format,arguments);
    va_end(arguments);
    if (count<0 || (unsigned)count>=sizeof(buffer)) {line+="format_failed";return;}
    line.append(buffer,(unsigned)count);
}

inline bool LezacActiveWrite(gzFile output,const std::string& line,bool entry) {
    if (line.empty() || line.back()!='\n') return false;
    std::vector<std::string> values;
    size_t start=0;
    for (size_t i=0;i<line.size();++i) {
        if (line[i]==',' || line[i]=='\n') {values.push_back(line.substr(start,i-start));start=i+1;}
    }
    if (!lezac_active_previous.empty() && values.size()!=lezac_active_previous.size()) return false;
    for (size_t i=0;i<values.size();++i) {
        if (i) gzprintf(output,",");
        if (!entry && !lezac_active_previous.empty() && values[i]==lezac_active_previous[i]) gzprintf(output,"~");
        else gzprintf(output,"%s",values[i].c_str());
    }
    gzprintf(output,"\n");lezac_active_previous=std::move(values);return true;
}

inline void LezacDosTimeEmit(const char* kind) {
    auto& p = lezac_dos_time_probe;
    if (!p.output) return;
    LezacClockObservation observation = {};
    LezacReadPicClock(observation);
    LezacReadPit0(observation);
    if (p.records >= 1000000 || gztell(p.output) >= 1024LL * 1024 * 1024) {
        gzprintf(p.output, "cap\n");
        gzclose(p.output);
        p.output = 0;
        return;
    }
    std::string line;
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
    LezacActivePrintf(line, "%s,%llu,%lld", kind, (unsigned long long)p.dispatch, clock);
    for (unsigned i = 0; i < sizeof(values)/sizeof(values[0]); ++i)
        LezacActivePrintf(line, ",%llu", values[i]);
    LezacActivePrintf(line, ",");
    for (unsigned i = 0; i < 8; ++i)
        LezacActivePrintf(line, "%02x", (unsigned)mem_readb(SegPhys(cs) + (Bit16u)(reg_eip + i)));
    LezacActivePrintf(line, ",");
    for (unsigned i = 0; i < 128; ++i)
        LezacActivePrintf(line, "%02x", (unsigned)mem_readb((PhysPt)p.stack_ss * 16 + (Bit16u)(p.stack_base + i)));
    LezacActivePrintf(line, ",");
    for (unsigned i = 0; i < 15; ++i)
        LezacActivePrintf(line, "%02x", (unsigned)mem_readb((PhysPt)p.vector_cs * 16 + (Bit16u)(p.vector_ip + i)));
    LezacActivePrintf(line, ",%u,%u,%u,%u,%u,%u,", (unsigned)mem_readb(0x440), (unsigned)mem_readb(0x43f),
        (unsigned)mem_readw(0x70), (unsigned)mem_readw(0x72), (unsigned)p.stack_base, (unsigned)p.stack_ss);
    const PhysPt data = (PhysPt)p.data * 16;
    for (unsigned i = 0; i < 2; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x78c0 + i));
    for (unsigned i = 0; i < 3; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x79a0 + i));
    for (unsigned i = 0; i < 5; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x79c0 + i));
    LezacActivePrintf(line, ",");
    if (std::strcmp(kind, "keyboard_enter") == 0) {
        const PhysPt bank = (PhysPt)mem_readw(data + 0x79c2) * 16 + mem_readw(data + 0x79c0);
        for (unsigned i = 0; i < 780; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(bank + i));
    }
    LezacActivePrintf(line, ",%lld,%lld,%lld,%llu,%llu,%llu,%llu,%llu,%u,%u,%llu,%u,%llu,%u,%u,%llu,%u,",
        (long long)CPU_Cycles, (long long)CPU_CycleLeft, (long long)CPU_IODelayRemoved,
        (unsigned long long)observation.active, (unsigned long long)observation.pending,
        (unsigned long long)observation.active_lines, (unsigned long long)observation.inservice_lines,
        (unsigned long long)observation.masked_lines, observation.special ? 1u : 0u,
        observation.auto_eoi ? 1u : 0u, (unsigned long long)observation.irq0_vector,
        (unsigned)observation.pit_delay_bits, (unsigned long long)observation.pit_count,
        (unsigned)observation.pit_mode, observation.pit_update ? 1u : 0u,
        (unsigned long long)observation.pit_start_bits, observation.queue_overflow ? 1u : 0u);
    for (unsigned i = 0; i < observation.queue_count; ++i) {
        if (i) LezacActivePrintf(line, ";");
        LezacActivePrintf(line, "%08x:%llu:%llu", (unsigned)observation.queue[i].index_bits,
            (unsigned long long)observation.queue[i].kind, (unsigned long long)observation.queue[i].value);
    }
    LezacActivePrintf(line, ",%u,%u,", p.irq_in_window ? 1u : 0u, p.target_completed ? 1u : 0u);
    for (unsigned i = 0; i < 2; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x2074 + i));
    for (unsigned i = 0; i < 9; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x79a4 + i));
    LezacActivePrintf(line, ",");
    for (unsigned i = 0; i < 4; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x78c6 + i));
    LezacActivePrintf(line, "%02x,", (unsigned)mem_readb(data + 0x79b5));
    for (unsigned i = 0; i < 2; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x78c2 + i));
    for (unsigned i = 0; i < 4; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x78ca + i));
    for (unsigned i = 0; i < 2; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x7f68 + i));
    LezacActivePrintf(line, "%02x,", (unsigned)mem_readb(0x400));
    LezacDeviceObservation devices = {};
    LezacReadDeviceClock(devices);
    for (unsigned i = 0; i < 25; ++i) {
        if (i) LezacActivePrintf(line, ";");
        LezacActivePrintf(line, "%llu", (unsigned long long)devices.values[i]);
    }
    for (unsigned i = 0; i < 6; ++i) LezacActivePrintf(line, ";%llu", (unsigned long long)devices.delay_bits[i]);
    LezacActivePrintf(line, ",%u,", devices.ticker_overflow ? 1u : 0u);
    for (unsigned i = 0; i < devices.ticker_count; ++i) {
        if (i) LezacActivePrintf(line, ";");
        LezacActivePrintf(line, "%u", (unsigned)devices.ticker_kinds[i]);
    }
    const Bit16u keyboard_ip = mem_readw(0x58), keyboard_cs = mem_readw(0x5a);
    LezacActivePrintf(line, ",%u,%u,", (unsigned)keyboard_ip, (unsigned)keyboard_cs);
    for (unsigned i = 0; i < 20; ++i)
        LezacActivePrintf(line, "%02x", (unsigned)mem_readb((PhysPt)keyboard_cs * 16 + (Bit16u)(keyboard_ip + i)));
    LezacActivePrintf(line, ",%02x%02x,", (unsigned)mem_readb(data + 0x7f6d), (unsigned)mem_readb(data + 0x7f6e));
    for (unsigned i = 0; i < 132; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(0x400 + i));
    LezacActivePrintf(line, ",%u,%u,%02x,", p.keyboard_entry, p.keyboard_class,
        (unsigned)mem_readb(data + 0x2058));
    for (unsigned i = 0; i < 30; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x206e + i));
    for (unsigned i = 0; i < 47; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x79b3 + i));
    for (unsigned i = 0; i < 7; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x1aae + i));
    for (unsigned i = 0; i < 2; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + 0x1afa + i));
    LezacActivePrintf(line, ",");
    if (std::strcmp(kind, "keyboard_enter") == 0) {
        const unsigned font = mem_readw(data + 0x2070);
        for (unsigned i = 0; i < 640; ++i) LezacActivePrintf(line, "%02x", (unsigned)mem_readb(data + (Bit16u)(font + i)));
    }
    unsigned char pixels[272] = {};
    const bool video_profile = LezacReadHudPixels(pixels);
    LezacActivePrintf(line, ",");
    for (unsigned i = 0; i < 272; ++i) LezacActivePrintf(line, "%02x", (unsigned)pixels[i]);
    LezacActivePrintf(line, ",%u,", video_profile ? 1u : 0u);
    for (unsigned i=0;i<32;++i) LezacActivePrintf(line,"%02x",(unsigned)mem_readb((PhysPt)p.psp*16+0x2e + i));
    LezacRenderPaletteObservation palette = {};
    LezacReadRenderPalette(palette);
    LezacActivePrintf(line,",");
    const bool entry=std::strcmp(kind,"keyboard_enter")==0;
    if (entry || !lezac_previous_palette_valid || std::memcmp(&palette,&lezac_previous_palette,sizeof(palette))) {
        for (unsigned i=0;i<4;++i) LezacActivePrintf(line,"%u;",(unsigned)palette.fields[i]);
        for (unsigned i=0;i<256;++i) LezacActivePrintf(line,"%08x",(unsigned)palette.rgb[i]);
        LezacActivePrintf(line,";");
        for (unsigned i=0;i<256;++i) LezacActivePrintf(line,"%08x",(unsigned)palette.lut[i]);
        LezacActivePrintf(line,";");
        for (unsigned i=0;i<256;++i) LezacActivePrintf(line,"%02x",(unsigned)palette.modified[i]);
        lezac_previous_palette=palette;lezac_previous_palette_valid=true;
    }
    Bit32u format[18] = {};
    LezacReadGfxFormat(format);
    LezacActivePrintf(line,",");
    for (unsigned i=0;i<18;++i) LezacActivePrintf(line,"%s%u",i?";":"",(unsigned)format[i]);
    LezacActivePrintf(line,",");
    if (entry) {
        Bit32u native[256] = {};LezacReadNativePalette(native);
        for (unsigned i=0;i<256;++i) LezacActivePrintf(line,"%08x",(unsigned)native[i]);
    }
    LezacActivePrintf(line,"\n");
    if (!LezacActiveWrite(p.output,line,std::strcmp(kind,"keyboard_enter")==0)) {
        gzprintf(p.output,"encoding_failed\n");gzclose(p.output);p.output=0;return;
    }
    ++p.records;
}

inline void LezacDosTimeExit() {
    if (lezac_dos_time_probe.output) {
        gzprintf(lezac_dos_time_probe.output, "end\n");
        gzclose(lezac_dos_time_probe.output);
        lezac_dos_time_probe.output = 0;
    }
}

inline void LezacDosTimeCallback(const char*, Bit16u) {}

inline void LezacWorkProbe() {
    auto& p = lezac_dos_time_probe;
    if (!p.initialized) {
        p.initialized = true;
        const char* path = getenv("LEZAC_FRAME_FOREGROUND_TRACE");
        if (path) p.output = gzopen(path, "wb1");
        if (p.output) {
            gzprintf(p.output,"active-sparse-v1\n");
            gzprintf(p.output, "kind,dispatch,clock,call,windowed,pic_ticks,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,flags,defined_flags,bios_ticks,psp,psp_stack,return_ip,return_cs,vector_cs,vector_ip,cycle_max,id_toggle,opcode,stack,vector_stub,motor,drive,int1c_ip,int1c_cs,stack_base,stack_ss,globals,bank,cpu_cycles,cpu_left,io_delay_removed,pic_active,pic_pending,active_lines,inservice_lines,masked_lines,pic_special,pic_auto_eoi,irq0_vector,pit0_delay_bits,pit0_count,pit0_mode,pit0_update,pit0_start_bits,queue_overflow,queue,irq_in_window,target_completed,frame_globals,display_globals,pacing_globals,devices,ticker_overflow,tickers,keyboard_base,keyboard_cs,keyboard_stub,crt_globals,bios_keyboard,keyboard_entry,keyboard_class,drain_key,hud_globals,hud_font,hud_pixels,hud_vga_profile,psp_bytes,render_palette,gfx_format,native_palette\n");
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
    if (!p.frame_waiting && code == p.code && ip == 0x7903) {
        const PhysPt data = (PhysPt)p.data * 16;
        LezacDeviceObservation d = {};LezacReadDeviceClock(d);
        const unsigned frame=mem_readw(data+0x78c2);
        const unsigned delay=mem_readw(data+0x78cc);
        const bool word_changed=mem_readw(data+0x2088)!=mem_readw(data+0x208a);
        const bool byte_changed=mem_readb(data+0x79b5)!=mem_readb(data+0x79b6);
        LezacClockObservation c = {};LezacReadPicClock(c);
        float pit_due=-1;
        for(unsigned i=0;i<c.queue_count;++i) if(c.queue[i].kind==1) {
            float due=0;std::memcpy(&due,&c.queue[i].index_bits,sizeof(due));pit_due=due-PIC_TickIndex();
        }
        if(frame<256) {
            const char* scan=getenv("LEZAC_FRAME_FOREGROUND_SCAN");
            if(scan) {
                FILE* log=fopen(scan,"a");
                if(log) {fprintf(log,"%u,%u,%u,%u,%llu,%llu,%llu,%llu,%llu,%llu,%u,%u,%.9g\n",frame,
                    (unsigned)mem_readw(data+0x2074),(unsigned)mem_readw(data+0x78ca),(unsigned)mem_readw(data+0x78cc),
                    (unsigned long long)d.values[12],(unsigned long long)d.values[16],(unsigned long long)d.values[17],
                    (unsigned long long)d.values[18],(unsigned long long)d.values[19],(unsigned long long)d.values[20],
                    word_changed?1u:0u,byte_changed?1u:0u,(double)pit_due);fclose(log);}
            }
        }
        if (p.full_windows >= 4) return;
        if (!mem_readb(data+0x79e6) && !mem_readb(data+0x79e7)) return;
        if (mem_readb(data+0x79c4)) return;
        if (d.values[17] || d.values[18] || d.values[19] || d.values[20]) return;
        if (c.queue_overflow) return;
        for (unsigned i=0;i<c.queue_count;++i) if(c.queue[i].kind<1 || c.queue[i].kind>7 || c.queue[i].kind==2) return;
        if(frame%30==29) return;
        const unsigned category=(p.categories&1u)?1u:0u;
        if (category==0) {
            if((!word_changed && !byte_changed) || delay>20) return;
        } else {
            const char* input_done=getenv("LEZAC_ACTIVE_INPUT_DONE");
            FILE* marker=input_done?fopen(input_done,"r"):0;
            if (!marker) return;
            fclose(marker);
            if(delay<2 || delay>20 || pit_due<=delay+0.25f || pit_due>=delay+12.0f) return;
        }
        p.keyboard_class = category; p.keyboard_entry = ip;
        p.call = ++p.full_windows;
        p.windowed = p.frame_waiting = true;
        p.irq_in_window = p.render_seen = p.render_irq = false;
        p.entry_game_vector = true;
        p.stack_ss = SegValue(ss); p.stack_base = (Bit16u)(reg_sp - 80);
        p.return_ip = 0x7a57; p.return_cs = p.code; p.remaining = 500000;
        if (!LezacActiveMemory("initial")) {
            gzprintf(p.output,"snapshot_failed\n");gzclose(p.output);p.output=0;return;
        }
        LezacDosTimeEmit("keyboard_enter");
    }
    if (!p.frame_waiting) return;
    if (code == p.return_cs && ip == p.return_ip) {
        if (!LezacActiveMemory("final")) {
            gzprintf(p.output,"snapshot_failed\n");gzclose(p.output);p.output=0;return;
        }
        if (p.keyboard_class==0 || p.render_irq) p.categories |= 1u << p.keyboard_class;
        p.target_completed = p.categories==3;
        LezacDosTimeEmit("keyboard_return");
        if (p.output) gzflush(p.output, Z_SYNC_FLUSH);
        p.frame_waiting = false;
        if(p.keyboard_class==0) {
            const char* path=getenv("LEZAC_FRAME_FOREGROUND_FIRST_DONE");
            if(path) {FILE* marker=fopen(path,"wx");if(marker){fprintf(marker,"1\n");fclose(marker);}}
        }
        if (p.target_completed) {
            const char* path = getenv("LEZAC_FRAME_FOREGROUND_TARGET");
            if (path) {
                FILE* marker = fopen(path, "wx");
                if (marker) { fprintf(marker, "1\n"); fclose(marker); }
            }
        }
        return;
    }
    if (code == p.code && ip == 0x7a13) p.render_seen=true;
    if (code == 0xf000 && ip == 0xfea5) {
        p.irq_in_window = true;
        if (p.render_seen) p.render_irq=true;
    }
    if (!p.remaining) {
        LezacDosTimeEmit("window_exhausted");
        p.frame_waiting = false;
        return;
    }
    LezacDosTimeEmit("instruction");
    --p.remaining;
}
