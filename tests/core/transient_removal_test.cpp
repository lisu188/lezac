#include "core/transient_removal.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
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
            [](uint16_t p)->uint8_t { require(p==0x61,"Unexpected removal IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected removal IRQ output"); }
        };
    }
};
std::vector<uint8_t> read(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing removal input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated removal fixture");
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
    Reader exe{raw};require(exe.number(2)==0x5a4d,"Removal MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<raw.size() && table+relocations*4<=header && raw.size()-header+0x10000<=1048576,"Removal MZ layout differs");
    Memory result;std::copy(raw.begin()+header,raw.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto value=exe.number(4),at=0x10000+(value>>16)*16+(value&65535);
        require(at+1<result.bytes.size(),"Removal relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row) {
    const bool flags=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;actual.flags=expected.flags;
    if (!flags || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " sp=" << actual.sp << '/' << expected.sp << " bp=" << actual.bp << '/' << expected.bp << std::dec << '\n';
        throw std::runtime_error("Removal register/control trace differs");
    }
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};require(input.bytes.size()<=16*1024*1024,"Removal fixture exceeds reserve");
    for (char c : std::string("LZTRRM01")) require(input.number(1)==static_cast<uint8_t>(c),"Removal magic differs");
    const auto count=input.number(4),mzBytes=input.number(4);const auto mz=read(std::filesystem::path(root)/"LEZAC.EXE");
    require(count>0 && count<1000 && mzBytes==mz.size() && input.at+mzBytes<=input.bytes.size(),"Removal corpus/MZ size differs");
    require(std::equal(mz.begin(),mz.end(),input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at)),"Removal canonical MZ bytes differ");
    input.at+=mzBytes;const auto base=image(mz);uint64_t comparisons=0,dispatches=0,writtenTotal=0,replays=0;
    std::array<unsigned,2> kinds{},outcomes{};unsigned sparse=0;
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Removal case index differs");const auto kind=input.number(4),outcome=input.number(4);
        require(kind<2 && outcome<2,"Removal kind/outcome differs");++kinds[kind];++outcomes[outcome];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
        require(seeds<64,"Removal seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Removal seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>=2 && states<=10001,"Removal trace reserve differs");
        const auto trace=input.trace(states);const auto written=input.number(4);require(written<200000,"Removal write reserve differs");
        auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Removal write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        const bool endpointOnly=trace.size()==2;if (endpointOnly) ++sparse;
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();TransientRemovalOperation operation(entry,0x1000,0x200000);
            require(static_cast<unsigned>(operation.snapshot().kind)==kind,"Removal entry kind differs");
            require(operation.advance(0,bus,[](uint16_t n) { return n; })==0 && memory.writes.empty(),"Zero removal budget changed state");
            size_t cursor=0;uint64_t steps=0;compare(operation.registers(),trace[0],index,0);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus,[=](uint16_t n) { return std::min(n,limit); });
                require(used>0 && used<=budget && (steps+=used)<400000,"Removal dispatch grant/reserve differs");
                operation=TransientRemovalOperation(operation.snapshot());
                if (endpointOnly) continue;
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Removal exceeded original endpoint");const auto before=trace[cursor];
                    if (before.cs==0x1000 && (before.ip==0x456b || before.ip==0x45ce) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Removal REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                require(cursor<trace.size(),"Removal trace exhausted");compare(operation.registers(),trace[cursor],index,cursor);++comparisons;
            }
            require((endpointOnly || cursor+1==trace.size()) && operation.registers()==endpoint,"Removal endpoint/all flags differ");
            require(operation.snapshot().outcome==(outcome ? TransientRemovalOutcome::RuntimeError : TransientRemovalOutcome::Returned),"Removal outcome differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Removal ordered writes/complete memory differ");
            const auto done=operation.snapshot();require(operation.advance(19,bus,[](uint16_t n) { return n; })==0 && operation.snapshot()==done,"Finished removal changed state");
            bool stopped=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { stopped=true; }
            require(stopped,"Finished removal admitted IRQ");dispatches+=steps;++replays;
        }
        writtenTotal+=writes.size();
    }
    require(input.at==input.bytes.size() && kinds[0] && kinds[1] && outcomes[0] && outcomes[1],"Removal coverage/tail differs");
    std::cout << "transient_removal_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << writtenTotal << " endpoint_only_long_cases=" << sparse
        << " full_memory=1 canonical_mz_bytes=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
Memory unitMemory(bool debris) {
    Memory m;for (unsigned i=0;i<2600;++i) m.bytes[0x1aa20+0x209eu+i]=static_cast<uint8_t>(i*29+7);
    m.store(0x1aa20+0x2076,4);m.store(0x1aa20+0x207e,204);m.store(0x1aa20+0x207c,0x209e);
    m.store(0x70000+0x3fe4,debris ? 0x4a3c : 0x4929);m.store(0x70000+0x3fe6,0x4000);
    m.store(0x70000+0x3fe8,debris ? 201 : 2);m.store(0x70000+0x3ffe,203);return m;
}
void irqCheck(TransientRemovalOperation operation,Memory memory,bool partial) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.bytes[0x440]=2;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    if (partial) {
        const auto before=operation.registers();const auto writes=memory.writes.size();
        operation.advance(1,bus,[](uint16_t) { return uint16_t{1}; });
        require(operation.registers().ip==before.ip && operation.registers().cx==before.cx-1 && memory.writes.size()==writes+1,"Removal partial copy differs");
    }
    const auto before=operation.registers();operation.deliverTimerInterrupt(bus);
    bool nested=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested,"Removal nested IRQ accepted");unsigned steps=0;
    while (operation.interruptInProgress()) {
        require(steps++<4096,"Removal IRQ stalled");operation.advance(1,bus,all);operation=TransientRemovalOperation(operation.snapshot());
    }
    require(operation.registers()==before && memory.word(0x40,0x6c)==101,"Removal IRQ did not restore CPU/clock");
    auto other=operation;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!operation.finished()) { require(steps++<400000,"Removal continuation stalled");operation.advance(1,bus,all); }
    while (!other.finished()) { require(steps++<800000,"Removal alternate stalled");other.advance(17,otherBus,all);other=TransientRemovalOperation(other.snapshot()); }
    require(operation.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,"Removal IRQ grant/snapshot continuation differs");
}
void unit() {
    unsigned rejected=0,boundaries=0,irqs=0;
    const auto reject=[&](const TransientRemovalSnapshot& state) {
        bool failed=false;try { (void)TransientRemovalOperation(state); } catch (const std::invalid_argument&) { failed=true; }
        require(failed,"Malformed removal state accepted");++rejected;
    };
    for (bool debris : {false,true}) {
        DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x4567;r.ip=debris ? 0x458d : 0x452a;
        auto memory=unitMemory(debris);const auto bus=memory.bus();TransientRemovalOperation operation(r,0x1000,0x200000);
        while (!operation.finished()) {
            const auto good=operation.snapshot();(void)TransientRemovalOperation(good);++boundaries;
            for (unsigned field=0;field<10;++field) {
                auto bad=good;auto& cpu=bad.cpu;
                if (field==0) ++cpu.registers.ss;
                if (field==1) ++cpu.registers.sp;
                if (field==2) ++cpu.registers.bp;
                if (field==3) ++cpu.registers.ds;
                if (field==4) bad.kind=static_cast<TransientRemovalKind>(99);
                if (field==5) bad.outcome=static_cast<TransientRemovalOutcome>(99);
                if (field==6) cpu.outcome=ActorFinishOutcome::Returned;
                if (field==7) cpu.timerInstructions=cpu.dispatchedInstructions+1;
                if (field==8) cpu.timerDeliveries=cpu.timerInstructions+2;
                if (field==9) {cpu.registers.cs=0x1000;cpu.registers.ip=0;}
                reject(bad);
            }
            const auto pc=operation.registers();const bool rep=pc.ip==0x456b || pc.ip==0x45ce;
            if (pc.ip==(debris ? 0x458d : 0x452a) || pc.ip==(debris ? 0x4592 : 0x452f) ||
                (pc.cs==0x1920 && pc.ip==0x4df) || rep || pc.ip==(debris ? 0x45f6 : 0x4589)) {
                irqCheck(operation,memory,rep);++irqs;
            }
            if (rep) {
                auto copy=operation;auto m=memory;const auto b=m.bus();const auto before=copy.registers();const auto writes=m.writes.size();
                require(copy.advance(1,b,[](uint16_t) { return uint16_t{0}; })==1 && copy.registers()==before && m.writes.size()==writes,"Zero removal copy changed state");
                bool failed=false;try { copy.advance(1,b,[](uint16_t n) { return static_cast<uint16_t>(n+1u); }); } catch (const std::domain_error&) { failed=true; }
                require(failed && copy.registers()==before && m.writes.size()==writes,"Oversized removal copy accepted");
            }
            require(operation.advance(1,bus,[](uint16_t n) { return n; })==1,"Unit removal stalled");
            operation=TransientRemovalOperation(operation.snapshot());
        }
    }
    require(irqs==10,"Removal IRQ coverage differs");
    std::cout << "transient_removal_unit=ok state_rejections=" << rejected << " boundaries=" << boundaries << " computed_irq_cases=" << irqs
        << " partial_copy_irqs=2 copy_grant_controls=4\n";
}
}
int main(int argc,char** argv) {
    try { if (argc==1) unit();else { require(argc==3,"Use removal fixture and repository root");replay(argv[1],argv[2]); } }
    catch (const std::exception& error) { std::cerr << "transient_removal_error=" << error.what() << '\n';return 1; }
}
