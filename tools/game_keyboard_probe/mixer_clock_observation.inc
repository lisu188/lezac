#include "../cpu/lezac_clock_observation.h"

unsigned LezacClockMixerKind(TIMER_TickHandler handler) {
    if (handler == MIXER_Mix_NoSound) return 11;
    if (handler == MIXER_Mix) return 12;
    return 2;
}
void LezacReadMixerClock(LezacDeviceObservation& result) {
    result.values[21] = mixer.nosound;
    for (MixerChannel* channel = mixer.channels; channel; channel = channel->next) {
        result.values[22] += channel->enabled;
        ++result.values[24];
    }
    result.values[23] = CaptureState;
}
