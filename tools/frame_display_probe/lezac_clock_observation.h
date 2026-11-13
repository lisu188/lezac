#pragma once
#include <cstring>
#include "cpu.h"
#include "pic.h"

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
