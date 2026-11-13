#include "../cpu/lezac_clock_observation.h"

void LezacReadRenderClock(LezacDeviceObservation& result) {
    const Bit64u values[] = {render.active, render.updating, render.frameskip.count,
        render.frameskip.max, render.scale.clearCache, render.pal.changed};
    std::memcpy(result.values + 11, values, sizeof(values));
}
