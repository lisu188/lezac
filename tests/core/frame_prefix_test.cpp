#include "core/frame_prefix.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
std::vector<uint8_t> readFile(const char* path) {
    std::ifstream input(path, std::ios::binary); require(input.good(), "Cannot read prefix corpus input");
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
struct Write { uint32_t address; uint8_t size; uint16_t value; bool operator==(const Write&) const = default; };
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t s, uint16_t o) { return (uint32_t{s} * 16 + o) & 0xfffffu; }
    uint16_t word(uint16_t s, uint16_t o) const {
        const auto at = address(s, o);
        return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[(at + 1u) & 0xfffffu]} << 8));
    }
    void word(uint16_t s, uint16_t o, uint16_t value) {
        const auto at = address(s, o); bytes[at] = static_cast<uint8_t>(value);
        bytes[(at + 1u) & 0xfffffu] = static_cast<uint8_t>(value >> 8); writes.push_back({at, 2, value});
    }
    TimerIrqBus bus() {
        return {
            [this](uint16_t s, uint16_t o) { return bytes[address(s, o)]; },
            [this](uint16_t s, uint16_t o) { return word(s, o); },
            [this](uint16_t s, uint16_t o) { return uint32_t{word(s, o)} | (uint32_t{word(s, static_cast<uint16_t>(o + 2u))} << 16); },
            [this](uint16_t s, uint16_t o, uint8_t v) { const auto at = address(s, o); bytes[at] = v; writes.push_back({at, 1, v}); },
            [this](uint16_t s, uint16_t o, uint16_t v) { word(s, o, v); },
            [this](uint16_t s, uint16_t o, uint32_t v) { word(s, o, static_cast<uint16_t>(v)); word(s, static_cast<uint16_t>(o + 2u), static_cast<uint16_t>(v >> 16)); },
            [](uint16_t p) -> uint8_t { require(p == 0x61, "Unexpected prefix IRQ input"); return 0; },
            [](uint16_t p, uint8_t) { require(p == 0x20 || p == 0x61, "Unexpected prefix IRQ output"); }
        };
    }
};
struct Reader {
    std::vector<uint8_t> bytes; size_t at = 0;
    uint32_t number(unsigned n) {
        require(n <= 4 && at + n <= bytes.size(), "Truncated prefix corpus");
        uint32_t result = 0; for (unsigned i = 0; i < n; ++i) result |= uint32_t{bytes[at++]} << (i * 8);
        return result;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value = static_cast<uint16_t>(number(2));
        r.flags = number(4); return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t count) {
        std::vector<DosGetTimeRegisters> result(count);
        for (auto member : {&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
                &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
                &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
                &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip})
            for (auto& r : result) r.*member = static_cast<uint16_t>(number(2));
        for (auto& r : result) r.flags = number(4);
        return result;
    }
};
Memory loadImage(const char* path) {
    const auto exe = readFile(path);
    const auto word = [&](size_t at) { require(at + 2 <= exe.size(), "Truncated MZ image"); return uint32_t{exe[at]} | (uint32_t{exe[at + 1]} << 8); };
    require(word(0) == 0x5a4d && word(6) == 468 && word(8) * 16 == 0x770, "Original MZ layout differs");
    Memory memory;
    require(exe.size() > 0x770 && exe.size() - 0x770 <= memory.bytes.size() - 0x10000, "Original image exceeds memory");
    std::copy(exe.begin() + 0x770, exe.end(), memory.bytes.begin() + 0x10000);
    for (uint32_t i = 0; i < 468; ++i) {
        const auto e = word(24) + i * 4, at = 0x10000 + word(e + 2) * 16 + word(e);
        require(at + 2 <= memory.bytes.size(), "Original relocation exceeds memory");
        const auto value = static_cast<uint16_t>((memory.bytes[at] | (uint16_t{memory.bytes[at + 1]} << 8)) + 0x1000);
        memory.bytes[at] = static_cast<uint8_t>(value); memory.bytes[at + 1] = static_cast<uint8_t>(value >> 8);
    }
    return memory;
}
void compare(DosGetTimeRegisters actual, DosGetTimeRegisters expected, uint32_t index, size_t cursor) {
    const bool control = ((actual.flags ^ expected.flags) & ~uint32_t{0x8d5}) == 0;
    actual.flags = expected.flags;
    if (!control || actual != expected) {
        std::cerr << "case=" << index << " observation=" << cursor << " actual=" << std::hex << actual.cs << ':' << actual.ip
                  << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
                  << " di=" << actual.di << '/' << expected.di << std::dec << '\n';
        throw std::runtime_error("Prefix register/control-flag trace differs");
    }
}
void irqCheck(FramePrefixOperation operation, Memory memory, const std::vector<uint8_t>& expected,
              DosGetTimeRegisters endpoint, uint16_t cs, uint16_t ip, uint16_t ds) {
    memory.word(0, 0x70, 0x0fbe); memory.word(0, 0x72, 0x1000);
    memory.word(0x40, 0x6c, 100); memory.word(0x40, 0x6e, 0);
    memory.bytes[Memory::address(0x40, 0x40)] = 2; memory.bytes[Memory::address(0x40, 0x3f)] = 0xa5;
    const auto bus = memory.bus(); const auto copies = [](uint16_t n) { return n; };
    unsigned steps = 0;
    while (!operation.finished() && !(operation.registers().cs == cs &&
            operation.registers().ip == ip && operation.registers().ds == ds)) {
        require(steps++ < 100000, "Prefix IRQ boundary was not reached"); operation.advance(1, bus, copies);
    }
    require(!operation.finished(), "Prefix IRQ boundary missing");
    operation.deliverTimerInterrupt(bus); require(operation.interruptInProgress(), "Prefix IRQ was not admitted");
    while (!operation.finished()) {
        require(steps++ < 200000, "Prefix IRQ did not finish"); operation.advance(17, bus, copies);
        operation = FramePrefixOperation(operation.snapshot());
    }
    require(operation.snapshot().outcome == FramePrefixOutcome::ActorUpdate && operation.registers() == endpoint, "Prefix IRQ changed endpoint registers");
    require(operation.snapshot().timerInstructions == 36 && operation.snapshot().timerDeliveries == 1 &&
        memory.word(0x40, 0x6c) == 101, "Prefix IRQ context/counters differ");
    require(std::equal(memory.bytes.begin() + 0xa0000, memory.bytes.begin() + 0xb0001, expected.begin() + 0xa0000),
        "Prefix IRQ changed original VGA endpoint");
    bool rejected = false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
    require(rejected, "Finished prefix operation admitted an IRQ");
}
void replay(const char* path, const char* exe, const char* pixels) {
    Reader reader{readFile(path)};
    for (char c : std::string("LZPRFX01")) require(reader.number(1) == static_cast<uint8_t>(c), "Prefix corpus magic differs");
    const auto count = reader.number(4); require(count == 238, "Prefix corpus domain differs");
    const auto image = loadImage(exe);
    uint64_t replays = 0, comparisons = 0, dispatches = 0, transfers = 0;
    unsigned handoffs = 0, errors = 0, irqCases = 0;
    constexpr std::array<std::array<uint16_t, 3>, 8> irqTargets{{
        {{0x1000, 0x7a57, 0x1aa2}}, {{0x1920, 0x13a8, 0x1aa2}},
        {{0x1000, 0x06ab, 0x1aa2}}, {{0x1000, 0x7c3d, 0x1aa2}},
        {{0x1000, 0x056b, 0x1aa2}}, {{0x1000, 0x116a, 0x1aa2}},
        {{0x1000, 0x1344, 0x5000}}, {{0x1000, 0x07ec, 0x1aa2}}
    }};
    std::array<bool, irqTargets.size()> irqSeen{};
    std::ofstream dump;
    if (pixels) {
        require(!std::filesystem::exists(pixels) && !std::filesystem::is_symlink(pixels), "Existing prefix pixel output preserved");
        dump.open(pixels, std::ios::binary); require(dump.good(), "Cannot open prefix pixel output"); dump.write("LZPFPX01", 8);
    }
    for (uint32_t index = 0; index < count; ++index) {
        require(reader.number(4) == index, "Prefix case index differs"); const auto outcome = reader.number(4);
        require(outcome <= 2, "Prefix outcome differs"); handoffs += outcome == 1; errors += outcome == 2;
        const auto entry = reader.registers(), endpoint = reader.registers(); auto initial = image;
        const auto seeds = reader.number(4); require(seeds < 500, "Prefix seed reserve differs");
        for (uint32_t i = 0; i < seeds; ++i) {
            const auto at = reader.number(4), length = reader.number(4);
            require(length <= 65536 && uint64_t{at} + length <= initial.bytes.size() && reader.at + length <= reader.bytes.size(), "Prefix seed exceeds memory");
            std::copy_n(reader.bytes.begin() + static_cast<std::ptrdiff_t>(reader.at), length, initial.bytes.begin() + at); reader.at += length;
        }
        const auto states = reader.number(4); require(states > 1 && states < 2000000, "Prefix trace reserve differs");
        const auto trace = reader.trace(states); const auto writeCount = reader.number(4);
        require(writeCount < 200000, "Prefix write reserve differs");
        auto expected = initial.bytes; std::vector<Write> writes;
        for (uint32_t i = 0; i < writeCount; ++i) {
            const auto at = reader.number(4), size = reader.number(1), value = reader.number(2);
            require((size == 1 || size == 2) && uint64_t{at} + size <= expected.size(), "Prefix write exceeds memory");
            writes.push_back({at, static_cast<uint8_t>(size), static_cast<uint16_t>(value)});
            expected[at] = static_cast<uint8_t>(value); if (size == 2) expected[at + 1] = static_cast<uint8_t>(value >> 8);
        }
        for (uint16_t limit : {uint16_t{1}, uint16_t{2}, uint16_t{65535}}) for (uint64_t budget : {1u, 2u, 17u, 4096u}) {
            auto memory = initial; const auto bus = memory.bus(); FramePrefixOperation operation(entry, 0x1000, 0x200000);
            const auto copies = [=](uint16_t n) { return std::min(n, limit); }; const auto zero = operation.snapshot();
            require(operation.advance(0, bus, copies) == 0 && operation.snapshot() == zero && memory.writes.empty(), "Zero prefix grant changed state");
            size_t cursor = 0; uint64_t consumed = 0;
            compare(operation.registers(), trace[0], index, cursor); ++comparisons;
            while (!operation.finished()) {
                const auto used = operation.advance(budget, bus, copies); require(used > 0 && used <= budget, "Prefix instruction grant differs");
                consumed += used;
                require(operation.snapshot().dispatchedInstructions == consumed, "Prefix dispatch accounting differs");
                for (uint64_t step = 0; step < used; ++step) {
                    require(cursor + 1 < trace.size(), "Prefix exceeded original endpoint"); const auto before = trace[cursor];
                    if (before.cs == 0x1000 && (before.ip == 0x116a || before.ip == 0x7ec) && before.cx) {
                        transfers += std::min(before.cx, limit); cursor += std::min(before.cx, limit); require(cursor < trace.size(), "Truncated prefix REP observations");
                        if (trace[cursor].ip == before.ip && trace[cursor].cx == 0) ++cursor;
                    } else ++cursor;
                }
                require(cursor < trace.size(), "Prefix trace exhausted"); compare(operation.registers(), trace[cursor], index, cursor);
                ++comparisons; operation = FramePrefixOperation(operation.snapshot());
            }
            const auto final = operation.snapshot();
            require(cursor + 1 == trace.size() && operation.registers() == endpoint, "Prefix endpoint registers/all flags differ");
            require(final.outcome == (outcome == 0 ? FramePrefixOutcome::ActorUpdate : outcome == 1 ? FramePrefixOutcome::EndRunUi : FramePrefixOutcome::RuntimeError), "Prefix endpoint outcome differs");
            require(memory.writes == writes, "Prefix ordered original writes differ");
            require(memory.bytes == expected, "Prefix complete 1 MiB post-state differs");
            require(operation.advance(100, bus, copies) == 0 && operation.snapshot() == final, "Finished prefix operation changed state");
            if (dump.is_open() && limit == 65535 && budget == 4096 && (index == 128 || index == 160 || index == 165 || index == 204)) {
                for (unsigned byte = 0; byte < 4; ++byte) dump.put(static_cast<char>(index >> (byte * 8)));
                dump.write(reinterpret_cast<const char*>(expected.data() + 0xa0000), 64000);
                dump.write(reinterpret_cast<const char*>(memory.bytes.data() + 0xa0000), 64000);
            }
            dispatches += final.dispatchedInstructions; ++replays;
        }
        for (size_t target = 0; target < irqTargets.size(); ++target) if (!outcome && !irqSeen[target]) {
            const auto [cs, ip, ds] = irqTargets[target];
            if (std::any_of(trace.begin(), trace.end(), [&](const auto& r) { return r.cs == cs && r.ip == ip && r.ds == ds; })) {
                irqCheck(FramePrefixOperation(entry, 0x1000, 0x200000), initial, expected, endpoint, cs, ip, ds);
                irqSeen[target] = true; ++irqCases;
            }
        }
    }
    require(reader.at == reader.bytes.size() && handoffs == 2 && errors == 8 && irqCases == 8, "Prefix corpus tail differs");
    if (dump.is_open()) { dump.flush(); require(dump.good(), "Prefix pixel output failed"); }
    std::cout << "frame_prefix_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
              << " dispatches=" << dispatches << " transfers=" << transfers << " end_run_handoffs=" << handoffs
              << " runtime_errors=" << errors << " computed_irq_cases=" << irqCases
              << " active_prefix_executed=0 end_run_ui=0 full_frame_claim=0 work_clock_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r; r.cs = 0x1000; r.ds = 0x1aa2; r.ss = 0x7000; r.sp = 0x3fe4; r.bp = 0x3ffe; r.ip = 0x7a57;
    unsigned rejected = 0;
    for (unsigned field = 0; field < 4; ++field) {
        auto bad = r; if (field == 0) bad.cs = 0; else if (field == 1) bad.ds = 0; else if (field == 2) bad.ip = 0;
        try { FramePrefixOperation operation(bad, 0x1000, field == 3 ? 1 : 0); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    auto bad = FramePrefixOperation(r, 0x1000, 0).snapshot(); bad.spawnerTimer = TimerIrqSnapshot{}; auto w = r; w.ip = 0x7c3d;
    bad.callee = FrameWaitingOperation(w, 0x1000, 0).snapshot();
    try { FramePrefixOperation operation(bad); } catch (const std::invalid_argument&) { ++rejected; }
    require(rejected == 5, "Prefix operation accepted invalid ownership");
    Memory memory; const auto bus = memory.bus(); const auto copies = [](uint16_t n) { return n; };
    r.ip = 0x7903;
    auto active = FramePrefixOperation(r, 0x140, 0x160, 0x900, 0x1000, 0).snapshot();
    auto renderRegisters = r; renderRegisters.ip = 0x7a13;
    auto render = FrameRenderOperation(renderRegisters, 0x1000).snapshot();
    render.registers.ip = 0x7a3a; render.registers.flags |= 0x40;
    std::get<FrameActiveSnapshot>(active.callee).render = render;
    FramePrefixOperation first(active);
    require(first.advance(1, bus, copies) == 1 && std::holds_alternative<FrameSpawnerSnapshot>(first.snapshot().callee) &&
        first.registers().ip == 0x7a57 && memory.writes.empty(), "Active-to-spawner handoff changed original boundary");
    auto spawner = first.snapshot(); std::get<FrameSpawnerSnapshot>(spawner.callee).registers.ip = 0x7a72;
    FramePrefixOperation second(spawner);
    require(second.advance(1, bus, copies) == 1 && std::holds_alternative<FrameWaitingSnapshot>(second.snapshot().callee) &&
        second.registers().ip == 0x7c3d && memory.writes.empty(), "Spawner-to-waiting handoff changed original boundary");
    auto waiting = second.snapshot(); auto& child = std::get<FrameWaitingSnapshot>(waiting.callee);
    child.registers.ip = 0x7eb6; child.registers.flags |= 0x40;
    FramePrefixOperation third(waiting);
    require(third.advance(1, bus, copies) == 1 && third.finished() && third.snapshot().outcome == FramePrefixOutcome::ActorUpdate &&
        third.registers().ip == 0x7ebb && memory.writes.empty(), "Actor handoff executed unrecovered work");
    const auto finished = third.snapshot();
    require(third.advance(100, bus, copies) == 0 && third.snapshot() == finished, "Finished prefix dispatched work");
    std::cout << "frame_prefix_unit=ok entry_rejections=5 stage_handoffs=3\n";
}
}
int main(int argc, char** argv) {
    try {
        if (argc == 1) unit();
        else if (argc == 3 || argc == 4) replay(argv[1], argv[2], argc == 4 ? argv[3] : nullptr);
        else throw std::runtime_error("Expected prefix corpus and original EXE");
        return 0;
    } catch (const std::exception& error) { std::cerr << "frame_prefix=failed " << error.what() << '\n'; return 1; }
}
