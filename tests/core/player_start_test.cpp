#include "core/player_start.hpp"
#include "gameplay/player_start.hpp"

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
void require(bool yes, const char* message) { if (!yes) throw std::runtime_error(message); }
struct Write {
    uint32_t address;
    uint8_t size;
    uint16_t value;
    bool operator==(const Write&) const = default;
};
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at = 0;
    uint32_t number(unsigned count) {
        require(at + count <= bytes.size(), "Truncated player start fixture");
        uint32_t value = 0;
        for (unsigned i = 0; i < count; ++i) value |= uint32_t{bytes[at++]} << (8 * i);
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
std::vector<uint8_t> read(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "Cannot read player start input");
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t segment, uint16_t offset) { return (uint32_t{segment} * 16 + offset) & 0xfffffu; }
    uint16_t word(uint32_t at) const { return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[(at+1u)&0xfffffu]} << 8)); }
    void store(uint32_t at, uint16_t value, uint8_t size = 2) {
        bytes[at] = static_cast<uint8_t>(value);
        if (size == 2) bytes[(at+1u)&0xfffffu] = static_cast<uint8_t>(value >> 8);
    }
    TimerIrqBus bus() {
        TimerIrqBus result;
        result.readByte = [this](uint16_t s, uint16_t o) { return bytes[address(s,o)]; };
        result.readWord = [this](uint16_t s, uint16_t o) { return word(address(s,o)); };
        result.writeByte = [this](uint16_t s, uint16_t o, uint8_t v) { const auto a=address(s,o);store(a,v,1);writes.push_back({a,1,v}); };
        result.writeWord = [this](uint16_t s, uint16_t o, uint16_t v) { const auto a=address(s,o);store(a,v);writes.push_back({a,2,v}); };
        return result;
    }
};
struct Case {
    std::array<uint16_t,6> profile{};
    std::vector<lezac::resources::LevelPortal> portals;
    DosGetTimeRegisters initial, final;
    std::vector<DosGetTimeRegisters> trace;
    std::vector<Write> writes;
};
Memory initialMemory(const Case& sample, const std::vector<uint8_t>& image) {
    Memory memory;
    std::copy(image.begin(), image.end(), memory.bytes.begin()+0x10000);
    const auto& p = sample.profile;
    const auto stack = 0x70000u + p[4] - 96u;
    for (unsigned i=0;i<112;++i) memory.bytes[stack+i]=static_cast<uint8_t>(i*29+p[0]*7+11);
    const auto actor = 0x1b88u + (p[1]-1u)*38u, visual = 0xc21eu + (p[1]-1u)*8u;
    for (unsigned i=0;i<38;++i) memory.bytes[0x1aa20+actor+i]=static_cast<uint8_t>(i*11+p[0]*7+19);
    memory.bytes[0x1aa20+actor+1]=static_cast<uint8_t>(p[1]-1);
    for (unsigned i=0;i<8;++i) memory.bytes[0x1aa20+visual+i]=static_cast<uint8_t>(i*13+p[0]*3+7);
    memory.bytes[0x1aa20+0x79a5]=static_cast<uint8_t>(p[2]);
    memory.store(0x1aa20+0x1afa,p[3]);
    for (size_t i=0;i<sample.portals.size();++i) {
        const auto& portal=sample.portals[i];const auto at=static_cast<uint32_t>(0x1aa20 + 0x771e + i*7);
        memory.store(at,portal.key);memory.store(at+2,portal.x);memory.store(at+4,portal.y);
        memory.store(at+6,portal.marker,1);
    }
    const auto at=0x70000u+p[4];
    memory.store(at,0x7d23);memory.store(at+2,static_cast<uint16_t>(0x7b00|p[1]));
    memory.store(at+4,static_cast<uint16_t>(actor));memory.store(at+6,0x1aa2);
    return memory;
}
std::vector<uint8_t> relocated(const std::filesystem::path& root) {
    Reader exe{read(root / "LEZAC.EXE")};
    require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Original MZ header differs");
    exe.at=6;const auto count=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto relocations=exe.number(2);
    require(header<exe.bytes.size() && relocations+count*4<=header,"Original MZ layout differs");
    std::vector<uint8_t> image(exe.bytes.begin()+header,exe.bytes.end());
    exe.at=relocations;
    for (uint32_t i=0;i<count;++i) {
        const auto offset=exe.number(2),segment=exe.number(2);const auto at=segment*16+offset;
        require(at+1<image.size(),"Original relocation is out of range");
        const auto value=static_cast<uint16_t>(image[at]+(uint16_t{image[at+1]}<<8)+0x1000);
        image[at]=static_cast<uint8_t>(value);image[at+1]=static_cast<uint8_t>(value>>8);
    }
    require(image.size()+0x10000<=1048576,"Original image exceeds memory");
    return image;
}
void compareTrace(DosGetTimeRegisters actual, DosGetTimeRegisters expected) {
    require(((actual.flags^expected.flags)&~uint32_t{0x8d5})==0,"Start trace control flags differ");
    actual.flags=expected.flags;
    require(actual==expected,"Start instruction register trace differs");
}
void replay(const char* path, const char* root) {
    Reader input{read(path)};const auto image=relocated(root);
    for (char c : std::string("LZSTART1")) require(input.number(1)==static_cast<uint8_t>(c),"Start fixture magic differs");
    const auto count=input.number(4);require(count==1043,"Start case count differs");
    uint64_t comparisons=0, totalWrites=0;unsigned errors=0;
    for (uint32_t index=0;index<count;++index) {
        Case sample;
        for (auto& value : sample.profile) value=static_cast<uint16_t>(input.number(2));
        const auto& p=sample.profile;
        require(p[0]==index && (p[1]==1 || p[1]==2) && p[2]<=3 && p[5]<=1,"Start case fields differ");
        for (unsigned i=0;i<p[2];++i) {
            lezac::resources::LevelPortal portal;
            portal.key=static_cast<uint16_t>(input.number(2));portal.x=static_cast<uint16_t>(input.number(2));
            portal.y=static_cast<uint16_t>(input.number(2));portal.marker=static_cast<uint8_t>(input.number(1));
            sample.portals.push_back(portal);
        }
        sample.initial=input.registers();sample.final=input.registers();
        const auto states=input.number(4);require(states>1 && states<1000,"Start trace size differs");
        for (uint32_t i=0;i<states;++i) sample.trace.push_back(input.registers());
        const auto writes=input.number(4);require(writes<100,"Start write count differs");
        for (uint32_t i=0;i<writes;++i) {
            const auto address=input.number(4);const auto size=static_cast<uint8_t>(input.number(1));
            const auto value=static_cast<uint16_t>(input.number(2));
            require(address+size<=1048576 && (size==1 || size==2),"Start write fields differ");
            sample.writes.push_back({address,size,value});
        }
        auto expected=initialMemory(sample,image);
        for (const auto& write : sample.writes) expected.store(write.address,write.value,write.size);
        if (!p[5]) {
            const auto [x,y]=lezac::gameplay::playerStart(sample.portals,static_cast<uint8_t>(p[1]));
            const auto at=0x1aa20u + 0xc21e + (p[1]-1u)*8;
            require(expected.word(at)==x && expected.word(at+2)==y,"Live start locator differs from original");
        }
        errors+=p[5];totalWrites+=sample.writes.size();
        for (uint64_t budget : {1u,2u,17u,4096u}) {
            auto memory=initialMemory(sample,image);const auto bus=memory.bus();
            PlayerStartOperation operation(sample.initial,0x1000);const auto before=operation.snapshot();
            require(operation.advance(0,bus)==0 && operation.snapshot()==before && memory.writes.empty(),"Start zero budget mutated state");
            size_t cursor=0;compareTrace(operation.snapshot().registers,sample.trace[0]);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus);
                require(used>0 && used<=budget,"Start dispatch budget differs");
                cursor+=static_cast<size_t>(used);require(cursor<sample.trace.size(),"Start ran beyond original endpoint");
                compareTrace(operation.snapshot().registers,sample.trace[cursor]);++comparisons;
                operation=PlayerStartOperation(operation.snapshot());
            }
            const auto final=operation.snapshot();
            require(cursor+1==sample.trace.size() && final.dispatchedInstructions==cursor,"Start dispatch count differs");
            require(final.registers==sample.final,"Start endpoint registers or flags differ");
            require(final.outcome==(p[5]?PlayerStartOutcome::RuntimeError:PlayerStartOutcome::Returned),"Start outcome differs");
            require(memory.writes==sample.writes && memory.bytes==expected.bytes,"Start ordered writes or complete memory differ");
            require(operation.advance(100,bus)==0 && operation.snapshot()==final,"Completed start operation changed");
        }
    }
    require(input.at==input.bytes.size() && errors==3 && totalWrites==14053,"Start corpus tail differs");
    std::cout << "player_start_cpu=ok cases=" << count << " replays=" << count*4 << " comparisons=" << comparisons
        << " writes=" << totalWrites << " runtime_errors=3 whole_game_parity=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ip=0x56b;
    unsigned rejected=0;
    for (unsigned field=0;field<3;++field) {
        auto bad=r;if (field==0) bad.cs=0;else if (field==1) bad.ds=0;else bad.ip=0;
        try { PlayerStartOperation operation(bad,0x1000); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    require(rejected==3,"Start accepted an invalid entry");
    require(lezac::gameplay::playerStart({},1)==std::pair<uint16_t,uint16_t>{uint16_t{17},uint16_t{17}},"Start fallback differs");
    std::cout << "player_start_unit=ok entry_rejections=3\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();else if (argc==3) replay(argv[1],argv[2]);else throw std::runtime_error("Expected fixture and original root");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "player_start=failed " << error.what() << '\n';return 1;
    }
}
