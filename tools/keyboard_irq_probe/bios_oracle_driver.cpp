#include <array>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include "SDL_version.h"

using Bit8u = uint8_t;
using Bit16u = uint16_t;
using Bitu = uintptr_t;
constexpr unsigned BIOS_KEYBOARD_FLAGS1 = 0x417, BIOS_KEYBOARD_FLAGS2 = 0x418;
constexpr unsigned BIOS_KEYBOARD_TOKEN = 0x419, BIOS_KEYBOARD_FLAGS3 = 0x496, BIOS_KEYBOARD_LEDS = 0x497;
constexpr unsigned BIOS_KEYBOARD_BUFFER_HEAD = 0x41a, BIOS_KEYBOARD_BUFFER_TAIL = 0x41c;
constexpr unsigned BIOS_KEYBOARD_BUFFER_START = 0x480, BIOS_KEYBOARD_BUFFER_END = 0x482;
constexpr unsigned MAX_SCAN_CODE = 0x58, MCH_PCJR = 0, CBRET_NONE = 0;
unsigned machine = 5;
uint8_t reg_al = 0;
uint16_t reg_ip = 0x1234;
std::array<uint8_t, 0x500> memory{};
std::vector<std::pair<uint16_t, uint8_t>> ports;
struct PauseHandoff {};

uint8_t mem_readb(unsigned at) {return memory.at(at);}
uint16_t mem_readw(unsigned at) {return static_cast<uint16_t>(mem_readb(at) | uint16_t{mem_readb(at + 1)} << 8);}
void mem_writeb(unsigned at, uint8_t value) {memory.at(at) = value;}
void mem_writew(unsigned at, uint16_t value) {mem_writeb(at, static_cast<uint8_t>(value)); mem_writeb(at + 1, static_cast<uint8_t>(value >> 8));}
void real_writew(uint16_t segment, uint16_t offset, uint16_t value) {mem_writew(segment * 16u + offset, value);}
bool DOS_LayoutKey(Bitu, Bit8u, Bit8u, Bit8u) {return false;}
void IO_Write(uint16_t port, uint8_t value) {ports.emplace_back(port, value);}
void CALLBACK_Idle() {throw PauseHandoff{};}

#if SDL_VERSION_ATLEAST(1, 2, 14)
#define CAN_USE_LOCK 1
#endif

// ORIGINAL_FUNCTIONS

void byte(uint8_t value) {std::putchar(value);}
void word(uint16_t value) {byte(static_cast<uint8_t>(value)); byte(static_cast<uint8_t>(value >> 8));}
void dword(uint32_t value) {word(static_cast<uint16_t>(value)); word(static_cast<uint16_t>(value >> 16));}

int main() {
    static_assert(SDL_VERSION_ATLEAST(1, 2, 14));
    std::fwrite("LZBIOSK1", 1, 8, stdout);
    dword(65536);
    for (const auto& entry : scan_to_scanascii) {word(entry.normal); word(entry.shift); word(entry.control); word(entry.alt);}
    for (unsigned profile = 0; profile < 256; ++profile) for (unsigned scan = 0; scan < 256; ++scan) {
        memory.fill(0);
        for (unsigned at = 0; at < 152; ++at) memory[0x400 + at] = static_cast<uint8_t>((at * 17 + profile * 11) ^ 0x5a);
        memory[BIOS_KEYBOARD_FLAGS1] = static_cast<uint8_t>(profile);
        constexpr std::array<uint8_t, 8> flags2{0, 1, 2, 3, 8, 0x80, 0x60, 0xff};
        memory[BIOS_KEYBOARD_FLAGS2] = flags2[profile % flags2.size()];
        memory[BIOS_KEYBOARD_FLAGS3] = static_cast<uint8_t>(0x10 | ((profile >> 2) & 15));
        memory[BIOS_KEYBOARD_LEDS] = static_cast<uint8_t>(profile % 8);
        memory[BIOS_KEYBOARD_TOKEN] = static_cast<uint8_t>(profile * 29);
        mem_writew(BIOS_KEYBOARD_BUFFER_START, 0x1e); mem_writew(BIOS_KEYBOARD_BUFFER_END, 0x3e);
        constexpr std::array<uint16_t, 8> heads{0x1e, 0x1e, 0x20, 0x3c, 0x1e, 0x28, 0x3c, 0x3c};
        constexpr std::array<uint16_t, 8> tails{0x1e, 0x3c, 0x3c, 0x3a, 0x28, 0x1e, 0x3c, 0x1e};
        mem_writew(BIOS_KEYBOARD_BUFFER_HEAD, heads[profile % heads.size()]);
        mem_writew(BIOS_KEYBOARD_BUFFER_TAIL, tails[profile % tails.size()]);
        const auto initial = memory;
        ports.clear(); reg_al = static_cast<uint8_t>(scan); reg_ip = 0x1234;
        uint8_t action = 0;
        try {IRQ1_Handler();} catch (const PauseHandoff&) {action = 1;}
        if (ports.size() > 1 || reg_ip != 0x1234) throw std::runtime_error("Unexpected BIOS callback continuation");
        word(static_cast<uint16_t>(profile)); byte(static_cast<uint8_t>(scan)); byte(action);
        byte(static_cast<uint8_t>(ports.size()));
        std::fwrite(initial.data() + 0x400, 1, 152, stdout);
        std::fwrite(memory.data() + 0x400, 1, 152, stdout);
        for (const auto& [port, value] : ports) {word(port); byte(value);}
    }
    return std::ferror(stdout) ? 1 : 0;
}
