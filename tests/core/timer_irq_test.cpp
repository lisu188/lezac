#include "core/timer_irq.hpp"

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

using namespace lezac::core;

namespace {
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}
struct Reader {
    std::vector<uint8_t> bytes;
    std::size_t cursor = 0;
    uint32_t number(unsigned count) {
        require(count <= 4 && count <= bytes.size() - cursor, "projection truncated");
        uint32_t result = 0;
        for (unsigned index = 0; index < count; ++index) result |= uint32_t{bytes[cursor++]} << (index * 8);
        return result;
    }
    uint16_t word() { return static_cast<uint16_t>(number(2)); }
    std::vector<uint8_t> take(std::size_t count) {
        require(count <= bytes.size() - cursor, "projection bytes truncated");
        std::vector<uint8_t> result(bytes.begin() + cursor, bytes.begin() + cursor + count);
        cursor += count;
        return result;
    }
};
using ByteEvent = std::tuple<uint32_t, uint8_t, uint32_t>;
using IoEvent = std::tuple<bool, uint16_t, uint8_t, uint32_t>;
struct Expected {
    TimerIrqRegisters registers;
    uint32_t defined, ioCount, writeCount, readCount;
    std::vector<uint8_t> stack, globals;
};
Expected state(Reader& reader) {
    TimerIrqRegisters r;
    r.ax=reader.word(); r.bx=reader.word(); r.cx=reader.word(); r.dx=reader.word();
    r.si=reader.word(); r.di=reader.word(); r.bp=reader.word(); r.cs=reader.word();
    r.ds=reader.word(); r.es=reader.word(); r.ss=reader.word(); r.sp=reader.word(); r.ip=reader.word();
    r.flags=reader.number(4);
    const auto mask=reader.number(4), io=reader.number(4), writes=reader.number(4), reads=reader.number(4);
    return {r, mask, io, writes, reads, reader.take(112), reader.take(10)};
}
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1024 * 1024);
    std::vector<ByteEvent> writes, reads;
    std::vector<IoEvent> io;
    uint32_t dispatch = 0;
    uint8_t port61 = 0;
    bool bios = false;
    static bool stack(uint32_t address) { return address >= 0x8fdb0 && address < 0x8fe20; }
    uint32_t read(uint16_t segment, uint16_t offset, unsigned size) {
        const uint32_t address = uint32_t{segment} * 16 + offset;
        uint32_t result = 0;
        for (unsigned index=0; index<size; ++index) {
            const uint32_t at=(address+index)&0xfffff;
            require(stack(at) || (at>=0x222e0 && at<=0x223e4) || (at>=0x30000 && at<0x3030c) || bios,
                    "read outside observed memory");
            result |= uint32_t{bytes[at]} << (index*8);
            if (!stack(at)) reads.emplace_back(at, bytes[at], dispatch);
        }
        return result;
    }
    void write(uint16_t segment, uint16_t offset, uint32_t value, unsigned size) {
        const uint32_t address=uint32_t{segment}*16+offset;
        for (unsigned index=0; index<size; ++index) {
            const uint32_t at=(address+index)&0xfffff;
            require(stack(at) || (at>=0x222e0 && at<0x222e2) || (at>=0x223c0 && at<0x223c3) || at==0x223e4 || bios,
                    "write outside original footprint");
            bytes[at]=static_cast<uint8_t>(value>>(index*8));
            writes.emplace_back(at, bytes[at], dispatch);
        }
    }
    TimerIrqBus bus() {
        return {
            [&](uint16_t s,uint16_t o){return static_cast<uint8_t>(read(s,o,1));},
            [&](uint16_t s,uint16_t o){return static_cast<uint16_t>(read(s,o,2));},
            [&](uint16_t s,uint16_t o){return read(s,o,4);},
            [&](uint16_t s,uint16_t o,uint8_t v){write(s,o,v,1);},
            [&](uint16_t s,uint16_t o,uint16_t v){write(s,o,v,2);},
            [&](uint16_t s,uint16_t o,uint32_t v){write(s,o,v,4);},
            [&](uint16_t port){require(port==0x61,"unexpected input port"); io.emplace_back(false,port,port61,dispatch); return port61;},
            [&](uint16_t port,uint8_t value){
                require(port==0x61 || port==0x42 || port==0x43 || (bios && port==0x20),"unexpected output port");
                io.emplace_back(true,port,value,dispatch); if(port==0x61)port61=value;
            }
        };
    }
    std::vector<uint8_t> globals() const {
        std::vector<uint8_t> result;
        for (auto [address,count] : {std::pair{0x222e0,2},std::pair{0x223c0,3},std::pair{0x223e0,5}})
            result.insert(result.end(),bytes.begin()+address,bytes.begin()+address+count);
        return result;
    }
};

std::size_t compare(Reader reader, const std::vector<uint8_t>& bank) {
    require(reader.take(8)==std::vector<uint8_t>({'L','Z','T','I','M','R','0','1'}),"projection version differs");
    const auto count=reader.number(4);
    require(count==164 && bank.size()==782,"case domain or sound bank differs");
    std::size_t comparisons=0;
    for(unsigned caseIndex=0;caseIndex<count;++caseIndex) {
        const auto stateCount=reader.number(4),ioCount=reader.number(4),writeCount=reader.number(4),readCount=reader.number(4);
        const auto port=static_cast<uint8_t>(reader.number(1));
        std::vector<Expected> states;
        for(unsigned i=0;i<stateCount;++i)states.push_back(state(reader));
        std::vector<IoEvent> expectedIo;
        for(unsigned i=0;i<ioCount;++i){
            const bool out=reader.number(1)!=0; const auto port=reader.word();
            const auto value=static_cast<uint8_t>(reader.number(1)); const auto dispatch=reader.number(4);
            expectedIo.emplace_back(out,port,value,dispatch);
        }
        std::vector<ByteEvent> expectedWrites,expectedReads;
        for(auto [target,n]:{std::pair{&expectedWrites,writeCount},std::pair{&expectedReads,readCount}})
            for(unsigned i=0;i<n;++i){
                const auto address=reader.number(4); const auto value=static_cast<uint8_t>(reader.number(1));
                target->emplace_back(address,value,reader.number(4));
            }
        for(bool restoreEveryStep:{false,true}) {
            Memory memory;
            memory.port61=port;
            std::copy(bank.begin()+2,bank.end(),memory.bytes.begin()+0x30000);
            std::copy(states.front().stack.begin(),states.front().stack.end(),memory.bytes.begin()+0x8fdb0);
            unsigned global=0;
            for(auto [at,n]:{std::pair{0x222e0,2},std::pair{0x223c0,3},std::pair{0x223e0,5}})
                for(int i=0;i<n;++i)memory.bytes[at+i]=states.front().globals[global++];
            TimerIrqOperation operation(states.front().registers,0x1000,0,false);
            const auto bus=memory.bus();
            for(unsigned index=0;index<stateCount;++index) {
                const auto& expected=states[index];
                const auto context="case="+std::to_string(caseIndex)+" state="+std::to_string(index);
                auto r=operation.snapshot().registers,wanted=expected.registers;
                require(((r.flags^wanted.flags)&expected.defined)==0,context+" defined flags differ");
                r.flags=wanted.flags=0;
                require(r==wanted,context+" registers differ");
                require(operation.snapshot().definedFlags==expected.defined,context+" flag mask differs");
                require(memory.globals()==expected.globals,context+" globals differ");
                require(std::equal(expected.stack.begin(),expected.stack.end(),memory.bytes.begin()+0x8fdb0),context+" stack differs");
                require(memory.io.size()==expected.ioCount && memory.writes.size()==expected.writeCount && memory.reads.size()==expected.readCount,
                        context+" bus counts differ");
                ++comparisons;
                const auto before=operation.snapshot();
                require(operation.advance(0,bus)==0 && operation.snapshot()==before,"zero budget changed state");
                if(index+1<stateCount){
                    memory.dispatch=index+1;
                    require(operation.advance(1,bus)==1,"instruction budget differs");
                }
                if(restoreEveryStep)operation=TimerIrqOperation(operation.snapshot());
            }
            require(operation.returned() && operation.advance(100,bus)==0,"terminal state differs");
            require(memory.io==expectedIo,"ordered I/O differs");
            require(memory.writes==expectedWrites,"ordered byte writes differ");
            require(memory.reads==expectedReads,"observed data/bank reads differ");
        }
    }
    require(reader.cursor==reader.bytes.size(),"projection tail differs");
    return comparisons;
}
std::vector<uint8_t> readFile(const char* path) {
    std::ifstream stream(path,std::ios::binary);
    require(stream.good(),"input file missing");
    return {std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()};
}

void biosUnit() {
    Memory memory;
    memory.bios=true;
    memory.bytes[0x70]=0xbe; memory.bytes[0x71]=0x0f; memory.bytes[0x73]=0x10;
    memory.bytes[0x440]=2; memory.bytes[0x43f]=0xa5;
    for(unsigned i=0;i<4;++i)memory.bytes[0x46c+i]=0xff;
    for(unsigned i=0;i<112;++i)memory.bytes[0x8fdb0+i]=static_cast<uint8_t>(i*37+11);
    for(auto [offset,value]:{std::pair{0,0x0400},std::pair{2,0x9000},std::pair{4,0x7246}}){
        memory.bytes[0x8fe00+offset]=static_cast<uint8_t>(value);
        memory.bytes[0x8fe01+offset]=static_cast<uint8_t>(value>>8);
    }
    TimerIrqRegisters registers;
    registers.ax=0x1234; registers.bx=0x2345; registers.cx=0x3456; registers.dx=0x4567;
    registers.si=0x5678; registers.di=0x6789; registers.bp=0x789a;
    registers.cs=0xf000; registers.ip=0xfea5; registers.ds=0x4321; registers.es=0x5432;
    registers.ss=0x8000; registers.sp=0xfe00; registers.flags=0x80207046;
    TimerIrqOperation operation(registers,0x1000,0x200000);
    const auto bus=memory.bus();
    require(operation.advance(9999,bus)==36 && operation.returned(),"BIOS timer return work differs");
    require(memory.bytes[0x440]==1 && memory.bytes[0x43f]==0xa0 &&
            memory.bytes[0x46c]==0 && memory.bytes[0x46d]==0 && memory.bytes[0x46e]==0 && memory.bytes[0x46f]==0,
            "BIOS counter or disk state differs");
    auto expected=registers;
    expected.cs=0x9000; expected.ip=0x400; expected.sp=0xfe06; expected.flags=0x80007246;
    require(operation.snapshot().registers==expected,"BIOS wrapper register restoration differs");
    require(memory.io==std::vector<IoEvent>{{true,0x20,0x20,0}},"PIC EOI differs");
}
}

int main(int argc,char** argv) {
    try {
        biosUnit();
        require(argc==3,"expected projection and PROEFS.SON paths");
        const auto count=compare(Reader{readFile(argv[1])},readFile(argv[2]));
        std::cout<<"timer_irq_original=ok cases=164 comparisons="<<count
                 <<" instructions=98 real_crt_calls=1 ordered_bus_events=1 natural_timing=0\n";
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
