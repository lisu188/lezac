#include <array>
#include <bit>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <utility>
#include <vector>

using Bit8u = uint8_t;
using Bitu = uint64_t;
constexpr unsigned MCH_PCJR = 0;
unsigned machine = 5;
bool a20 = false;
std::vector<std::pair<uint8_t, uint32_t>> effects;
struct DiscardLog {
    template<class... Args> void operator()(const char*, Args...) const {}
};
#define LOG(...) DiscardLog{}
[[noreturn]] void E_Exit(const char*) {throw std::runtime_error("Unsupported original key");}

// ORIGINAL_ENUM

static void KEYBOARD_TransferBuffer(Bitu);
void PIC_ActivateIRQ(Bitu irq) {effects.emplace_back(3, static_cast<uint32_t>(irq));}
void PIC_AddEvent(void(*handler)(Bitu), float delay, Bitu value = 0) {
    if (handler != KEYBOARD_TransferBuffer || value) throw std::runtime_error("Unknown original event");
    effects.emplace_back(1, std::bit_cast<uint32_t>(delay));
}
void PIC_RemoveEvents(void(*handler)(Bitu)) {
    if (handler != KEYBOARD_TransferBuffer) throw std::runtime_error("Unknown original removal");
    effects.emplace_back(2, 0);
}
bool MEM_A20_Enabled() {return a20;}
void MEM_A20_Enable(bool value) {a20 = value; effects.emplace_back(4, value);}
void TIMER_SetGate2(bool value) {effects.emplace_back(5, value);}
void PCSPEAKER_SetType(Bitu value) {effects.emplace_back(6, static_cast<uint32_t>(value));}

// ORIGINAL_FUNCTIONS

void byte(uint8_t value) {std::putchar(value);}
void word(uint16_t value) {byte(static_cast<uint8_t>(value)); byte(static_cast<uint8_t>(value >> 8));}
void dword(uint32_t value) {word(static_cast<uint16_t>(value)); word(static_cast<uint16_t>(value >> 16));}
void qword(uint64_t value) {dword(static_cast<uint32_t>(value)); dword(static_cast<uint32_t>(value >> 32));}
void state() {
    std::fwrite(keyb.buffer, 1, 32, stdout);
    for (uint64_t value : {keyb.used, keyb.pos, uint64_t(keyb.repeat.key), keyb.repeat.wait,
            keyb.repeat.pause, keyb.repeat.rate, uint64_t(keyb.command), uint64_t(keyb.p60data),
            uint64_t(keyb.p60changed), uint64_t(keyb.active), uint64_t(keyb.scanning),
            uint64_t(keyb.scheduled), uint64_t(port_61_data)}) qword(value);
    byte(a20);
}
void initialize(unsigned profile) {
    keyb = {};
    for (unsigned i = 0; i < 32; ++i) keyb.buffer[i] = static_cast<uint8_t>(i * 17 + profile * 11);
    constexpr std::array<unsigned, 4> used{0, 1, 31, 32}, waits{0, 1, 2, 1000};
    constexpr std::array<KBD_KEYS, 6> keys{KBD_z, KBD_up, KBD_rightalt, KBD_printscreen, KBD_pause, KBD_NONE};
    constexpr std::array<unsigned, 32> rates{33,37,42,46,50,54,58,63,67,75,83,92,100,109,118,125,
        133,149,167,182,200,217,233,250,270,303,333,370,400,435,476,500};
    keyb.used = used[profile % 4]; keyb.pos = (profile * 7) % 32;
    keyb.repeat.key = keys[profile % keys.size()]; keyb.repeat.wait = waits[(profile / 4) % 4];
    if (keyb.repeat.wait && keyb.repeat.key == KBD_NONE) keyb.repeat.key = KBD_z;
    keyb.repeat.pause = 250 * (1 + profile % 4); keyb.repeat.rate = rates[profile];
    keyb.command = static_cast<KeyCommands>(profile / 8);
    keyb.p60data = static_cast<uint8_t>(profile * 13);
    keyb.p60changed = profile & 1; keyb.active = profile & 2; keyb.scanning = profile & 4;
    keyb.scheduled = profile & 8; port_61_data = static_cast<uint8_t>(profile * 37);
    a20 = profile & 16;
    effects.clear();
}
void run(unsigned profile, uint8_t action, uint16_t argument = 0, bool pressed = false) {
    initialize(profile);
    byte(action); word(argument); byte(pressed); state();
    Bitu result = 0;
    switch (action) {
    case 1: KEYBOARD_AddKey(static_cast<KBD_KEYS>(argument), pressed); break;
    case 2: write_p60(0x60, argument, 1); break;
    case 3: result = read_p60(0x60, 1); break;
    case 4: write_p61(0x61, argument, 1); break;
    case 5: result = read_p61(0x61, 1); break;
    case 6: write_p64(0x64, argument, 1); break;
    case 7: result = read_p64(0x64, 1); break;
    case 8: KEYBOARD_TransferBuffer(0); break;
    case 9: KEYBOARD_ClrBuffer(); break;
    case 10: KEYBOARD_TickHandler(); break;
    default: throw std::runtime_error("Unknown oracle action");
    }
    state(); word(static_cast<uint16_t>(result)); byte(static_cast<uint8_t>(effects.size()));
    for (const auto& [kind, value] : effects) {byte(kind); dword(value);}
}
int main() {
    static_assert(KBD_LAST == 103);
    std::fwrite("LZKDEV01", 1, 8, stdout); dword(31296);
    for (unsigned profile = 0; profile < 32; ++profile) {
        for (uint16_t key = 1; key < KBD_LAST; ++key) for (bool pressed : {false, true}) run(profile, 1, key, pressed);
        for (uint8_t action : {uint8_t{2}, uint8_t{4}, uint8_t{6}})
            for (uint16_t argument = 0; argument < 256; ++argument) run(profile, action, argument);
        for (uint8_t action : {uint8_t{3}, uint8_t{5}, uint8_t{7}, uint8_t{8}, uint8_t{9}, uint8_t{10}}) run(profile, action);
    }
    return std::ferror(stdout) ? 1 : 0;
}
