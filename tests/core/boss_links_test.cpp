#include "core/boss_links.hpp"

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
void require(bool yes,const char* message) { if (!yes) throw std::runtime_error(message); }
struct Write {
    uint32_t address;
    uint8_t size;
    uint32_t value;
    bool operator==(const Write&) const = default;
};
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned count) {
        require(at+count<=bytes.size(),"Truncated link fixture");
        uint32_t result=0;
        for (unsigned i=0;i<count;++i) result|=uint32_t{bytes[at++]}<<(8*i);
        return result;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
};
std::vector<uint8_t> read(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);
    require(input.good(),"Missing original link input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t segment,uint16_t offset) { return (uint32_t{segment}*16+offset)&0xfffffu; }
    uint16_t word(uint32_t at) const { return static_cast<uint16_t>(bytes[at]|(uint16_t{bytes[(at+1u)&0xfffffu]}<<8)); }
    void store(uint32_t at,uint32_t value,uint8_t size=2) {
        for (unsigned i=0;i<size;++i) bytes[(at+i)&0xfffffu]=static_cast<uint8_t>(value>>(8*i));
    }
    TimerIrqBus bus() {
        TimerIrqBus bus;
        bus.readByte=[this](uint16_t s,uint16_t o) { return bytes[address(s,o)]; };
        bus.readWord=[this](uint16_t s,uint16_t o) { return word(address(s,o)); };
        bus.writeByte=[this](uint16_t s,uint16_t o,uint8_t v) { const auto at=address(s,o);store(at,v,1);writes.push_back({at,1,v}); };
        bus.writeWord=[this](uint16_t s,uint16_t o,uint16_t v) { const auto at=address(s,o);store(at,v);writes.push_back({at,2,v}); };
        return bus;
    }
};
struct Case {
    uint32_t index=0;
    std::array<uint16_t,14> profile{};
    DosGetTimeRegisters initial,final;
    std::vector<DosGetTimeRegisters> trace;
    std::vector<Write> writes;
};
Memory initialMemory(const Case& sample,const std::vector<uint8_t>& image,const std::array<uint8_t,768>& sine) {
    const auto& p=sample.profile;
    Memory memory;
    std::copy(image.begin(),image.end(),memory.bytes.begin()+0x10000);
    for (unsigned i=0;i<1040;++i) memory.bytes[0x70000u+p[12]-1024u+i]=static_cast<uint8_t>(i*29+sample.index*7+11);
    memory.store(0x1aa20+0x1afa,p[11]);
    std::copy(sine.begin(),sine.end(),memory.bytes.begin()+0x1aa20+0x7bda);
    for (unsigned visual=0;visual<256;++visual) {
        const auto at=0x1aa20u+0xc21eu+visual*8;
        memory.store(at,static_cast<uint16_t>(visual*977+sample.index*13+0x7fff));
        memory.store(at+2,static_cast<uint16_t>(visual*1013+sample.index*17+0x8000));
        memory.store(at+4,static_cast<uint16_t>(visual*37+sample.index*19+0xa55a));
        memory.store(at+6,static_cast<uint16_t>(visual*41+sample.index*23+0x5aa5));
    }
    for (unsigned link=1;link<=p[0];++link) {
        const auto at=0x1aa20u+0x79eau+link*16;
        for (unsigned i=0;i<16;++i) memory.bytes[at+i]=static_cast<uint8_t>(i*11+sample.index*7+link*19);
        memory.bytes[at]=static_cast<uint8_t>(p[6]);memory.bytes[at+1]=static_cast<uint8_t>(p[7]);
        memory.bytes[at+2]=static_cast<uint8_t>(p[2]);
        memory.bytes[at+3]=static_cast<uint8_t>(p[0]>=2 && p[0]<=7 ? (link%2 ? 255 : 0) : p[1]);
        memory.bytes[at+4]=static_cast<uint8_t>(p[4]);memory.bytes[at+5]=static_cast<uint8_t>(p[5]);
        memory.bytes[at+6]=static_cast<uint8_t>(p[3]+link-1);
        memory.store(at+7,p[8]);memory.store(at+9,p[9]);memory.bytes[at+15]=static_cast<uint8_t>(p[10]);
    }
    memory.bytes[0x1aa20+0x79f9]=static_cast<uint8_t>(p[0]);
    memory.store(0x70000u+p[12],0x7ec5);
    return memory;
}
std::vector<uint8_t> relocated(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};
    require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Original link MZ header differs");
    exe.at=6;const auto count=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto relocations=exe.number(2);
    require(header<exe.bytes.size() && relocations+count*4<=header,"Original link MZ layout differs");
    std::vector<uint8_t> image(exe.bytes.begin()+header,exe.bytes.end());
    exe.at=relocations;
    for (uint32_t i=0;i<count;++i) {
        const auto offset=exe.number(2),segment=exe.number(2),at=segment*16+offset;
        require(at+1<image.size(),"Original link relocation exceeds image");
        const auto value=static_cast<uint16_t>(image[at]+(uint16_t{image[at+1]}<<8)+0x1000);
        image[at]=static_cast<uint8_t>(value);image[at+1]=static_cast<uint8_t>(value>>8);
    }
    require(image.size()+0x10000<=1048576,"Original link image exceeds memory");
    return image;
}
void compareTrace(DosGetTimeRegisters actual,DosGetTimeRegisters expected,uint32_t index,size_t row) {
    require(((actual.flags^expected.flags)&~uint32_t{0x8d5})==0,"Link trace control flags differ");
    actual.flags=expected.flags;
    if (actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " dx=" << actual.dx << '/' << expected.dx << std::dec << '\n';
        throw std::runtime_error("Link instruction register trace differs");
    }
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};
    const auto image=relocated(root);
    for (char c : std::string("LZLINK01")) require(input.number(1)==static_cast<uint8_t>(c),"Link fixture magic differs");
    const auto count=input.number(4);
    require(count==1413,"Original link case count differs");
    std::array<uint8_t,768> sine{};
    for (auto& byte : sine) byte=static_cast<uint8_t>(input.number(1));
    uint64_t comparisons=0,totalWrites=0;
    unsigned errors=0,large=0;
    for (uint32_t index=0;index<count;++index) {
        Case sample;
        sample.index=input.number(4);
        for (auto& value : sample.profile) value=static_cast<uint16_t>(input.number(2));
        require(sample.index==index && sample.profile[0]<=255 && sample.profile[13]<=1,"Link profile domain differs");
        sample.initial=input.registers();sample.final=input.registers();
        const auto states=input.number(4);
        require(states>1 && states<50000,"Link trace length differs");
        for (uint32_t i=0;i<states;++i) sample.trace.push_back(input.registers());
        const auto writes=input.number(4);
        require(writes<10000,"Link write count differs");
        for (uint32_t i=0;i<writes;++i) {
            Write write{input.number(4),static_cast<uint8_t>(input.number(1)),input.number(4)};
            require(write.address<1048576 && (write.size==1 || write.size==2),"Link write domain differs");
            sample.writes.push_back(write);
        }
        const auto initial=initialMemory(sample,image,sine);
        auto expected=initial;
        for (const auto& write : sample.writes) expected.store(write.address,write.value,write.size);
        for (unsigned variant=0;variant<4;++variant) {
            auto memory=initial;
            const auto bus=memory.bus();
            BossLinksOperation operation(sample.initial,0x1000);
            const auto untouched=operation.snapshot();
            require(operation.advance(0,bus)==0 && operation.snapshot()==untouched && memory.writes.empty(),"Zero link budget mutated state");
            size_t row=0;
            while (!operation.finished()) {
                require(operation.snapshot().dispatchedInstructions<100000,"Link operation did not finish");
                if (variant==0) { compareTrace(operation.snapshot().registers,sample.trace.at(row),index,row);++row;++comparisons; }
                require(operation.advance(variant==0 ? 1 : variant==1 ? 17 : variant==2 ? 97 : 4096,bus)>0,"Link operation did not dispatch");
                operation=BossLinksOperation(operation.snapshot());
            }
            if (variant==0) {
                compareTrace(operation.snapshot().registers,sample.trace.at(row),index,row);++row;++comparisons;
                require(row==sample.trace.size(),"Original link trace not fully consumed");
            }
            require(operation.snapshot().registers==sample.final,"Link endpoint registers/flags differ");
            require(memory.writes==sample.writes,"Link ordered writes differ");
            require(memory.bytes==expected.bytes,"Link complete memory differs");
            require(operation.returned()==(sample.profile[13]==0),"Link runtime-error/return outcome differs");
            const auto done=operation.snapshot();
            require(operation.advance(11,bus)==0 && operation.snapshot()==done,"Finished link operation is not inert");
        }
        totalWrites+=sample.writes.size();errors+=sample.profile[13]!=0;large+=sample.profile[0]==255;
    }
    require(input.at==input.bytes.size() && errors==3 && large==1,"Original link corpus coverage differs");
    std::cout << "boss_links_original=ok cases=" << count << " replays=" << count*4 << " comparisons=" << comparisons
        << " writes=" << totalWrites << " runtime_errors=" << errors << " maximum_count_cases=" << large
        << " actual_app_integration=0 full_frame_claim=0 whole_game_parity=0\n";
}
void unit() {
    DosGetTimeRegisters registers;
    registers.cs=0x1000;registers.ds=0x1aa2;registers.ss=0x7000;
    registers.sp=0x3fde;registers.bp=0x3ffe;registers.ip=0x432a;
    unsigned rejected=0;
    for (unsigned variant=0;variant<3;++variant) {
        auto wrong=registers;
        if (variant==0) ++wrong.cs;
        if (variant==1) ++wrong.ds;
        if (variant==2) ++wrong.ip;
        try { BossLinksOperation invalid(wrong,0x1000); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    require(rejected==3,"Link entry validation differs");
    Memory memory;
    auto state=BossLinksOperation(registers,0x1000).snapshot();
    state.registers.cs=0x4000;
    bool unknown=false;
    try { BossLinksOperation(state).advance(1,memory.bus()); }
    catch (const std::domain_error&) { unknown=true; }
    require(unknown && memory.writes.empty(),"Unknown link segment did not fail closed");
    std::cout << "boss_links_unit=ok entry_rejections=3 unknown_segment_rejected=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==3,"Expected original link fixture and source root");replay(argv[1],argv[2]); }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "boss_links=failed " << error.what() << '\n';return 1;
    }
}
