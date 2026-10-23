#include "core/frame_tail.hpp"
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
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
uint64_t fingerprint(const std::vector<uint8_t>& bytes) {
    uint64_t result=14695981039346656037ull;
    for (const auto b:bytes) { result^=b;result*=1099511628211ull; }return result;
}
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    Reader(const std::filesystem::path& path,size_t size,uint64_t hash) {
        require(std::filesystem::file_size(path)==size,"Tail input size differs");
        std::ifstream input(path,std::ios::binary);
        bytes={std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
        require(bytes.size()==size && fingerprint(bytes)==hash,"Tail input fingerprint differs");
    }
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Tail input truncated");
        uint32_t v=0;for (unsigned i=0;i<n;++i) v|=uint32_t{bytes[at++]}<<(i*8);return v;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (const auto member:members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace() {
        const auto n=number(4);require(n>1 && n<500000,"Tail trace count differs");
        std::vector<DosGetTimeRegisters> rows;rows.reserve(n);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<n;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i || mask==0x3fff),"Tail trace mask differs");
            for (unsigned j=0;j<members.size();++j)
                if (mask&(1u<<j)) previous.*members[j]=static_cast<uint16_t>(number(2));
            if (mask&0x2000u) previous.flags=number(4);
            rows.push_back(previous);
        }
        return rows;
    }
};
struct Write {
    uint32_t address;uint8_t size;uint32_t value;
    bool operator==(const Write&) const = default;
};
struct Port {
    uint16_t port;uint8_t size;uint32_t value;
    bool operator==(const Port&) const = default;
};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<Write> writes;std::vector<Port> ports;
    static uint32_t address(uint16_t s,uint16_t o) { return (uint32_t{s}*16+o)&0xfffffu; }
    uint32_t load(uint32_t a,unsigned size) const {
        uint32_t value=0;
        for (unsigned i=0;i<size;++i) value|=uint32_t{bytes[(a+i)&0xfffffu]}<<(i*8);
        return value;
    }
    void store(uint32_t a,uint32_t value,unsigned size) {
        for (unsigned i=0;i<size;++i) bytes[(a+i)&0xfffffu]=static_cast<uint8_t>(value>>(i*8));
    }
    TimerIrqBus bus() {
        return {
            [this](uint16_t s,uint16_t o) { return static_cast<uint8_t>(load(address(s,o),1)); },
            [this](uint16_t s,uint16_t o) { return static_cast<uint16_t>(load(address(s,o),2)); },
            [this](uint16_t s,uint16_t o) { return load(address(s,o),4); },
            [this](uint16_t s,uint16_t o,uint8_t v) { const auto a=address(s,o);store(a,v,1);writes.push_back({a,1,v}); },
            [this](uint16_t s,uint16_t o,uint16_t v) { const auto a=address(s,o);store(a,v,2);writes.push_back({a,2,v}); },
            [this](uint16_t s,uint16_t o,uint32_t v) { const auto a=address(s,o);store(a,v,4);writes.push_back({a,4,v}); },
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected tail input");return 0; },
            [this](uint16_t p,uint8_t v) {
                require(p==0x3c8 || p==0x3c9 || p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected tail output");
                ports.push_back({p,1,v});
            }
        };
    }
};
uint64_t stateRejections=0;
void reject(FrameTailSnapshot state,const char* message="Tail admitted invalid snapshot") {
    bool rejected=false;
    try { FrameTailOperation operation(std::move(state));(void)operation; }
    catch (const std::invalid_argument&) { rejected=true; }
    require(rejected,message);
    ++stateRejections;
}
void timerPhaseControls(const DosGetTimeRegisters& entry) {
    struct Profile { uint8_t latch;uint16_t sequence;uint8_t period,cutoff;uint16_t frequency; };
    constexpr std::array<Profile,9> profiles{{
        {0,0,1,1,440},{1,0xea61,1,1,440},{1,0xea65,1,1,440},
        {1,0,1,1,0x7530},{1,0,1,1,440},{1,0,1,1,1},
        {1,0,2,1,440},{1,0,2,2,440},{1,0,1,1,0}
    }};
    std::vector<std::pair<uint16_t,uint16_t>> seen;
    for (const auto profile:profiles) for (const uint8_t speaker:{uint8_t{0},uint8_t{3}}) {
        Memory memory;
        memory.store(0x70,0xfbe,2);memory.store(0x72,0x1000,2);
        memory.store(0x46c,100,4);memory.store(0x440,2,1);memory.store(0x43f,0xa5,1);
        memory.store(0x1aa20+0x79c4,profile.latch,1);
        memory.store(0x1aa20+0x78c0,profile.sequence,2);
        memory.store(0x1aa20+0x79a2,profile.period,1);
        memory.store(0x1aa20+0x79a1,profile.cutoff,1);
        memory.store(0x1aa20+0x79c0,0,2);memory.store(0x1aa20+0x79c2,0x4000,2);
        memory.store(0x40000,profile.frequency,2);memory.store(0x40002,1,1);memory.store(0x40003,3,1);
        auto bus=memory.bus();
        bus.inByte=[=](uint16_t port) { require(port==0x61,"IRQ phase input differs");return speaker; };
        FrameTailOperation active(entry,0x1000,0x200000);
        active.deliverTimerInterrupt(bus);
        unsigned steps=0;
        while (active.interruptInProgress()) {
            const auto state=active.snapshot();
            const auto& timer=*state.timer;
            const std::pair pc{timer.registers.cs,timer.registers.ip};
            if (std::find(seen.begin(),seen.end(),pc)==seen.end()) {
                seen.push_back(pc);
                auto bad=state;bad.timer->registers.ip=0xffff;reject(bad);
                bad=state;++bad.timer->registers.sp;reject(bad);
                bad=state;++bad.timer->registers.bp;reject(bad);
                bad=state;bad.timer->registers.flags|=0x200u;reject(bad);
                bad=state;bad.timer->definedFlags|=0x80000000u;reject(bad);
                bad=state;++bad.registers.ss;reject(bad,"Tail admitted foreign foreground SS during IRQ");
                bad=state;++bad.timer->registers.ss;reject(bad,"Tail admitted foreign live IRQ SS");
                bad=state;++bad.timer->registers.ds;reject(bad,"Tail admitted foreign IRQ DS");
                if (timer.dispatchedInstructions) {
                    bad=state;bad.timer->dispatchedInstructions=0;reject(bad);
                }
            }
            require(steps++<128,"IRQ phase profile stalled");
            require(active.advance(1,bus)==1,"IRQ phase did not dispatch");
            active=FrameTailOperation(active.snapshot());
        }
        require(active.registers()==entry && active.snapshot().timerInstructions==steps &&
            active.snapshot().timerDeliveries==1 && memory.load(0x46c,4)==101 &&
            memory.load(0x440,1)==1 && memory.load(0x43f,1)==0xa0 &&
            std::count_if(memory.ports.begin(),memory.ports.end(),[](const Port& port) {
                return port.port==0x20 && port.value==0x20;
            })==1,"IRQ phase completion differs");
        auto incomplete=active.snapshot();incomplete.timerInstructions=1;reject(incomplete);
    }
    if (seen.size()!=110) {
        std::cerr<<"irq_phase_pcs="<<seen.size()<<'\n';
        for (const auto& [cs,ip]:seen) std::cerr<<std::hex<<cs<<':'<<ip<<' ';
        std::cerr<<std::dec<<'\n';
    }
    require(seen.size()==110,"IRQ phase instruction coverage differs");
}
void completedTimerControls(const FrameTailSnapshot& foreground) {
    Memory memory;const auto bus=memory.bus();
    FrameTailOperation interrupted(foreground);interrupted.deliverTimerInterrupt(bus);
    auto phantom=interrupted.snapshot();phantom.timerInstructions=1;
    reject(phantom,"Tail admitted active IRQ work without a completed delivery");
    constexpr std::array<uint64_t,12> lengths{36,44,49,52,58,61,65,67,71,73,82,86};
    std::vector<uint64_t> sums{0};
    for (uint64_t count=0;count<=3;++count) {
        for (uint64_t work=0;work<=count*86u+1u;++work) {
            auto state=foreground;state.timerDeliveries=count;state.timerInstructions=work;
            state.dispatchedInstructions=work+1u;
            if (std::find(sums.begin(),sums.end(),work)!=sums.end()) (void)FrameTailOperation(state);
            else reject(state,"Tail admitted impossible completed IRQ work");
        }
        std::vector<uint64_t> next;
        for (const auto sum:sums) for (const auto length:lengths) next.push_back(sum+length);
        std::sort(next.begin(),next.end());next.erase(std::unique(next.begin(),next.end()),next.end());
        sums=std::move(next);
    }
    constexpr uint64_t large=uint64_t{1}<<50;
    for (const uint64_t work:{36u*large,36u*large+13u,86u*large}) {
        auto state=foreground;state.timerDeliveries=large;state.timerInstructions=work;
        state.dispatchedInstructions=work+1u;(void)FrameTailOperation(state);
    }
    for (const uint64_t work:{36u*large+1u,86u*large-1u,86u*large+1u}) {
        auto state=foreground;state.timerDeliveries=large;state.timerInstructions=work;
        state.dispatchedInstructions=work+1u;reject(state,"Tail admitted a large completed IRQ work hole");
    }
    auto overflow=foreground;overflow.timerDeliveries=uint64_t{1}<<62;
    overflow.timerInstructions=overflow.timerDeliveries;overflow.dispatchedInstructions=overflow.timerInstructions+1;
    reject(overflow,"Tail admitted overflowing completed IRQ work");
}
void unit() {
    Memory memory;
    DosGetTimeRegisters r;
    r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3ffe;r.ip=0x806a;
    const auto bus=memory.bus();
    FrameTailOperation initial(r,0x1000,0x200000);
    const auto valid=initial.snapshot();
    const auto faults=std::array{
        +[](FrameTailSnapshot& s) { s.idToggleMask=1; },
        +[](FrameTailSnapshot& s) { ++s.gameSegment; },
        +[](FrameTailSnapshot& s) { ++s.callerSs; },
        +[](FrameTailSnapshot& s) { ++s.callerSp; },
        +[](FrameTailSnapshot& s) { ++s.callerBp; },
        +[](FrameTailSnapshot& s) { ++s.registers.ss; },
        +[](FrameTailSnapshot& s) { ++s.registers.cs; },
        +[](FrameTailSnapshot& s) { ++s.registers.ds; },
        +[](FrameTailSnapshot& s) { s.registers.ip=0x370e; },
        +[](FrameTailSnapshot& s) { s.registers.ip=0x3f27; },
        +[](FrameTailSnapshot& s) { ++s.registers.sp; },
        +[](FrameTailSnapshot& s) { ++s.registers.bp; },
        +[](FrameTailSnapshot& s) { s.outcome=static_cast<FrameTailOutcome>(255); },
        +[](FrameTailSnapshot& s) { s.outcome=FrameTailOutcome::NextFrame; },
        +[](FrameTailSnapshot& s) { s.outcome=FrameTailOutcome::RuntimeError; },
        +[](FrameTailSnapshot& s) { s.timerInstructions=1; },
        +[](FrameTailSnapshot& s) { s.tileCalls=2; },
        +[](FrameTailSnapshot& s) { s.tileReturns=1; },
        +[](FrameTailSnapshot& s) { s.tileCallback=true; },
        +[](FrameTailSnapshot& s) { s.tileWriter=true; },
        +[](FrameTailSnapshot& s) { s.rngReturn=FrameTailReturn{}; },
        +[](FrameTailSnapshot& s) { s.stackReturn=FrameTailReturn{}; },
        +[](FrameTailSnapshot& s) { s.registers.cs=0x1920;s.registers.ip=0x13a8; },
        +[](FrameTailSnapshot& s) { s.registers.cs=0x1920;s.registers.ip=0x4df; },
        +[](FrameTailSnapshot& s) { s.registers.cs=0x18ac;s.registers.ip=0; },
        +[](FrameTailSnapshot& s) { s.outcome=FrameTailOutcome::NextFrame;s.registers.ip=0x7903; }
    };
    for (const auto fault:faults) { auto state=valid;fault(state);reject(state); }
    require(memory.writes.empty() && memory.ports.empty(),"Tail constructor controls touched bus");
    require(initial.advance(0,bus)==0 && initial.snapshot()==valid,"Tail zero budget changed state");
    bool badEntry=false;
    try { auto wrong=r;wrong.ip=0x806b;FrameTailOperation operation(wrong,0x1000,0x200000); }
    catch (const std::invalid_argument&) { badEntry=true; }
    require(badEntry,"Tail admitted wrong entry");
    auto masked=r;masked.flags&=~uint32_t{0x200};
    FrameTailOperation noIrq(masked,0x1000,0x200000);
    bool blocked=false;
    try { noIrq.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked && memory.writes.empty(),"Tail admitted masked IRQ");
    initial.deliverTimerInterrupt(bus);
    const auto interrupted=initial.snapshot();
    auto skippedIrq=interrupted;skippedIrq.timer->registers.ip=0xfeb6;reject(skippedIrq);
    const auto irqFaults=std::array{
        +[](FrameTailSnapshot& s) { s.timer.reset(); },
        +[](FrameTailSnapshot& s) { ++s.registers.ss; },
        +[](FrameTailSnapshot& s) { ++s.timer->registers.ss; },
        +[](FrameTailSnapshot& s) { ++s.timer->gameSegment; },
        +[](FrameTailSnapshot& s) { ++s.timer->dataSegment; },
        +[](FrameTailSnapshot& s) { ++s.timer->crtSegment; },
        +[](FrameTailSnapshot& s) { ++s.timer->biosSegment; },
        +[](FrameTailSnapshot& s) { ++s.timer->biosEntry; },
        +[](FrameTailSnapshot& s) { s.timer->registers.cs=0x2000; },
        +[](FrameTailSnapshot& s) { s.timer->idToggleMask=1; },
        +[](FrameTailSnapshot& s) { s.timer->returned=true; },
        +[](FrameTailSnapshot& s) { s.timer->biosWrapper=false; },
        +[](FrameTailSnapshot& s) { s.timerDeliveries=0; },
        +[](FrameTailSnapshot& s) { s.timer->dispatchedInstructions=1; }
    };
    for (const auto fault:irqFaults) { auto state=interrupted;fault(state);reject(state); }
    const auto writes=memory.writes.size();
    blocked=false;
    try { initial.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked && memory.writes.size()==writes && initial.snapshot()==interrupted,"Tail admitted nested IRQ");
    auto wrongDivide=valid;wrongDivide.registers.ip=0x81d5;
    wrongDivide.outcome=FrameTailOutcome::DivideError;wrongDivide.dispatchedInstructions=1;
    wrongDivide.registers.cx=5;reject(wrongDivide);
    auto synthetic=valid;synthetic.registers.ip=0x81d5;synthetic.dispatchedInstructions=1;
    synthetic.registers.cx=0;
    FrameTailOperation divide(synthetic);
    require(divide.advance(1,bus)==1 && divide.snapshot().outcome==FrameTailOutcome::DivideError,
        "Tail divide boundary differs");
    Memory quiet;
    quiet.store(Memory::address(r.ds,0x78c2),1,2);
    const auto quietBus=quiet.bus();
    FrameTailOperation foreground(r,0x1000,0x200000);
    require(foreground.advance(1,quietBus)==1,"Tail foreground control did not dispatch");
    auto operandPc=foreground.snapshot();operandPc.registers.ip=0x806b;reject(operandPc);
    completedTimerControls(foreground.snapshot());
    auto inventedTimer=foreground.snapshot();inventedTimer.timerInstructions=1;reject(inventedTimer);
    FrameTailOperation ended(r,0x1000,0x200000);
    ended.advance(4096,quietBus);
    require(ended.snapshot().outcome==FrameTailOutcome::NextFrame,"Tail unit did not finish");
    const auto terminal=ended.snapshot();
    inventedTimer=terminal;inventedTimer.timerInstructions=1;reject(inventedTimer);
    require(ended.advance(1,quietBus)==0 && ended.snapshot()==terminal,"Terminal tail dispatched");
    blocked=false;
    try { ended.deliverTimerInterrupt(quietBus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked,"Terminal tail admitted IRQ");
    timerPhaseControls(r);
    std::cout<<"frame_tail_unit=ok state_rejections="<<stateRejections
        <<" entry_rejection=1 masked_irq=1 nested_irq=1 zero_budget=1 terminal_no_work=1 divide_control=1\n";
}
Memory image(const char* root) {
    Reader exe(std::filesystem::path(root)/"LEZAC.EXE",52384,0x2ae32f89b95e200bull);
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header,"Tail MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);
    exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto pair=exe.number(4),address=0x10000+(pair>>16)*16+(pair&65535);
        require(address+1<result.bytes.size(),"Tail MZ relocation extent differs");
        result.store(address,(result.load(address,2)+0x1000)&65535,2);
    }
    return result;
}
void compare(DosGetTimeRegisters actual,const DosGetTimeRegisters& expected,unsigned index,size_t row,bool end) {
    const bool defined=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    if (!end) actual.flags=expected.flags;
    if (!defined || actual!=expected) {
        std::cerr<<"case="<<index<<" row="<<row<<" actual="<<std::hex<<actual.cs<<':'<<actual.ip
            <<" expected="<<expected.cs<<':'<<expected.ip<<std::dec<<'\n';
        for (const auto member:members) std::cerr<<std::hex<<(actual.*member)<<'/'<<(expected.*member)<<' ';
        std::cerr<<"flags="<<actual.flags<<'/'<<expected.flags<<std::dec<<'\n';
        throw std::runtime_error("Tail registers/control differ");
    }
}
void rejectReturnFrames(const FrameTailOperation& active,const Memory& memory) {
    const auto r=active.registers();const auto state=active.snapshot();
    const bool far=(r.cs==0x1920 && (r.ip==0x13bb || r.ip==0x4f0)) || r.cs==0x18ac;
    for (const auto ip:{uint16_t{0x7903},uint16_t{0xe2},uint16_t{0xffff}}) {
        auto badMemory=memory;
        badMemory.store(Memory::address(r.ss,r.sp),ip,2);
        if (far) badMemory.store(Memory::address(r.ss,static_cast<uint16_t>(r.sp+2u)),
            ip==0xe2 ? 0x1920 : 0x1000,2);
        const auto bus=badMemory.bus();auto bad=active;bool rejected=false;
        try { bad.advance(1,bus); } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected && bad.snapshot().outcome==FrameTailOutcome::Running &&
            bad.snapshot().dispatchedInstructions==state.dispatchedInstructions+1 &&
            badMemory.writes==memory.writes && badMemory.ports==memory.ports,"Tail spoofed return escaped");
    }
}
uint64_t irqCheck(FrameTailOperation active,Memory memory) {
    memory.store(0x70,0xfbe,2);memory.store(0x72,0x1000,2);memory.store(0x46c,100,2);memory.store(0x46e,0,2);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto before=active.registers();const auto saved=active.snapshot();
    active.deliverTimerInterrupt(bus);unsigned steps=0;
    while (active.interruptInProgress()) {
        require(steps++<4096,"Tail IRQ stalled");
        require(active.advance(1,bus)==1,"Tail IRQ did not dispatch");
        active=FrameTailOperation(active.snapshot());
    }
    const auto instructions=active.snapshot().timerInstructions-saved.timerInstructions;
    require(instructions==36 && active.registers()==before &&
        memory.load(0x46c,2)==101 && active.snapshot().timerDeliveries==saved.timerDeliveries+1,
        "Tail IRQ CPU/tick restoration differs");
    auto other=active;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!active.finished()) {
        require(steps++<500000,"Tail IRQ continuation stalled");active.advance(1,bus);
        active=FrameTailOperation(active.snapshot());
    }
    while (!other.finished()) {
        require(steps++<1000000,"Tail alternate IRQ continuation stalled");other.advance(17,otherBus);
        other=FrameTailOperation(other.snapshot());
    }
    require(active.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes &&
        memory.writes==otherMemory.writes && memory.ports==otherMemory.ports,"Tail IRQ grant/restore differs");
    return instructions;
}
void replay(const char* path,const char* root) {
    Reader input(path,14476040,0xae915f1426e12eecull);
    for (const char c:std::string("LZTAIL01")) require(input.number(1)==static_cast<uint8_t>(c),"Tail magic differs");
    const auto count=input.number(4);require(count==2576,"Tail domain differs");
    const auto base=image(root);
    constexpr std::array outcomes{FrameTailOutcome::NextFrame,FrameTailOutcome::Completion,
        FrameTailOutcome::Escape,FrameTailOutcome::RuntimeError,FrameTailOutcome::ViewChange};
    uint64_t replays=0,comparisons=0,dispatches=0,written=0,ports=0;
    const auto previousRejections=stateRejections;
    std::array<bool,6> ownershipSeen{};
    std::array<bool,5> stackSeen{};
    std::array<bool,11> returnSeen{},irqSeen{};
    uint64_t irqInstructions=0;
    struct Target { uint16_t cs,ip;unsigned kind; };
    constexpr std::array<Target,11> targets{{
        {0x1000,0x806a,0},{0x1000,0x81ca,0},{0x1000,0x3f27,1},{0x1000,0x370e,2},
        {0x1920,0x13a8,0},{0x1920,0x13a8,1},{0x1920,0x4df,0},{0x1920,0x4df,1},
        {0x1920,0x4df,2},{0x18ac,0,0},{0x1000,0x7aa,0}
    }};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Tail order differs");
        const auto outcome=input.number(1);require(outcome<outcomes.size(),"Tail outcome differs");
        const auto entry=input.registers(),endpoint=input.registers();
        auto initial=base;const auto seeds=input.number(4);require(seeds<100,"Tail seed domain differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto a=input.number(4),n=input.number(4);
            require(a>=0x1aa20 && a+n<=1048576 && n<=65536 && input.at+n<=input.bytes.size(),"Tail seed extent differs");
            std::copy_n(input.bytes.begin()+input.at,n,initial.bytes.begin()+a);input.at+=n;
        }
        const auto trace=input.trace();compare(trace.front(),entry,index,0,true);compare(trace.back(),endpoint,index,trace.size()-1,true);
        const auto n=input.number(4);require(n<500000,"Tail write count differs");
        std::vector<Write> writes;auto expected=initial;
        for (unsigned i=0;i<n;++i) {
            const Write item{input.number(4),static_cast<uint8_t>(input.number(1)),input.number(4)};
            require((item.size==1 || item.size==2 || item.size==4) && item.address+item.size<=1048576,"Tail write extent differs");
            writes.push_back(item);expected.store(item.address,item.value,item.size);
        }
        const auto pn=input.number(4);require(pn<500000,"Tail port count differs");
        std::vector<Port> expectedPorts;
        for (unsigned i=0;i<pn;++i) expectedPorts.push_back({static_cast<uint16_t>(input.number(2)),
            static_cast<uint8_t>(input.number(1)),input.number(4)});
        for (const uint64_t budget:{1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();
            FrameTailOperation active(entry,0x1000,0x200000);size_t cursor=0;
            while (!active.finished()) {
                if (budget==1) {
                    const auto state=active.snapshot();const auto r=active.registers();
                    const unsigned kind=state.tileWriter ? 2u : state.tileCallback ? 1u : 0u;
                    constexpr std::array<std::array<uint16_t,2>,5> stackSites{{
                        {0x1000,0x806f},{0x1000,0x79d},{0x18ac,0},{0x1000,0x3f27},{0x1000,0x370e}
                    }};
                    for (size_t site=0;site<stackSites.size();++site)
                        if (!stackSeen[site] && r.cs==stackSites[site][0] && r.ip==stackSites[site][1]) {
                            stackSeen[site]=true;
                            auto invalid=state;++invalid.registers.sp;reject(invalid);
                            invalid=state;++invalid.registers.bp;reject(invalid);
                            invalid=state;++invalid.callerSp;reject(invalid);
                            invalid=state;invalid.timerInstructions=1;reject(invalid);
                            invalid=state;
                            if (site==0) invalid.registers.ip=0x806b;
                            if (site==1) invalid.registers.ip=0x79e;
                            if (site==2) {
                                invalid.registers.ip=2;
                                invalid.registers.sp=static_cast<uint16_t>(state.callerSp-14u);
                                invalid.registers.bp=invalid.registers.sp;
                            }
                            if (site==3 || site==4) {
                                invalid.registers.ip=site==3 ? 0x3f29 : 0x3710;
                                invalid.registers.sp=static_cast<uint16_t>(state.callerSp-(site==3 ? 6u : 20u));
                                invalid.registers.bp=static_cast<uint16_t>(state.callerSp-(site==3 ? 4u : 20u));
                            }
                            reject(invalid);
                        }
                    int owner=-1;
                    if (state.rngReturn) owner=state.rngReturn->ip==0x807c ? 0 : state.rngReturn->ip==0x3f3e ? 1 : 2;
                    if (state.stackReturn) owner=3+static_cast<int>(kind);
                    if (owner>=0 && !ownershipSeen[static_cast<size_t>(owner)]) {
                        ownershipSeen[static_cast<size_t>(owner)]=true;
                        for (unsigned fault=0;fault<9;++fault) {
                            auto invalid=state;
                            auto& context=invalid.rngReturn ? invalid.rngReturn : invalid.stackReturn;
                            if (fault==0) context.reset();
                            if (fault==1) ++context->cs;
                            if (fault==2) ++context->ip;
                            if (fault==3) ++context->sp;
                            if (fault==4) ++context->bp;
                            if (fault==5) ++invalid.registers.sp;
                            if (fault==6) ++invalid.registers.bp;
                            if (fault==7) ++invalid.callerSp;
                            if (fault==8) invalid.tileCallback=!invalid.tileCallback;
                            reject(invalid);
                        }
                        auto invalid=state;invalid.registers.ip=state.rngReturn ? 0x13a9 : 0x4e0;
                        reject(invalid);
                    }
                    int site=-1;
                    if (r.cs==0x1920 && r.ip==0x13bb) site=owner;
                    if (r.cs==0x1920 && r.ip==0x142c) site=3;
                    if (r.cs==0x1920 && r.ip==0x4f0) site=4+static_cast<int>(kind);
                    if (r.cs==0x18ac && r.ip==31) site=7;
                    if (r.cs==0x1000 && r.ip==0x7c4) site=8;
                    if (r.cs==0x1000 && r.ip==0x3a53) site=9;
                    if (r.cs==0x1000 && r.ip==0x3fa5) site=10;
                    if (site>=0 && !returnSeen[static_cast<size_t>(site)]) {
                        returnSeen[static_cast<size_t>(site)]=true;rejectReturnFrames(active,memory);
                    }
                    for (size_t target=0;target<targets.size();++target)
                        if (!irqSeen[target] && r.cs==targets[target].cs && r.ip==targets[target].ip &&
                            kind==targets[target].kind && (r.flags&0x200u)) {
                            irqSeen[target]=true;irqInstructions+=irqCheck(active,memory);
                        }
                }
                uint64_t used=0;
                try { used=active.advance(budget,bus); }
                catch (...) {
                    const auto r=active.registers();
                    std::cerr<<"dispatch_case="<<index<<" row="<<cursor<<" pc="<<std::hex<<r.cs<<':'<<r.ip<<std::dec<<'\n';
                    throw;
                }
                require(used && used<=budget && cursor+used<trace.size(),"Tail dispatch extent differs");
                cursor+=static_cast<size_t>(used);
                compare(active.registers(),trace[cursor],index,cursor,active.finished());++comparisons;
                active=FrameTailOperation(active.snapshot());
            }
            require(cursor+1==trace.size() && active.snapshot().outcome==outcomes[outcome] &&
                active.snapshot().dispatchedInstructions==cursor,"Tail terminal accounting differs");
            compare(active.registers(),endpoint,index,cursor,true);
            if (memory.writes!=writes) {
                size_t at=0;while (at<memory.writes.size() && at<writes.size() && memory.writes[at]==writes[at]) ++at;
                std::cerr<<"write_case="<<index<<" first="<<at<<" actual="<<memory.writes.size()<<" expected="<<writes.size()<<'\n';
                throw std::runtime_error("Tail ordered writes differ");
            }
            require(memory.bytes==expected.bytes && memory.ports==expectedPorts,"Tail complete RAM/DAC output differs");
            const auto saved=active.snapshot();
            require(active.advance(1,bus)==0 && active.snapshot()==saved,"Finished tail dispatched work");
            ++replays;dispatches+=cursor;written+=writes.size();ports+=expectedPorts.size();
        }
    }
    require(input.at==input.bytes.size(),"Tail input has trailing data");
    require(std::all_of(ownershipSeen.begin(),ownershipSeen.end(),[](bool v) { return v; }) &&
        std::all_of(returnSeen.begin(),returnSeen.end(),[](bool v) { return v; }) &&
        std::all_of(stackSeen.begin(),stackSeen.end(),[](bool v) { return v; }) &&
        std::all_of(irqSeen.begin(),irqSeen.end(),[](bool v) { return v; }),"Tail supplementary coverage differs");
    std::cout<<"frame_tail_original=ok cases="<<count<<" replays="<<replays<<" comparisons="<<comparisons
        <<" dispatches="<<dispatches<<" writes="<<written<<" dac_writes="<<ports
        <<" restore_rejections="<<stateRejections-previousRejections<<" return_rejections="<<returnSeen.size()*3
        <<" computed_irq_cases="<<irqSeen.size()<<" irq_instructions="<<irqInstructions
        <<" full_memory=1 canonical_mz=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {
        unit();
        if (argc==1) return 0;
        require(argc==3,"Expected fixture and original root");
        replay(argv[1],argv[2]);return 0;
    } catch (const std::exception& error) {
        std::cerr<<"frame_tail=failed "<<error.what()<<'\n';return 1;
    }
}
