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
void require(bool value,const std::string& message){if(!value)throw std::runtime_error(message);}
struct Reader {
    std::vector<uint8_t> bytes; std::size_t cursor=0;
    uint32_t number(unsigned count){
        require(count<=4 && count<=bytes.size()-cursor,"projection truncated");
        uint32_t value=0;for(unsigned i=0;i<count;++i)value|=uint32_t{bytes[cursor++]}<<(i*8);return value;
    }
    uint16_t word(){return static_cast<uint16_t>(number(2));}
    std::vector<uint8_t> take(unsigned count){
        require(count<=bytes.size()-cursor,"memory projection truncated");
        std::vector<uint8_t> value(bytes.begin()+cursor,bytes.begin()+cursor+count);cursor+=count;return value;
    }
};
struct Expected {
    TimerIrqRegisters registers;
    uint32_t mask,ticks;
    uint8_t motor,drive;
    uint32_t ioCount;
    std::vector<uint8_t> stack,globals;
};
Expected readState(Reader& reader){
    TimerIrqRegisters r;
    r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();r.si=reader.word();r.di=reader.word();r.bp=reader.word();
    r.cs=reader.word();r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();r.flags=reader.number(4);
    const auto mask=reader.number(4),ticks=reader.number(4);
    const auto motor=static_cast<uint8_t>(reader.number(1)),drive=static_cast<uint8_t>(reader.number(1));
    const auto io=reader.number(4);
    return {r,mask,ticks,motor,drive,io,reader.take(128),reader.take(10)};
}
using Io=std::tuple<bool,uint16_t,uint8_t>;
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1024*1024),known=bytes,writable=bytes;
    std::vector<Io> script;
    unsigned io=0;
    void seed(uint32_t address,const std::vector<uint8_t>& values,bool canWrite=false){
        for(unsigned index=0;index<values.size();++index){const auto at=(address+index)&0xfffff;
            require(!known[at] || bytes[at]==values[index],"contradictory aliased initial inputs");
            bytes[at]=values[index];known[at]=1;if(canWrite)writable[at]=1;
        }
    }
    uint32_t read(uint16_t segment,uint16_t offset,unsigned count)const{
        uint32_t value=0;
        for(unsigned i=0;i<count;++i){const auto at=(uint32_t{segment}*16+offset+i)&0xfffff;
            require(known[at],"read outside observed input memory");value|=uint32_t{bytes[at]}<<(i*8);
        }return value;
    }
    void write(uint16_t segment,uint16_t offset,uint32_t value,unsigned count){
        for(unsigned i=0;i<count;++i){const auto at=(uint32_t{segment}*16+offset+i)&0xfffff;
            require(writable[at],"write outside original owned footprint");bytes[at]=static_cast<uint8_t>(value>>(i*8));
        }
    }
    TimerIrqBus bus(){return {
        [&](uint16_t s,uint16_t o){return static_cast<uint8_t>(read(s,o,1));},
        [&](uint16_t s,uint16_t o){return static_cast<uint16_t>(read(s,o,2));},
        [&](uint16_t s,uint16_t o){return read(s,o,4);},
        [&](uint16_t s,uint16_t o,uint8_t v){write(s,o,v,1);},
        [&](uint16_t s,uint16_t o,uint16_t v){write(s,o,v,2);},
        [&](uint16_t s,uint16_t o,uint32_t v){write(s,o,v,4);},
        [&](uint16_t port){require(io<script.size() && !std::get<0>(script[io]) && std::get<1>(script[io])==port,
            "input I/O boundary differs");return std::get<2>(script[io++]);},
        [&](uint16_t port,uint8_t value){require(io<script.size() && script[io]==Io{true,port,value},
            "output I/O differs");++io;}
    };}
};
std::size_t compare(Reader reader){
    require(reader.take(8)==std::vector<uint8_t>({'L','Z','T','I','M','N','0','1'}),"projection version differs");
    const auto cases=reader.number(4);require(cases>0 && cases<=64,"natural case domain differs");
    std::size_t comparisons=0;
    for(unsigned caseIndex=0;caseIndex<cases;++caseIndex){
        const auto game=reader.word(),ss=reader.word(),stackBase=reader.word(),bankSegment=reader.word(),bankOffset=reader.word();
        const auto id=reader.number(4),stateCount=reader.number(4),ioCount=reader.number(4);
        const auto bank=reader.take(780);
        std::vector<Expected> states;for(unsigned i=0;i<stateCount;++i)states.push_back(readState(reader));
        std::vector<Io> io;
        for(unsigned i=0;i<ioCount;++i){const bool out=reader.number(1)!=0;const auto port=reader.word();
            io.emplace_back(out,port,static_cast<uint8_t>(reader.number(1)));}
        const uint32_t data=(uint32_t{game}+0xaa2)*16,stack=uint32_t{ss}*16+stackBase;
        for(bool restoreEveryStep:{false,true}){
            Memory memory;memory.script=io;
            memory.seed(uint32_t{bankSegment}*16+bankOffset,bank);
            memory.seed(stack,states[0].stack,true);
            unsigned index=0;
            for(auto [offset,count]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}}){
                const std::vector<uint8_t> input(states[0].globals.begin()+index,states[0].globals.begin()+index+count);
                memory.seed(data+offset,input);index+=count;
            }
            for(auto [offset,count]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c4,1}})
                for(int i=0;i<count;++i)memory.writable[data+offset+i]=1;
            memory.seed(0x70,{0xbe,0x0f,static_cast<uint8_t>(game),static_cast<uint8_t>(game>>8)});
            const auto ticks=states[0].ticks;
            memory.seed(0x46c,{static_cast<uint8_t>(ticks),static_cast<uint8_t>(ticks>>8),
                static_cast<uint8_t>(ticks>>16),static_cast<uint8_t>(ticks>>24)},true);
            memory.seed(0x440,{states[0].motor},true);memory.seed(0x43f,{states[0].drive},true);
            TimerIrqOperation operation(states[0].registers,game,id);
            const auto bus=memory.bus();
            for(unsigned step=0;step<stateCount;++step){
                const auto& expected=states[step];auto r=operation.snapshot().registers,wanted=expected.registers;
                const auto context="natural case="+std::to_string(caseIndex)+" state="+std::to_string(step);
                require(((r.flags^wanted.flags)&expected.mask)==0 &&
                    (operation.snapshot().definedFlags&expected.mask)==expected.mask,context+" defined flags differ");
                r.flags=wanted.flags=0;require(r==wanted,context+" registers differ");
                require(std::equal(expected.stack.begin(),expected.stack.end(),memory.bytes.begin()+stack),context+" stack differs");
                unsigned g=0;
                for(auto [offset,count]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                    for(int i=0;i<count;++i)require(memory.bytes[data+offset+i]==expected.globals[g++],context+" globals differ");
                require(memory.read(0x40,0x6c,4)==expected.ticks && memory.bytes[0x440]==expected.motor &&
                    memory.bytes[0x43f]==expected.drive && memory.io==expected.ioCount,context+" BIOS or I/O differs");
                ++comparisons;
                const auto before=operation.snapshot();require(operation.advance(0,bus)==0 && operation.snapshot()==before,"zero budget changed state");
                if(step+1<stateCount)require(operation.advance(1,bus)==1,"natural dispatch budget differs");
                if(restoreEveryStep)operation=TimerIrqOperation(operation.snapshot());
            }
            require(operation.returned() && operation.advance(99,bus)==0 && memory.io==ioCount,"natural return differs");
        }
    }
    require(reader.cursor==reader.bytes.size(),"natural projection tail differs");return comparisons;
}
}
int main(int argc,char** argv){try{
    require(argc==2,"expected natural projection");std::ifstream stream(argv[1],std::ios::binary);require(stream.good(),"projection missing");
    Reader reader{{std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()}};
    const auto count=compare(std::move(reader));
    std::cout<<"timer_irq_natural=ok comparisons="<<count<<" irq_executed=1 device_inputs_observed=1 scheduler_claim=0\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
