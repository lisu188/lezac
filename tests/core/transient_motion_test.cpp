#include "core/transient_motion.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <set>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool yes,const char* message) { if (!yes) throw std::runtime_error(message); }
struct Write { uint32_t address;uint8_t size;uint16_t value;bool operator==(const Write&) const = default; };
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);std::vector<Write> writes;
    static uint32_t address(uint16_t s,uint16_t o) { return (uint32_t{s}*16+o)&0xfffffu; }
    uint16_t word(uint16_t s,uint16_t o) const {
        const auto a=address(s,o);return static_cast<uint16_t>(bytes[a]|(uint16_t{bytes[(a+1u)&0xfffffu]}<<8));
    }
    void store(uint32_t a,uint16_t value,uint8_t size=2) {
        bytes[a]=static_cast<uint8_t>(value);if (size==2) bytes[(a+1u)&0xfffffu]=static_cast<uint8_t>(value>>8);
    }
    TimerIrqBus bus() {
        return {
            [this](uint16_t s,uint16_t o) { return bytes[address(s,o)]; },
            [this](uint16_t s,uint16_t o) { return word(s,o); },
            [this](uint16_t s,uint16_t o) { return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16); },
            [this](uint16_t s,uint16_t o,uint8_t v) { const auto a=address(s,o);store(a,v,1);writes.push_back({a,1,v}); },
            [this](uint16_t s,uint16_t o,uint16_t v) { const auto a=address(s,o);store(a,v);writes.push_back({a,2,v}); },
            [this](uint16_t s,uint16_t o,uint32_t v) {
                const auto a=address(s,o);store(a,static_cast<uint16_t>(v));store((a+2u)&0xfffffu,static_cast<uint16_t>(v>>16));
                writes.push_back({a,2,static_cast<uint16_t>(v)});writes.push_back({(a+2u)&0xfffffu,2,static_cast<uint16_t>(v>>16)});
            },
            [](uint16_t p)->uint8_t { require(p==0x61,"Unexpected motion IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected motion IRQ output"); }
        };
    }
};
std::vector<uint8_t> read(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing motion input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated motion fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* v : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *v=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t n) {
        std::vector<DosGetTimeRegisters> rows(n);
        for (auto member : {&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
                &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
                &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
                &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip})
            for (auto& r : rows) r.*member=static_cast<uint16_t>(number(2));
        for (auto& r : rows) r.flags=number(4);
        return rows;
    }
};
Memory image(const std::vector<uint8_t>& raw) {
    Reader exe{raw};require(exe.number(2)==0x5a4d,"Motion MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<raw.size() && table+relocations*4<=header && raw.size()-header+0x10000<=1048576,"Motion MZ layout differs");
    Memory result;std::copy(raw.begin()+header,raw.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto value=exe.number(4),at=0x10000+(value>>16)*16+(value&65535);
        require(at+1<result.bytes.size(),"Motion relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(const DosGetTimeRegisters& actual,const DosGetTimeRegisters& expected,unsigned index,size_t row) {
    if (actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " flags=" << actual.flags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Motion register/all-flags trace differs");
    }
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};require(input.bytes.size()<=16*1024*1024,"Motion fixture exceeds reserve");
    for (char c : std::string("LZTRMO01")) require(input.number(1)==static_cast<uint8_t>(c),"Motion magic differs");
    const auto count=input.number(4),mzBytes=input.number(4);const auto mz=read(std::filesystem::path(root)/"LEZAC.EXE");
    require(count==132928 && mzBytes==mz.size() && input.at+mzBytes<=input.bytes.size(),"Motion corpus/MZ size differs");
    require(std::equal(mz.begin(),mz.end(),input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at)),"Motion canonical MZ bytes differ");
    input.at+=mzBytes;const auto base=image(mz);auto memory=base,expected=base;const auto bus=memory.bus();
    uint64_t replays=0,dispatches=0,comparisons=0,flagChecks=0,totalWrites=0;unsigned denseCases=0;
    uint32_t previousReturn=0;
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Motion case index differs");std::array<uint8_t,4> xy{};
        for (auto& byte : xy) byte=static_cast<uint8_t>(input.number(1));
        const auto width=input.number(2),offset=input.number(2),sp=input.number(2),ss=input.number(2),flags=input.number(4);
        const auto endpoint=input.registers();const std::array points{input.number(4),input.number(4)};
        const auto states=input.number(2);require(states==0 || (states>=2 && states<=32),"Motion dense trace reserve differs");
        const auto trace=input.trace(states);if (states) ++denseCases;
        const auto returnAddress=Memory::address(static_cast<uint16_t>(ss),static_cast<uint16_t>(sp));
        if (index) for (auto* m : {&memory,&expected}) {
            m->bytes[previousReturn]=base.bytes[previousReturn];
            m->bytes[(previousReturn+1u)&0xfffffu]=base.bytes[(previousReturn+1u)&0xfffffu];
        }
        const auto seed=[&](Memory& m) {
            std::copy(xy.begin(),xy.end(),m.bytes.begin()+0x1aa20+0x78d2);
            m.store(0x1aa20+0xc204,static_cast<uint16_t>(width));m.store(0x1aa20+0x2090,static_cast<uint16_t>(offset));
            m.store(returnAddress,0x4662);m.writes.clear();
        };
        seed(expected);const auto written=input.number(1);require(written>=2 && written<=4,"Motion write reserve differs");
        std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Motion write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        DosGetTimeRegisters entry{0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x4567,
            0x1000,0x1aa2,0x40,static_cast<uint16_t>(ss),static_cast<uint16_t>(sp),0x3eda,flags};
        for (uint64_t budget : {1u,7u,64u}) {
            seed(memory);TransientMotionOperation operation(entry,0x1000,0x200000);size_t cursor=0;uint64_t steps=0;unsigned pointMask=0;
            require(operation.advance(0,bus)==0 && memory.writes.empty(),"Zero motion budget changed state");
            if (states) {compare(operation.registers(),trace[0],index,0);++comparisons;}
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus);require(used>0 && used<=budget && (steps+=used)<=64,"Motion dispatch grant/reserve differs");
                operation=TransientMotionOperation(operation.snapshot());cursor+=used;const auto r=operation.registers();
                if (states) {require(cursor<trace.size(),"Motion dense trace exhausted");compare(r,trace[cursor],index,cursor);++comparisons;}
                if (budget==1 && (r.ip==0x3eed || r.ip==0x3f13)) {
                    const unsigned point=r.ip==0x3eed ? 0u : 1u;
                    require(r.flags==points[point],"Motion exhaustive addition flags differ");pointMask|=1u<<point;++flagChecks;
                }
            }
            require(operation.registers()==endpoint && (!states || cursor+1==trace.size()) && (budget!=1 || pointMask==3),"Motion endpoint/flag coverage differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Motion ordered writes/complete memory differ");
            const auto done=operation.snapshot();require(operation.advance(19,bus)==0 && operation.snapshot()==done,"Finished motion changed state");
            bool stopped=false;try {operation.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {stopped=true;}
            require(stopped,"Finished motion admitted IRQ");dispatches+=steps;++replays;
        }
        previousReturn=returnAddress;totalWrites+=written;
    }
    require(input.at==input.bytes.size(),"Motion fixture tail differs");
    std::cout << "transient_motion_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " dense_cases=" << denseCases << " addition_flag_checks=" << flagChecks
        << " full_memory=1 all_trace_flags=1 canonical_mz_bytes=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
Memory unitMemory(bool alternate) {
    Memory m;const std::array<uint8_t,4> xy=alternate ? std::array<uint8_t,4>{255,255,127,0} : std::array<uint8_t,4>{127,127,128,128};
    std::copy(xy.begin(),xy.end(),m.bytes.begin()+0x1aa20+0x78d2);m.store(0x1aa20+0xc204,16);m.store(0x1aa20+0x2090,65535);
    m.store(0x70000+0x3fe4,0x4662);return m;
}
void irqCheck(TransientMotionOperation operation,Memory memory) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.bytes[0x440]=2;
    const auto bus=memory.bus();const auto before=operation.registers();operation.deliverTimerInterrupt(bus);
    bool nested=false;try {operation.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {nested=true;}
    require(nested,"Motion nested IRQ accepted");unsigned steps=0;
    while (operation.interruptInProgress()) {
        require(steps++<4096,"Motion IRQ stalled");operation.advance(1,bus);operation=TransientMotionOperation(operation.snapshot());
    }
    require(operation.registers()==before && memory.word(0x40,0x6c)==101,"Motion IRQ did not restore CPU/clock");
    auto other=operation;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!operation.finished()) {require(steps++<4200,"Motion continuation stalled");operation.advance(1,bus);}
    while (!other.finished()) {require(steps++<4300,"Motion alternate stalled");other.advance(7,otherBus);other=TransientMotionOperation(other.snapshot());}
    require(operation.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,"Motion IRQ grant/snapshot continuation differs");
}
void unit() {
    unsigned rejected=0,entryRejected=0;std::set<uint16_t> reached;
    const auto reject=[&](TransientMotionSnapshot state) {
        bool failed=false;try {(void)TransientMotionOperation(state);} catch (const std::invalid_argument&) {failed=true;}
        require(failed,"Malformed motion state accepted");++rejected;
    };
    for (bool alternate : {false,true}) {
        DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x4567;r.ip=0x3eda;
        auto memory=unitMemory(alternate);const auto bus=memory.bus();TransientMotionOperation operation(r,0x1000,0x200000);
        while (!operation.finished()) {
            const auto good=operation.snapshot();(void)TransientMotionOperation(good);
            if (reached.insert(operation.registers().ip).second) {
                for (unsigned field=0;field<12;++field) {
                    auto bad=good;auto& cpu=bad.cpu;
                    if (field==0) ++cpu.registers.cs;
                    if (field==1) ++cpu.registers.ds;
                    if (field==2) ++cpu.registers.ss;
                    if (field==3) ++cpu.registers.sp;
                    if (field==4) ++cpu.registers.bp;
                    if (field==5) cpu.outcome=ActorFinishOutcome::Returned;
                    if (field==6) bad.outcome=static_cast<TransientMotionOutcome>(99);
                    if (field==7) cpu.timerInstructions=cpu.dispatchedInstructions+1;
                    if (field==8) cpu.timerDeliveries=cpu.timerInstructions+2;
                    if (field==9) cpu.transferredBytes=1;
                    if (field==10) cpu.registers.ip=0x3edb;
                    if (field==11) cpu.idToggleMask=1;
                    reject(bad);
                }
                irqCheck(operation,memory);
            }
            require(operation.advance(1,bus)==1,"Unit motion stalled");operation=TransientMotionOperation(operation.snapshot());
        }
    }
    require(reached.size()==27 && rejected==324,"Motion instruction coverage differs");
    DosGetTimeRegisters entry;entry.cs=0x1000;entry.ds=0x1aa2;entry.ss=0x7000;
    entry.sp=0x3fe4;entry.bp=0x4567;entry.ip=0x3eda;entry.flags=2;
    for (unsigned field=0;field<4;++field) {
        auto bad=entry;if (field==0) ++bad.cs;if (field==1) ++bad.ds;if (field==2) ++bad.ip;
        bool failed=false;try {(void)TransientMotionOperation(bad,0x1000,field==3 ? 1 : 0);}
        catch (const std::invalid_argument&) {failed=true;}
        require(failed,"Malformed motion entry accepted");++entryRejected;
    }
    auto memory=unitMemory(false);TransientMotionOperation masked(entry,0x1000,0);
    bool denied=false;try {masked.deliverTimerInterrupt(memory.bus());} catch (const std::logic_error&) {denied=true;}
    require(denied && memory.writes.empty(),"Masked motion IRQ changed memory");
    std::cout << "transient_motion_unit=ok state_rejections=" << rejected << " boundaries=" << reached.size()
        << " computed_irq_cases=" << reached.size() << " entry_rejections=" << entryRejected << " masked_irq=1\n";
}
}
int main(int argc,char** argv) {
    try {if (argc==1) unit();else {require(argc==3,"Use motion fixture and repository root");replay(argv[1],argv[2]);}}
    catch (const std::exception& error) {std::cerr << "transient_motion_error=" << error.what() << '\n';return 1;}
}
