#include <SDL.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

using Bit8u=uint8_t;using Bit16u=uint16_t;using Bit32u=uint32_t;using Bitu=uint64_t;
enum {scalerMode8,scalerMode15,scalerMode16,scalerMode32};
enum {SCREEN_SURFACE,SCREEN_SURFACE_DDRAW,SCREEN_OVERLAY,SCREEN_OPENGL};
struct GFX_PalEntry {Bit8u red,green,blue;};
struct {
    struct {Bitu first,last;bool changed;GFX_PalEntry rgb[256];Bit8u modified[256];union {Bit32u b32[256];Bit16u b16[256];} lut;} pal;
    struct {Bitu outMode;} scale;
} render;
struct {struct {int type;} desktop;SDL_Surface* surface;} sdl;
Bitu GFX_GetRGB(Bit8u,Bit8u,Bit8u);
void GFX_SetPalette(Bitu,Bitu,GFX_PalEntry*) {std::abort();}
// ORIGINAL_FUNCTIONS

void number(uint32_t value) {for(unsigned i=0;i<4;++i)std::putchar(static_cast<int>((value>>(8*i))&255u));}
void state() {
    number(static_cast<uint32_t>(render.pal.first));number(static_cast<uint32_t>(render.pal.last));number(render.pal.changed);
    for(const auto& color:render.pal.rgb)number((uint32_t{color.red}<<16)|(uint32_t{color.green}<<8)|color.blue);
    for(auto value:render.pal.lut.b32)number(value);
    for(auto value:render.pal.modified)std::putchar(value);
}
int main() {
    Dl_info library = {};
    if (!dladdr(reinterpret_cast<void*>(SDL_MapRGB),&library) || !library.dli_fname)return 2;
    std::fprintf(stderr,"lezac_sdl_library=%s\n",library.dli_fname);
    std::fwrite("LZPAL001",1,8,stdout);number(96);
    const unsigned orders[6][3]={{16,8,0},{16,0,8},{8,16,0},{8,0,16},{0,16,8},{0,8,16}};
    for(const auto& shifts:orders)for(bool alpha:{false,true})for(unsigned profile=0;profile<8;++profile) {
        std::memset(&render,0,sizeof(render));render.scale.outMode=scalerMode32;
        sdl.surface=SDL_CreateRGBSurface(0,1,1,32,255u<<shifts[0],255u<<shifts[1],255u<<shifts[2],alpha?0xff000000u:0);
        if(!sdl.surface)return 1;sdl.desktop.type=SCREEN_SURFACE;
        const auto* f=sdl.surface->format;
        const uint32_t format[]={f->BitsPerPixel,f->BytesPerPixel,f->Rmask,f->Gmask,f->Bmask,f->Amask,f->Rshift,f->Gshift,f->Bshift,0,0,1,1,0,0,f->Rloss,f->Gloss,f->Bloss};
        for(auto value:format)number(value);
        render.pal.first=profile==0?256:profile==3?255:profile==4?31:0;
        render.pal.last=profile==0?0:profile==2?0:profile==4?67:255;
        render.pal.changed=(profile%2)==0;
        for(unsigned i=0;i<256;++i) {
            render.pal.rgb[i]={static_cast<Bit8u>(i),static_cast<Bit8u>(255-i),static_cast<Bit8u>(i*19u)};
            render.pal.lut.b32[i]=static_cast<Bit32u>(GFX_GetRGB(render.pal.rgb[i].red,render.pal.rgb[i].green,render.pal.rgb[i].blue));
            if(profile!=5 && i%3==0)render.pal.lut.b32[i]^=0x005a3c69u;
            render.pal.modified[i]=i%5==0;
        }
        state();Check_Palette();state();SDL_FreeSurface(sdl.surface);
    }
    return std::ferror(stdout)?1:0;
}
