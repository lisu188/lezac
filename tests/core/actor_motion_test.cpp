#include "core/actor_motion.hpp"
#include "core/actor_tile_flags.hpp"

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
std::vector<uint8_t> read(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing motion input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated motion fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t n) {
        std::vector<DosGetTimeRegisters> rows;rows.reserve(n);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<n;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i!=0 || mask==0x3fff),"Motion delta mask differs");
            for (unsigned column=0;column<members.size();++column)
                if (mask&(1u<<column)) previous.*members[column]=static_cast<uint16_t>(number(2));
            if (mask&0x2000u) previous.flags=number(4);
            rows.push_back(previous);
        }
        return rows;
    }
};
struct Write { uint32_t address;uint8_t size;uint16_t value;bool operator==(const Write&) const = default; };
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);std::vector<Write> writes;
    static uint32_t address(uint16_t s,uint16_t o) { return (uint32_t{s}*16+o)&0xfffffu; }
    uint16_t word(uint16_t s,uint16_t o) const {
        const auto a=address(s,o);return static_cast<uint16_t>(bytes[a]|(uint16_t{bytes[(a+1u)&0xfffffu]}<<8));
    }
    void store(uint32_t a,uint16_t v,uint8_t n=2) {
        bytes[a]=static_cast<uint8_t>(v);if (n==2) bytes[(a+1u)&0xfffffu]=static_cast<uint8_t>(v>>8);
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected motion IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected motion IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Motion MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,"Motion MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Motion relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
struct Execution {
    std::optional<FrameActorContactOperation> prefix;
    std::optional<ActorTileFlagsOperation> tile;
    std::optional<ActorMotionOperation> motion;
    std::optional<ActorFinishOperation> finish;
    uint32_t domain=0;int result=-1;uint64_t dispatched=0;
    Execution(DosGetTimeRegisters r,uint32_t mode) : domain(mode) {
        if (mode<4) motion.emplace(r,uint16_t{0x1000},uint32_t{0x200000},static_cast<ActorMotionEntry>(mode));
        else prefix.emplace(r,uint16_t{0x1000},uint32_t{0x200000});
    }
    DosGetTimeRegisters registers() const {
        return finish ? finish->registers() : motion ? motion->registers() : tile ? tile->registers() : prefix->registers();
    }
    bool finished() const { return result>=0; }
    void restore() {
        if (prefix) *prefix=FrameActorContactOperation(prefix->snapshot());
        if (tile) *tile=ActorTileFlagsOperation(tile->snapshot());
        if (motion) *motion=ActorMotionOperation(motion->snapshot());
        if (finish) *finish=ActorFinishOperation(finish->snapshot());
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        const auto all=[](uint16_t n) { return n; };uint64_t used=0;
        while (used<budget && !finished()) {
            if (finish) {
                require(finish->advance(1,bus,all)==1,"Actor finish failed to dispatch");
                if (finish->finished()) result=finish->snapshot().outcome==ActorFinishOutcome::Returned ? 4 : 2;
            } else if (motion) {
                require(motion->advance(1,bus,all)==1,"Actor motion failed to dispatch");
                if (motion->finished()) {
                    const auto r=motion->registers();
                    switch (motion->snapshot().outcome) {
                    case ActorMotionOutcome::MotionIntegration:
                        if (domain<4) result=0;
                        else { finish.emplace(r,uint16_t{0x1000},uint32_t{0x200000});motion.reset(); }
                        break;
                    case ActorMotionOutcome::Returned:result=1;break;
                    case ActorMotionOutcome::RuntimeError:result=2;break;
                    case ActorMotionOutcome::DivideError:result=3;break;
                    default:throw std::runtime_error("Motion did not reach a terminal outcome");
                    }
                }
            } else if (tile) {
                require(tile->advance(1,bus)==1,"Actor classifier failed to dispatch");
                if (tile->finished()) {
                    require(tile->snapshot().outcome==ActorTileFlagsOutcome::Behavior,"Motion corpus left nonzero behavior scope");
                    motion.emplace(tile->registers(),uint16_t{0x1000},uint32_t{0x200000});tile.reset();
                }
            } else {
                require(prefix->advance(1,bus,all)==1,"Actor prefix failed to dispatch");
                if (prefix->finished()) {
                    const auto r=prefix->registers();
                    if (prefix->snapshot().outcome==FrameActorContactOutcome::TileBehavior) {
                        tile.emplace(r,uint16_t{0x1000},uint32_t{0x200000});prefix.reset();
                    } else if (prefix->snapshot().outcome==FrameActorContactOutcome::MotionIntegration) {
                        finish.emplace(r,uint16_t{0x1000},uint32_t{0x200000});prefix.reset();
                    } else if (prefix->snapshot().outcome==FrameActorContactOutcome::RuntimeError) result=2;
                    else throw std::runtime_error("Motion prefix left declared continuation scope");
                }
            }
            ++used;++dispatched;
        }
        return used;
    }
};
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row) {
    const bool flags=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;const auto oldFlags=actual.flags;actual.flags=expected.flags;
    if (!flags || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " bx=" << actual.bx << '/' << expected.bx << " cx=" << actual.cx << '/' << expected.cx
            << " dx=" << actual.dx << '/' << expected.dx << " di=" << actual.di << '/' << expected.di
            << " bp=" << actual.bp << '/' << expected.bp << " sp=" << actual.sp << '/' << expected.sp
            << " flags=" << oldFlags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Motion register/control trace differs");
    }
}
uint64_t irqCheck(ActorMotionOperation operation,Memory memory) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    const auto before=operation.registers();operation.deliverTimerInterrupt(bus);bool nested=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && operation.snapshot().cpu.timerDeliveries==1,"Motion IRQ nesting/accounting differs");unsigned steps=0;
    while (operation.interruptInProgress()) {
        require(steps++<4096,"Motion IRQ did not return");operation.advance(1,bus,all);operation=ActorMotionOperation(operation.snapshot());
    }
    require(operation.registers()==before && memory.word(0x40,0x6c)==101,"Motion IRQ did not restore CPU/clock");
    auto other=operation;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!operation.finished()) { require(steps++<3000000,"Motion IRQ continuation stalled");operation.advance(1,bus,all); }
    while (!other.finished()) { require(steps++<6000000,"Motion IRQ alternate stalled");other.advance(17,otherBus,all);other=ActorMotionOperation(other.snapshot()); }
    require(operation.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Motion IRQ continuation grant/snapshot differs");
    bool ended=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished motion admitted IRQ");return operation.snapshot().cpu.timerInstructions;
}
void replay(const char* path,const char* root,bool oneGrant) {
    Reader input{read(path)};for (char c : std::string("LZMOTION")) require(input.number(1)==static_cast<uint8_t>(c),"Motion magic differs");
    const auto count=input.number(4);require(count==78927,"Motion corpus domain differs");const auto base=image(root);
    uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0,irqInstructions=0;
    std::array<unsigned,5> outcomes{};std::array<unsigned,6> domains{};
    constexpr std::array<std::array<uint16_t,2>,18> targets{{
        {{0x1000,0x7018}},{{0x1000,0x70dc}},{{0x1000,0x7131}},{{0x1000,0x71e7}},
        {{0x1000,0x72ac}},{{0x1000,0x7364}},{{0x1000,0x738c}},{{0x1000,0x73d2}},
        {{0x1000,0x370e}},{{0x1000,0x3780}},{{0x1000,0x3861}},{{0x1000,0x3a16}},
        {{0x1000,0x5b73}},{{0x1000,0x5b86}},{{0x1000,0x5bb9}},
        {{0x1920,0xfc2}},{{0x1920,0xff8}},{{0x1920,0x13f7}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Motion case index differs");const auto result=input.number(4),domain=input.number(4);
        require(result<outcomes.size() && domain<domains.size(),"Motion outcome/domain differs");++outcomes[result];++domains[domain];
        require(domain<4 || result==4,"Continuous motion case did not execute the actor return");
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
        require(seeds<4096,"Motion seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Motion seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>1 && states<3000000,"Motion trace reserve differs");
        const auto trace=input.trace(states);require(trace.front()==entry && trace.back()==endpoint,"Motion trace endpoints differ");
        const auto written=input.number(4);require(written<300000,"Motion write reserve differs");auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Motion write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        for (uint64_t budget : {1u,17u,4096u}) {
            if (oneGrant && budget!=1) continue;
            auto memory=initial;const auto bus=memory.bus();Execution operation(entry,domain);
            require(operation.advance(0,bus)==0 && operation.dispatched==0 && memory.writes.empty(),"Zero motion budget changed state");
            size_t cursor=0;compare(operation.registers(),trace.at(0),index,0);++comparisons;
            while (!operation.finished()) {
                uint64_t used=0;
                try { used=operation.advance(budget,bus); }
                catch (...) {
                    const auto r=operation.registers();
                    std::cerr << "case=" << index << " row=" << cursor << " stopped=" << std::hex
                        << r.cs << ':' << r.ip << std::dec << '\n';
                    throw;
                }
                require(used>0 && used<=budget,"Motion dispatch grant differs");
                for (uint64_t i=0;i<used;++i) {
                    const auto before=trace.at(cursor);
                    if ((before.cs==0x1920 && before.ip==0x91f) || (before.cs==0x18ac && before.ip==0x5d2)) {
                        cursor+=before.cx;
                        if (cursor<trace.size() && trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                require(cursor<trace.size(),"Motion exceeded original endpoint");operation.restore();
                compare(operation.registers(),trace[cursor],index,cursor);++comparisons;
            }
            if (operation.registers()!=endpoint) {
                compare(operation.registers(),endpoint,index,cursor);
                std::cerr << "case=" << index << " endpoint_flags=" << std::hex << operation.registers().flags << '/' << endpoint.flags << std::dec << '\n';
                throw std::runtime_error("Motion endpoint/all flags differ");
            }
            require(cursor+1==trace.size() && operation.result==static_cast<int>(result),"Motion outcome/trace extent differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Motion ordered writes/complete memory differ");
            const auto before=operation.registers();require(operation.advance(19,bus)==0 && operation.registers()==before,"Finished motion changed state");
            dispatches+=operation.dispatched;++replays;
        }
        totalWrites+=writes.size();bool needed=false;
        for (const auto& r : trace) for (size_t i=0;i<targets.size();++i)
            needed|=!irqSeen[i] && r.cs==targets[i][0] && r.ip==targets[i][1] && (r.flags&0x200u);
        if (needed) {
            auto memory=initial;const auto bus=memory.bus();Execution operation(entry,domain);unsigned steps=0;
            while (!operation.finished()) {
                require(steps++<3000000,"Motion IRQ seek stalled");const auto r=operation.registers();
                if (operation.motion) for (size_t i=0;i<targets.size();++i)
                    if (!irqSeen[i] && r.cs==targets[i][0] && r.ip==targets[i][1] && (r.flags&0x200u)) {
                        irqInstructions+=irqCheck(*operation.motion,memory);irqSeen[i]=true;
                    }
                operation.advance(1,bus);
            }
        }
        if (index && index%16384==0) std::cout << "actor_motion_progress=" << index << '/' << count << '\n' << std::flush;
    }
    require(input.at==input.bytes.size() && domains==std::array<unsigned,6>{6475,376,6416,65552,54,54} &&
        std::all_of(outcomes.begin(),outcomes.end(),[](unsigned n) { return n!=0; }) &&
        std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),"Motion coverage/tail differs");
    std::cout << "actor_motion_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " computed_irq_cases=" << targets.size()
        << " irq_instructions=" << irqInstructions << " one_grant=" << oneGrant
        << " friction_words=65536 continuous_actor_cases=54 real_caller_cases=54 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3f8c;r.bp=0x3fdc;r.ip=0x7018;r.ax=4;r.flags=2;
    Memory memory;ActorMotionOperation operation(r,0x1000,0x200000);const auto before=operation.snapshot();
    const auto all=[](uint16_t n) { return n; };
    require(operation.advance(0,memory.bus(),all)==0 && operation.snapshot()==before,"Zero motion unit budget changed state");
    bool masked=false;try { operation.deliverTimerInterrupt(memory.bus()); } catch (const std::logic_error&) { masked=true; }
    require(masked && memory.writes.empty() && operation.snapshot()==before,"Masked motion IRQ changed state");
    for (unsigned mutation=0;mutation<9;++mutation) {
        bool rejected=false;
        try {
            if (mutation==0) { auto other=r;other.cs=0x1920;ActorMotionOperation invalid(other,0x1000,0x200000); }
            if (mutation==1) { auto other=r;other.ds=0;ActorMotionOperation invalid(other,0x1000,0x200000); }
            if (mutation==2) { auto other=r;other.ip=0x701a;ActorMotionOperation invalid(other,0x1000,0x200000); }
            if (mutation==3) { ActorMotionOperation invalid(r,0x1000,1); }
            if (mutation==4) { auto state=before;state.entry=static_cast<ActorMotionEntry>(99);ActorMotionOperation invalid(state); }
            if (mutation==5) { auto state=before;state.outcome=ActorMotionOutcome::RuntimeError;ActorMotionOperation invalid(state); }
            if (mutation==6) { auto state=before;state.cpu.outcome=ActorFinishOutcome::Returned;ActorMotionOperation invalid(state); }
            if (mutation==7) { auto state=before;state.cpu.registers.cs=0x18ac;ActorMotionOperation invalid(state); }
            if (mutation==8) { auto state=before;state.outcome=ActorMotionOutcome::Returned;ActorMotionOperation invalid(state); }
        } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected,"Invalid motion entry/snapshot was admitted");
    }
    auto state=before;state.cpu.registers.ip=0x70dc;state.cpu.registers.ax=123;state.cpu.registers.dx=0;
    ActorMotionOperation fault(state);const auto regs=fault.registers();require(fault.advance(1,memory.bus(),all)==1 &&
        fault.snapshot().outcome==ActorMotionOutcome::DivideError && fault.registers()==regs && memory.writes.empty(),
        "Motion divide fault did not preserve pre-handler CPU/memory");
    require(fault.advance(1,memory.bus(),all)==0,"Finished divide fault dispatched");
    std::cout << "actor_motion_unit=ok entry_state_rejections=9 masked_irq=1 precise_divide_fault=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==3 || (argc==4 && std::string(argv[3])=="--one-grant"),"Motion replay arguments differ");replay(argv[1],argv[2],argc==4); }
        return 0;
    } catch (const std::exception& e) { std::cerr << "actor_motion=failed " << e.what() << '\n';return 1; }
}
