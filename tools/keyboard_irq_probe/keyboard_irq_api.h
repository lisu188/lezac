#pragma once
#include "dosbox.h"

struct LezacKeyboardHardwareObservation {
    Bit8u buffer[32];
    Bit64u values[13];
};
void LezacReadKeyboardHardware(LezacKeyboardHardwareObservation& result);
