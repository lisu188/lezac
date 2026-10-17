#include "../cpu/lezac_clock_observation.h"

unsigned LezacClockVgaKind(PIC_EventHandler handler) {
    if (handler == VGA_DrawPart) return 3;
    if (handler == VGA_VerticalTimer) return 4;
    if (handler == VGA_DisplayStartLatch) return 5;
    if (handler == VGA_PanningLatch) return 6;
    if (handler == VGA_VertInterrupt) return 7;
    return 2;
}
void LezacReadVgaClock(LezacDeviceObservation& result) {
    const Bit64u values[] = {machine, vga.mode, vga.draw.mode, vga.draw.parts_left,
        vga.draw.parts_total, vga.draw.parts_lines, vga.draw.lines_done, vga.draw.lines_total,
        vga.draw.vblank_skip, vga.draw.vret_triggered, vga.crtc.vertical_retrace_end};
    std::memcpy(result.values, values, sizeof(values));
    const double delays[] = {vga.draw.delay.parts, vga.draw.delay.vtotal, vga.draw.delay.vrstart,
        vga.draw.delay.vrend, vga.draw.delay.vdend, vga.draw.delay.htotal};
    std::memcpy(result.delay_bits, delays, sizeof(delays));
}
