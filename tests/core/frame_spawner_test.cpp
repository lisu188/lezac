#include "core/frame_spawner.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
std::vector<uint8_t> readFile(const char* path) {
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "Cannot read spawner test input");
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
struct Write {
    uint32_t address;
    uint8_t size;
    uint16_t value;
    bool operator==(const Write&) const = default;
};
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t s, uint16_t o) { return (uint32_t{s} * 16 + o) & 0xfffffu; }
    TimerIrqBus bus() {
        TimerIrqBus result;
        result.readByte = [this](uint16_t s, uint16_t o) { return bytes[address(s,o)]; };
        result.readWord = [this](uint16_t s, uint16_t o) {
            const auto at=address(s,o);
            return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[(at+1u)&0xfffffu]}<<8));
        };
        result.writeByte = [this](uint16_t s, uint16_t o, uint8_t v) {
            const auto at=address(s,o); bytes[at]=v; writes.push_back({at,1,v});
        };
        result.writeWord = [this](uint16_t s, uint16_t o, uint16_t v) {
            const auto at=address(s,o); bytes[at]=static_cast<uint8_t>(v);
            bytes[(at+1u)&0xfffffu]=static_cast<uint8_t>(v>>8); writes.push_back({at,2,v});
        };
        result.inByte = [](uint16_t)->uint8_t { throw std::runtime_error("Unexpected spawner I/O"); };
        result.outByte = [](uint16_t,uint8_t) { throw std::runtime_error("Unexpected spawner I/O"); };
        return result;
    }
};
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated spawner corpus");
        uint32_t result=0;
        for (unsigned i=0;i<n;++i) result|=uint32_t{bytes[at++]}<<(i*8);
        return result;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value=static_cast<uint16_t>(number(2));
        r.flags=number(4); return r;
    }
};
Memory loadImage(const char* path) {
    const auto exe=readFile(path);
    const auto word=[&](size_t at) {
        require(at+2<=exe.size(),"Truncated original image");
        return uint32_t{exe[at]}|(uint32_t{exe[at+1]}<<8);
    };
    require(word(0)==0x5a4d && word(6)==468 && word(8)*16==0x770,"Original MZ layout differs");
    Memory memory;
    require(exe.size()>0x770 && exe.size()-0x770<=memory.bytes.size()-0x10000,"Original image size differs");
    std::copy(exe.begin()+0x770,exe.end(),memory.bytes.begin()+0x10000);
    for (uint32_t i=0;i<468;++i) {
        const auto entry=word(24)+i*4;
        const auto at=0x10000+word(entry+2)*16+word(entry);
        require(at+2<=memory.bytes.size(),"Original relocation exceeds image");
        const auto value=static_cast<uint16_t>((memory.bytes[at]|(uint16_t{memory.bytes[at+1]}<<8))+0x1000);
        memory.bytes[at]=static_cast<uint8_t>(value);memory.bytes[at+1]=static_cast<uint8_t>(value>>8);
    }
    return memory;
}
void compareTrace(DosGetTimeRegisters actual, DosGetTimeRegisters expected, uint32_t index, size_t cursor) {
    const bool control=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    actual.flags=expected.flags;
    if (!control || actual!=expected) {
        std::cerr << "case=" << index << " boundary=" << cursor << " actual=" << std::hex << actual.cs << ':'
            << actual.ip << " expected=" << expected.cs << ':' << expected.ip << std::dec << '\n';
        throw std::runtime_error("Spawner instruction register/control-flag trace differs");
    }
}
void replay(const char* fixture, const char* exe) {
    Reader reader{readFile(fixture)};
    for (char c : std::string("LZSPWN01")) require(reader.number(1)==static_cast<uint8_t>(c),"Spawner corpus magic differs");
    const auto count=reader.number(4);require(count==151,"Spawner corpus case count differs");
    const auto image=loadImage(exe);
    uint64_t comparisons=0, instructions=0;
    uint32_t errors=0;
    for (uint32_t index=0;index<count;++index) {
        require(reader.number(4)==index,"Spawner case index differs");
        const auto error=reader.number(4);require(error<=1,"Spawner error field differs");errors+=error;
        const auto entry=reader.registers(), endpoint=reader.registers();
        auto initial=image;
        const auto seeds=reader.number(4);require(seeds<300,"Spawner input count exceeds reserve");
        for (uint32_t i=0;i<seeds;++i) {
            const auto at=reader.number(4), length=reader.number(4);
            require(length<=8192 && uint64_t{at}+length<=initial.bytes.size() &&
                reader.at+length<=reader.bytes.size(),"Spawner seed leaves memory reserve");
            std::copy_n(reader.bytes.begin()+static_cast<std::ptrdiff_t>(reader.at),length,initial.bytes.begin()+at);
            reader.at+=length;
        }
        const auto states=reader.number(4);require(states>1 && states<200000,"Spawner trace reserve differs");
        std::vector<DosGetTimeRegisters> trace;
        for (uint32_t i=0;i<states;++i) trace.push_back(reader.registers());
        const auto writeCount=reader.number(4);require(writeCount<20000,"Spawner write reserve differs");
        std::vector<Write> writes;
        auto expected=initial.bytes;
        for (uint32_t i=0;i<writeCount;++i) {
            const auto at=reader.number(4);const auto size=reader.number(1);const auto value=reader.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.size(),"Spawner write leaves memory reserve");
            writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
            expected[at]=static_cast<uint8_t>(value);
            if (size==2) expected[at+1]=static_cast<uint8_t>(value>>8);
        }
        for (uint64_t budget : {1u,2u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();
            FrameSpawnerOperation operation(entry,0x1000);
            const auto zero=operation.snapshot();
            require(operation.advance(0,bus)==0 && operation.snapshot()==zero && memory.writes.empty(),
                    "Spawner zero budget changed state");
            size_t cursor=0;compareTrace(operation.snapshot().registers,trace[0],index,cursor);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus);
                require(used>0 && used<=budget,"Spawner instruction grant differs");
                cursor+=static_cast<size_t>(used);
                require(cursor<trace.size(),"Spawner exceeded original endpoint");
                compareTrace(operation.snapshot().registers,trace[cursor],index,cursor);++comparisons;
                operation=FrameSpawnerOperation(operation.snapshot());
            }
            const auto final=operation.snapshot();
            require(cursor+1==trace.size() && final.dispatchedInstructions==cursor,"Spawner dispatch count differs");
            require(final.registers==endpoint,"Spawner endpoint registers/flags differ");
            require(final.outcome==(error?FrameSpawnerOutcome::RuntimeError:FrameSpawnerOutcome::Returned),
                    "Spawner final outcome differs");
            require(memory.writes==writes,"Spawner original write order differs");
            require(memory.bytes==expected,"Spawner complete 1 MiB post-state differs");
            require(operation.advance(100,bus)==0 && operation.snapshot()==final,"Finished spawner changed state");
            instructions+=cursor;
        }
    }
    require(reader.at==reader.bytes.size() && errors==2,"Spawner corpus tail/outcomes differ");
    std::cout << "frame_spawner_original=ok cases=" << count << " replays=" << count*4
        << " comparisons=" << comparisons << " instructions=" << instructions << " runtime_errors=" << errors
        << " full_frame_claim=0 work_clock_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3ffe;r.ip=0x7a57;
    unsigned rejected=0;
    for (unsigned field=0;field<3;++field) {
        auto bad=r;if(field==0)bad.cs=0;else if(field==1)bad.ds=0;else bad.ip=0;
        try { FrameSpawnerOperation op(bad,0x1000); } catch(const std::invalid_argument&) {++rejected;}
    }
    require(rejected==3,"Spawner accepted invalid entry");
    Memory memory;const auto bus=memory.bus();FrameSpawnerOperation op(r,0x1000);
    const auto zero=op.snapshot();require(op.advance(0,bus)==0 && op.snapshot()==zero,"Spawner zero budget differs");
    require(op.advance(100,bus)==7 && op.returned(),"Zero-spawner reset path differs");
    std::cout << "frame_spawner_unit=ok entry_rejections=3 empty_dispatches=7\n";
}
}
int main(int argc,char** argv) {
    try {
        if(argc==1)unit();else if(argc==3)replay(argv[1],argv[2]);
        else throw std::runtime_error("Expected spawner corpus and original EXE");
        return 0;
    } catch(const std::exception& error) {
        std::cerr << "frame_spawner=failed " << error.what() << '\n';return 1;
    }
}
