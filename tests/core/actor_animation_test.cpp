#include "core/actor_animation.hpp"
#include "gameplay/actor_models.hpp"

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
        require(at+count <= bytes.size(),"Truncated actor animation fixture");
        uint32_t value = 0;
        for (unsigned i=0;i<count;++i) value |= uint32_t{bytes[at++]} << (8*i);
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
    std::ifstream input(path,std::ios::binary);
    require(input.good(),"Cannot read actor animation input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t segment, uint16_t offset) { return (uint32_t{segment}*16+offset)&0xfffffu; }
    uint16_t word(uint32_t at) const { return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[(at+1u)&0xfffffu]}<<8)); }
    void store(uint32_t at, uint16_t value, uint8_t size = 2) {
        bytes[at] = static_cast<uint8_t>(value);
        if (size == 2) bytes[(at+1u)&0xfffffu] = static_cast<uint8_t>(value>>8);
    }
    TimerIrqBus bus() {
        TimerIrqBus result;
        result.readByte = [this](uint16_t s,uint16_t o) { return bytes[address(s,o)]; };
        result.readWord = [this](uint16_t s,uint16_t o) { return word(address(s,o)); };
        result.writeByte = [this](uint16_t s,uint16_t o,uint8_t v) { const auto a=address(s,o);store(a,v,1);writes.push_back({a,1,v}); };
        result.writeWord = [this](uint16_t s,uint16_t o,uint16_t v) { const auto a=address(s,o);store(a,v);writes.push_back({a,2,v}); };
        return result;
    }
};
struct Case {
    uint32_t index = 0;
    std::array<uint16_t,7> profile{};
    std::array<uint8_t,14> cursors{};
    DosGetTimeRegisters initial,final;
    std::vector<DosGetTimeRegisters> trace;
    std::vector<Write> writes;
};
Memory initialMemory(const Case& sample,const std::vector<uint8_t>& image) {
    Memory memory;
    std::copy(image.begin(),image.end(),memory.bytes.begin()+0x10000);
    const auto& p = sample.profile;
    const auto stack = 0x70000u+p[4]-128u;
    for (unsigned i=0;i<144;++i) memory.bytes[stack+i] = static_cast<uint8_t>(i*29+sample.index*7+11);
    memory.store(0x1aa20+0x1afa,p[3]);
    for (unsigned i=0;i<256;++i) {
        memory.store(0x1aa20+0xc324+i*4,static_cast<uint16_t>(i*197+sample.index*13+0x5a));
        memory.store(0x1aa20+0xc224+i*8,static_cast<uint16_t>(i*117+sample.index*23+0xa55a));
    }
    for (unsigned i=0;i<38;++i)
        memory.bytes[Memory::address(p[0],static_cast<uint16_t>(p[1]+i))] = static_cast<uint8_t>(i*11+sample.index*7+19);
    memory.bytes[Memory::address(p[0],static_cast<uint16_t>(p[1]+1u))] = static_cast<uint8_t>(p[2]);
    for (unsigned i=0;i<14;++i)
        memory.bytes[Memory::address(p[0],static_cast<uint16_t>(p[1]+0x16u+i))] = sample.cursors[i];
    const auto at = 0x70000u+p[4];
    memory.store(at,0x7ee4);memory.store(at+2,p[1]);memory.store(at+4,p[0]);
    return memory;
}
std::vector<uint8_t> relocated(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};
    require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Original MZ header differs");
    exe.at=6;const auto count=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto relocations=exe.number(2);
    require(header<exe.bytes.size() && relocations+count*4<=header,"Original MZ layout differs");
    std::vector<uint8_t> image(exe.bytes.begin()+header,exe.bytes.end());
    exe.at=relocations;
    for (uint32_t i=0;i<count;++i) {
        const auto offset=exe.number(2),segment=exe.number(2),at=segment*16+offset;
        require(at+1<image.size(),"Original relocation exceeds image");
        const auto value=static_cast<uint16_t>(image[at]+(uint16_t{image[at+1]}<<8)+0x1000);
        image[at]=static_cast<uint8_t>(value);image[at+1]=static_cast<uint8_t>(value>>8);
    }
    require(image.size()+0x10000<=1048576,"Original image exceeds memory");
    return image;
}
void compareTrace(DosGetTimeRegisters actual,DosGetTimeRegisters expected) {
    require(((actual.flags^expected.flags)&~uint32_t{0x8d5})==0,"Animation trace control flags differ");
    actual.flags=expected.flags;
    if (actual != expected) {
        std::cerr << "trace actual=" << std::hex << actual.cs << ':' << actual.ip << " expected=" << expected.cs << ':' << expected.ip << std::dec << '\n';
        throw std::runtime_error("Animation instruction register trace differs");
    }
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};
    const auto image=relocated(root);
    for (char c : std::string("LZANIM01")) require(input.number(1)==static_cast<uint8_t>(c),"Animation fixture magic differs");
    const auto count=input.number(4);
    require(count==1011,"Animation case count differs");
    uint64_t comparisons=0,totalWrites=0,transferred=0;
    unsigned errors=0,wrapped=0,copyCases=0,modelCases=0;
    for (uint32_t index=0;index<count;++index) {
        Case sample;
        sample.index=input.number(4);
        for (auto& value : sample.profile) value=static_cast<uint16_t>(input.number(2));
        for (auto& value : sample.cursors) value=static_cast<uint8_t>(input.number(1));
        require(sample.index==index && sample.profile[2]<=255 && sample.profile[5]<=1 && sample.profile[6]<=1,"Animation case domain differs");
        sample.initial=input.registers();sample.final=input.registers();
        const auto states=input.number(4);
        require(states>1 && states<1000,"Animation trace length differs");
        for (uint32_t i=0;i<states;++i) sample.trace.push_back(input.registers());
        const auto writes=input.number(4);
        require(writes<1000,"Animation write count differs");
        for (uint32_t i=0;i<writes;++i) {
            Write w{input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require(w.address<1048576 && (w.size==1 || w.size==2),"Animation write domain differs");
            sample.writes.push_back(w);
        }
        const auto initial=initialMemory(sample,image);
        auto expected=initial;
        for (const auto& w : sample.writes) expected.store(w.address,w.value,w.size);
        if (!sample.profile[6]) {
            const auto& p=sample.profile;
            const auto cursor=[&](unsigned offset) {
                std::array<uint8_t,7> value{};
                for (unsigned i=0;i<7;++i)
                    value[i]=initial.bytes[Memory::address(p[0],static_cast<uint16_t>(p[1]+offset+i))];
                return lezac::gameplay::ActorAnimation{value[0],value[1],value[2],value[3],value[4],value[5],std::bit_cast<int8_t>(value[6])};
            };
            auto active=cursor(0x16);
            const bool advanced=active.advance(cursor(0x1d));
            const auto packed=active.packed();
            for (unsigned i=0;i<7;++i)
                require(packed[i]==expected.bytes[Memory::address(p[0],static_cast<uint16_t>(p[1]+0x16u+i))],
                    "Shared production animation model differs from original bytes");
            const auto visual=0x1aa20u+0xc224u+p[2]*8u;
            const bool wrote=std::any_of(sample.writes.begin(),sample.writes.end(),[&](const Write& w) {
                return w.size==2 && w.address==visual;
            });
            require(advanced==wrote,"Shared production model advance/descriptor-write boundary differs");
            if (advanced) require(expected.word(visual)==initial.word(0x1aa20+0xc324+active.current*4u),
                "Shared production model selected the wrong descriptor word");
            ++modelCases;
        }
        for (unsigned variant=0;variant<4;++variant) {
            auto memory=initial;
            const auto bus=memory.bus();
            ActorAnimationOperation operation(sample.initial,0x1000);
            unsigned grants=0;
            const auto copies=[&](uint16_t requested) -> uint16_t {
                ++grants;
                if (variant==2 && grants%2==1) return 0;
                return std::min<uint16_t>(requested,variant==0 ? 1 : variant==1 ? 2 : 7);
            };
            const auto untouched=operation.snapshot();
            require(operation.advance(0,bus,copies)==0 && operation.snapshot()==untouched && memory.writes.empty(),"Zero animation budget mutated state");
            size_t row=0;
            while (!operation.finished()) {
                require(operation.snapshot().dispatchedInstructions<10000,"Animation did not finish");
                if (variant==0) { compareTrace(operation.snapshot().registers,sample.trace.at(row++));++comparisons; }
                require(operation.advance(variant==0 ? 1 : 17,bus,copies)>0,"Animation did not dispatch");
                operation=ActorAnimationOperation(operation.snapshot());
            }
            if (variant==0) {
                compareTrace(operation.snapshot().registers,sample.trace.at(row++));++comparisons;
                require(row==sample.trace.size(),"Animation original trace not fully consumed");
            }
            require(operation.snapshot().registers==sample.final,"Animation endpoint registers/flags differ");
            require(memory.writes==sample.writes,"Animation ordered writes differ");
            require(memory.bytes==expected.bytes,"Animation complete memory differs");
            require(operation.atBehaviorDispatch()==(sample.profile[6]==0),"Animation dispatch/runtime-error outcome differs");
            const auto done=operation.snapshot();
            require(operation.advance(5,bus,copies)==0 && operation.snapshot()==done,"Finished animation was not inert");
            if (variant==0) {
                transferred+=done.transferredBytes;
                copyCases+=done.transferredBytes!=0;
            }
        }
        totalWrites+=sample.writes.size();errors+=sample.profile[6]!=0;wrapped+=sample.profile[1]>=0xffe7;
    }
    require(input.at==input.bytes.size(),"Animation fixture has trailing bytes");
    require(errors==3 && wrapped==72 && copyCases>0,"Animation corpus coverage differs");
    std::cout << "actor_animation_original=ok cases=" << count << " replays=" << count*4
        << " comparisons=" << comparisons << " writes=" << totalWrites << " string_bytes=" << transferred
        << " wrapped_records=" << wrapped << " runtime_errors=" << errors
        << " shared_model_cases=" << modelCases
        << " behavior_executed=0 actual_app_integration=0 whole_game_parity=0\n";
}
void unit() {
    DosGetTimeRegisters r;
    r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fde;r.bp=0x3ffe;r.ip=0x6053;
    unsigned rejected=0;
    for (unsigned variant=0;variant<3;++variant) {
        auto wrong=r;
        if (variant==0) ++wrong.cs;
        if (variant==1) ++wrong.ds;
        if (variant==2) ++wrong.ip;
        try { ActorAnimationOperation invalid(wrong,0x1000); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    require(rejected==3,"Animation entry validation differs");
    Memory memory;
    auto state=ActorAnimationOperation(r,0x1000).snapshot();
    state.registers.cs=0x1920;state.registers.ip=0x91f;state.registers.cx=7;
    ActorAnimationOperation zeroGrant(state);
    require(zeroGrant.advance(1,memory.bus(),[](uint16_t) { return uint16_t{0}; })==1 &&
        zeroGrant.snapshot().registers==state.registers && zeroGrant.snapshot().transferredBytes==0 &&
        memory.writes.empty() && !zeroGrant.finished(),"Zero copy credit changed guest state");
    ActorAnimationOperation invalidGrant(state);
    bool badGrant=false;
    try { invalidGrant.advance(1,memory.bus(),[](uint16_t n) { return static_cast<uint16_t>(n+1u); }); }
    catch (const std::domain_error&) { badGrant=true; }
    require(badGrant && memory.writes.empty(),"Oversized animation copy grant was accepted");
    std::cout << "actor_animation_unit=ok entry_rejections=3 oversized_copy_rejected=1 zero_copy_stalls=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==3,"Expected animation oracle and original root");replay(argv[1],argv[2]); }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "actor_animation=failed " << error.what() << '\n';
        return 1;
    }
}
