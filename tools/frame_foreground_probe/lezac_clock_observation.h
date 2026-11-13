#pragma once
#include <cstring>
#include "cpu.h"
#include "pic.h"
#include "timer.h"

struct LezacClockObservation {
    Bitu pending, active, active_lines, masked_lines, inservice_lines;
    bool special, auto_eoi, queue_overflow;
    Bitu irq0_vector, pit_count;
    Bit8u pit_mode;
    bool pit_update;
    Bit32u pit_delay_bits;
    Bit64u pit_start_bits;
    unsigned queue_count;
    struct Event { Bit32u index_bits; Bitu kind, value; } queue[64];
};

bool LezacClockIsPit0(PIC_EventHandler handler);
void LezacReadPit0(LezacClockObservation& result);
void LezacReadPicClock(LezacClockObservation& result);

struct LezacDeviceObservation {
    Bit64u values[25], delay_bits[6];
    unsigned ticker_count;
    Bitu ticker_kinds[16];
    bool ticker_overflow;
};
unsigned LezacClockVgaKind(PIC_EventHandler handler);
unsigned LezacClockKeyboardKind(TIMER_TickHandler handler);
unsigned LezacClockMixerKind(TIMER_TickHandler handler);
void LezacReadVgaClock(LezacDeviceObservation& result);
void LezacReadRenderClock(LezacDeviceObservation& result);
void LezacReadKeyboardClock(LezacDeviceObservation& result);
void LezacReadMixerClock(LezacDeviceObservation& result);
void LezacReadDeviceClock(LezacDeviceObservation& result);
bool LezacReadHudPixels(unsigned char* result);

struct LezacRenderPaletteObservation {
    Bit32u fields[4], rgb[256], lut[256];
    Bit8u modified[256];
};
void LezacReadRenderPalette(LezacRenderPaletteObservation& result);
bool LezacRenderUpdating();
void LezacReadGfxFormat(Bit32u* fields);
void LezacReadNativePalette(Bit32u* mapped);
