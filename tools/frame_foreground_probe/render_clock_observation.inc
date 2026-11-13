#include "../cpu/lezac_clock_observation.h"

void LezacReadRenderClock(LezacDeviceObservation& result) {
    const Bit64u values[] = {render.active, render.updating, render.frameskip.count,
        render.frameskip.max, render.scale.clearCache, render.pal.changed};
    std::memcpy(result.values + 11, values, sizeof(values));
}

bool LezacRenderUpdating() { return render.updating; }

void LezacReadRenderPalette(LezacRenderPaletteObservation& result) {
    const Bit32u fields[] = {render.pal.first, render.pal.last, render.scale.inMode, render.scale.outMode};
    std::memcpy(result.fields, fields, sizeof(fields));
    for (unsigned i=0;i<256;++i) {
        result.rgb[i] = (render.pal.rgb[i].red<<16)|(render.pal.rgb[i].green<<8)|render.pal.rgb[i].blue;
        result.lut[i] = render.pal.lut.b32[i];
        result.modified[i] = render.pal.modified[i];
    }
}
