#include "../cpu/lezac_clock_observation.h"

void LezacReadGfxFormat(Bit32u* fields) {
    if (!sdl.surface || !sdl.surface->format) return;
    const SDL_PixelFormat* f=sdl.surface->format;
    const Bit32u values[] = {f->BitsPerPixel,f->BytesPerPixel,f->Rmask,f->Gmask,f->Bmask,f->Amask,
        f->Rshift,f->Gshift,f->Bshift,sdl.surface->flags,(Bit32u)sdl.surface->offset,sdl.active,
        !sdl.updating || LezacRenderUpdating(),(Bit32u)sdl.desktop.type,sdl.blit.surface!=0,
        f->Rloss,f->Gloss,f->Bloss};
    std::memcpy(fields,values,sizeof(values));
}

void LezacReadNativePalette(Bit32u* mapped) {
    if (sdl.desktop.type!=SCREEN_SURFACE || !sdl.surface || !sdl.surface->format) return;
    LezacRenderPaletteObservation p = {};
    LezacReadRenderPalette(p);
    for (unsigned i=0;i<256;++i)
        mapped[i]=GFX_GetRGB((Bit8u)(p.rgb[i]>>16),(Bit8u)(p.rgb[i]>>8),(Bit8u)p.rgb[i]);
}
