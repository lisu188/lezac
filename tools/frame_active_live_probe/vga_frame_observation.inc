// Copy the active chained-VGA backing directly, without changing VGA read latches.
bool LezacReadFrameVga(unsigned char* result) {
    const bool profile=machine==MCH_VGA && vga.mode==M_VGA && vga.config.chained &&
        vga.config.compatible_chain4 && vga.draw.linear_base==vga.fastmem &&
        !vga.svga.bank_write_full;
    if (!profile) return false;
    std::memcpy(result,vga.fastmem,65536);
    return true;
}
