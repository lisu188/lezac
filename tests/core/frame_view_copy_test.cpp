#include "core/frame_view_copy.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac::core;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576);
    bool wrapWord = false;
    uint32_t address(uint16_t segment, uint16_t offset) const {
        return (uint32_t{segment} * 16u + offset) & 0xfffffu;
    }
    uint16_t read(uint16_t segment, uint16_t offset) const {
        const auto at = address(segment, offset);
        const auto next = wrapWord ? address(segment, static_cast<uint16_t>(offset + 1u)) : (at + 1u) & 0xfffffu;
        return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[next]} << 8));
    }
    void write(uint16_t segment, uint16_t offset, uint16_t value) {
        const auto at = address(segment, offset);
        const auto next = wrapWord ? address(segment, static_cast<uint16_t>(offset + 1u)) : (at + 1u) & 0xfffffu;
        bytes[at] = static_cast<uint8_t>(value); bytes[next] = static_cast<uint8_t>(value >> 8);
    }
    TimerIrqBus bus() {
        TimerIrqBus result;
        result.readWord = [this](uint16_t s, uint16_t o) { return read(s, o); };
        result.writeWord = [this](uint16_t s, uint16_t o, uint16_t value) { write(s, o, value); };
        result.inByte = [](uint16_t) -> uint8_t { throw std::runtime_error("Unexpected I/O"); };
        result.outByte = [](uint16_t, uint8_t) { throw std::runtime_error("Unexpected I/O"); };
        return result;
    }
};
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at = 0;
    uint32_t number(unsigned count) {
        require(at + count <= bytes.size(), "Truncated corpus");
        uint32_t value = 0;
        for (unsigned i = 0; i < count; ++i) value |= uint32_t{bytes[at++]} << (i * 8);
        return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value = static_cast<uint16_t>(number(2));
        r.flags = number(4);
        return r;
    }
};
struct Case {
    std::array<uint16_t,9> profile{};
    DosGetTimeRegisters initial, final;
    uint32_t words = 0;
    std::array<uint8_t,6> stack{};
    std::vector<uint8_t> vga;
};
Memory initialMemory(const Case& sample) {
    Memory memory;
    const auto& p = sample.profile;
    for (uint32_t i = 0; i < 65538; ++i) {
        memory.bytes[0x50000 + i] = static_cast<uint8_t>(i * 17 + (i >> 6) * 3 + (i >> 16) * 97 + p[0] + 1);
        memory.bytes[0xa0000 + i] = static_cast<uint8_t>(i * 37 + (i >> 8) * 11 + (i >> 16) * 109 + (p[0] + 1) * 13);
    }
    struct Word { uint16_t offset, value; };
    for (const auto& [offset,value] : std::array<Word,8>{{
        {0xc1ec,p[1]},{0xc1ee,p[2]},{0xc20a,p[3]},{0xc20c,p[4]},
        {0xc214,p[5]},{0xc1f4,p[6]},{0xc206,static_cast<uint16_t>(320-p[1])},{0xc212,0x5000}}})
        memory.write(0x1aa2,offset,value);
    memory.write(0x7000,0x3fe4,p[8]); memory.write(0x7000,0x3fe6,0x1000);
    return memory;
}
bool matches(const Memory& memory, const Case& sample, const FrameViewCopySnapshot& state) {
    return state.returned && state.registers == sample.final && state.transferredWords == sample.words &&
        std::equal(sample.stack.begin(),sample.stack.end(),memory.bytes.begin()+0x73fe2) &&
        std::equal(sample.vga.begin(),sample.vga.end(),memory.bytes.begin()+0xa0000);
}
void replay(const char* path) {
    std::ifstream file(path,std::ios::binary);
    require(file.good(),"Cannot read corpus");
    Reader reader{{std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()}};
    for (const char c : std::string("LZVCOPY1")) require(reader.number(1) == static_cast<uint8_t>(c),"Corpus magic differs");
    const auto cases = reader.number(4); require(cases == 12,"Corpus case count differs");
    uint32_t replays = 0, wrapFaults = 0;
    for (uint32_t index = 0; index < cases; ++index) {
        Case sample;
        for (auto& value : sample.profile) value = static_cast<uint16_t>(reader.number(2));
        require(sample.profile[0] == index,"Corpus index differs");
        sample.initial = reader.registers(); sample.final = reader.registers(); sample.words = reader.number(4);
        for (auto& value : sample.stack) value = static_cast<uint8_t>(reader.number(1));
        sample.vga.resize(65538);
        for (auto& value : sample.vga) value = static_cast<uint8_t>(reader.number(1));
        for (const uint16_t copyLimit : {uint16_t{1},uint16_t{7},uint16_t{65535}}) {
            for (const uint64_t budget : {1u,2u,17u,100000u}) {
                auto memory = initialMemory(sample); const auto before = memory.bytes;
                const auto bus = memory.bus();
                auto operation = FrameViewCopyOperation(sample.initial,0x1000);
                const auto copyBudget = [copyLimit](uint16_t count) { return std::min(count,copyLimit); };
                const auto empty = operation.snapshot();
                require(operation.advance(0,bus,copyBudget) == 0 && operation.snapshot() == empty,"Zero budget changed state");
                uint64_t total = 0;
                while (!operation.returned()) {
                    const auto used = operation.advance(budget,bus,copyBudget);
                    require(used && used <= budget,"Instruction budget differs");
                    total += used; require(total < 1000000,"Copy did not terminate");
                    operation = FrameViewCopyOperation(operation.snapshot());
                }
                const auto& p = sample.profile;
                const auto words = (p[1]-8u)/2u;
                const auto expected = 22u + (p[2]-8u)*(6u+(words+copyLimit-1u)/copyLimit);
                require(total == expected && operation.snapshot().dispatchedInstructions == total,"Dispatch count differs");
                require(matches(memory,sample,operation.snapshot()),"Original endpoint differs");
                for (size_t i = 0; i < before.size(); ++i)
                    if (!(i >= 0xa0000 && i < 0xb0002) && !(i >= 0x73fe2 && i < 0x73fe4))
                        require(memory.bytes[i] == before[i],"Copy changed unrelated memory");
                const auto final = operation.snapshot();
                require(operation.advance(100,bus,copyBudget) == 0 && operation.snapshot() == final,"Finished copy changed state");
                ++replays;
            }
        }
        auto wrong = initialMemory(sample); wrong.wrapWord = true;
        FrameViewCopyOperation fault(sample.initial,0x1000);
        fault.advance(100000,wrong.bus(),[](uint16_t count) { return count; });
        if (!matches(wrong,sample,fault.snapshot())) ++wrapFaults;
    }
    require(reader.at == reader.bytes.size(),"Trailing corpus bytes");
    require(wrapFaults >= 2,"Word-crossing controls are not observable");
    std::cout << "frame_view_copy_original=ok cases=" << cases << " replays=" << replays
        << " word_wrap_faults=" << wrapFaults << " full_frame_claim=0\n";
}
template<class F> void rejects(F action) {
    bool rejected = false;
    try { action(); } catch (const std::invalid_argument&) { rejected = true; }
    require(rejected,"Invalid operation accepted");
}
void unit() {
    DosGetTimeRegisters r; r.cs=0x18ac; r.ds=0x1aa2; r.ss=0x7000; r.sp=0x3fe4; r.ip=0x3c8;
    auto bad = r; bad.cs=0;
    rejects([&] { FrameViewCopyOperation operation(bad,0x1000); });
    bad=r; bad.ds=0; rejects([&] { FrameViewCopyOperation operation(bad,0x1000); });
    bad=r; bad.ip=0; rejects([&] { FrameViewCopyOperation operation(bad,0x1000); });
    FrameViewCopyOperation operation(r,0x1000);
    auto snapshot=operation.snapshot(); snapshot.registers.ip=0x408;
    rejects([&] { FrameViewCopyOperation resumed(snapshot); });
    snapshot=operation.snapshot(); snapshot.registers.cs=0;
    rejects([&] { FrameViewCopyOperation resumed(snapshot); });
    Case sample; sample.profile={0,320,9,0,0,8,1284,0x202,0x7a35}; sample.initial=r;
    auto memory=initialMemory(sample); const auto bus=memory.bus();
    while (operation.snapshot().registers.ip != 0x407)
        operation.advance(1,bus,[](uint16_t count) { return count; });
    const auto saved=operation.snapshot(); const auto before=memory.bytes;
    for (const auto invalid : {uint16_t{0},uint16_t{65535}}) {
        rejects([&] { operation.advance(1,bus,[invalid](uint16_t) { return invalid; }); });
        require(operation.snapshot() == saved && memory.bytes == before,"Rejected REP mutated state");
    }
    snapshot=saved; snapshot.registers.cx=0;
    FrameViewCopyOperation emptyCopy(snapshot);
    emptyCopy.advance(1,bus,[](uint16_t) -> uint16_t { throw std::runtime_error("Zero REP requested a grant"); });
    require(emptyCopy.snapshot().registers.ip == 0x409 && emptyCopy.snapshot().transferredWords == 0 &&
        memory.bytes == before,"Zero REP changed memory");
    std::cout << "frame_view_copy_unit=ok rejections=7\n";
}
}

int main(int argc, char** argv) {
    try {
        if (argc == 1) unit();
        else if (argc == 2) replay(argv[1]);
        else throw std::runtime_error("Expected optional original corpus path");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "frame_view_copy=failed " << error.what() << '\n'; return 1;
    }
}
