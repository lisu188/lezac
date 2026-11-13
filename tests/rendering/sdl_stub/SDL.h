#pragma once
#include <cstdint>
using Uint32 = uint32_t;
struct SDL_Window;
struct SDL_Renderer;
struct SDL_Texture;
struct SDL_Rect;
inline constexpr int SDL_WINDOWPOS_CENTERED = 0x2fff0000;
inline constexpr Uint32 SDL_WINDOW_SHOWN = 4;
inline constexpr Uint32 SDL_RENDERER_SOFTWARE = 1;
inline constexpr Uint32 SDL_RENDERER_ACCELERATED = 2;
inline constexpr Uint32 SDL_PIXELFORMAT_ARGB8888 = 0x16362004;
inline constexpr int SDL_TEXTUREACCESS_STREAMING = 1;
SDL_Window* SDL_CreateWindow(const char*, int, int, int, int, Uint32);
SDL_Renderer* SDL_CreateRenderer(SDL_Window*, int, Uint32);
SDL_Texture* SDL_CreateTexture(SDL_Renderer*, Uint32, int, int, int);
void SDL_DestroyWindow(SDL_Window*);
void SDL_DestroyRenderer(SDL_Renderer*);
void SDL_DestroyTexture(SDL_Texture*);
int SDL_RenderSetLogicalSize(SDL_Renderer*, int, int);
int SDL_UpdateTexture(SDL_Texture*, const SDL_Rect*, const void*, int);
int SDL_RenderClear(SDL_Renderer*);
int SDL_RenderCopy(SDL_Renderer*, SDL_Texture*, const SDL_Rect*, const SDL_Rect*);
void SDL_RenderPresent(SDL_Renderer*);
const char* SDL_GetError();
void SDL_ClearError();
