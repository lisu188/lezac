#include "../cpu/lezac_clock_observation.h"

unsigned LezacClockKeyboardKind(TIMER_TickHandler handler) {
    return handler == KEYBOARD_TickHandler ? 10 : 2;
}
void LezacReadKeyboardClock(LezacDeviceObservation& result) {
    const Bit64u values[] = {keyb.repeat.wait, keyb.repeat.key, keyb.used, keyb.scheduled};
    std::memcpy(result.values + 17, values, sizeof(values));
}
