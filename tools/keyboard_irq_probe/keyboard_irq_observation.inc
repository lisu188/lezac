#include "../cpu/keyboard_irq_api.h"

void LezacReadKeyboardHardware(LezacKeyboardHardwareObservation& result) {
    std::memcpy(result.buffer, keyb.buffer, sizeof(result.buffer));
    const Bit64u values[] = {keyb.used, keyb.pos, keyb.repeat.key, keyb.repeat.wait,
        keyb.repeat.pause, keyb.repeat.rate, keyb.command, keyb.p60data,
        keyb.p60changed, keyb.active, keyb.scanning, keyb.scheduled, port_61_data};
    std::memcpy(result.values, values, sizeof(values));
}
