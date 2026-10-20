#include "core/nonplayer_loop.hpp"

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
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing loop input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated loop fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace() {
        const auto count=number(4);require(count>1 && count<=3000000,"Loop trace reserve differs");
        std::vector<DosGetTimeRegisters> rows;rows.reserve(count);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<count;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i || mask==0x3fff),"Loop delta mask differs");
            for (unsigned c=0;c<members.size();++c)
                if (mask&(1u<<c)) previous.*members[c]=static_cast<uint16_t>(number(2));
            if (mask&0x2000u) previous.flags=number(4);
            rows.push_back(previous);
        }
        return rows;
    }
};
struct Write { uint32_t address;uint8_t size;uint16_t value;bool operator==(const Write&) const = default; };
struct Event { uint32_t row;std::array<uint16_t,6> words;bool operator==(const Event&) const = default; };
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected loop IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected loop IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Loop MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,
        "Loop MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Loop relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,bool endpoint=false) {
    const auto flags=actual.flags;
    const bool defined=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    if (!endpoint) actual.flags=expected.flags;
    if (!defined || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " sp=" << actual.sp << '/' << expected.sp << " bp=" << actual.bp << '/' << expected.bp
            << " flags=" << flags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Nonplayer loop register/control trace differs");
    }
}
bool isEvent(const DosGetTimeRegisters& r) {
    return r.cs==0x1000 && (r.ip==0x62da || r.ip==0x6350 || r.ip==0x6500 || r.ip==0x654e ||
        r.ip==0x7018 || r.ip==0x7ee4);
}
Event event(const Memory& memory,const DosGetTimeRegisters& r,uint32_t row) {
    return {row,{r.ip,memory.word(r.ds,0x2082),memory.word(r.ss,static_cast<uint16_t>(r.bp-4u)),
        memory.word(r.ss,static_cast<uint16_t>(r.bp-6u)),memory.word(r.ss,static_cast<uint16_t>(r.bp-8u)),
        memory.word(r.ss,static_cast<uint16_t>(r.bp-10u))}};
}
uint64_t irqCheck(NonplayerLoopOperation active,Memory memory,bool partial) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    if (partial) {
        const auto before=active.registers();const auto count=memory.writes.size();
        require(before.cx>1,"Loop partial-copy IRQ lacks bytes");
        active.advance(1,bus,[](uint16_t) { return uint16_t{1}; });
        require(active.registers().ip==before.ip && active.registers().cx==before.cx-1 &&
            memory.writes.size()==count+1,"Loop partial copy did not transfer one byte");
    }
    const auto before=active.registers();const auto deliveries=active.snapshot().timerDeliveries;
    const auto instructions=active.snapshot().timerInstructions;
    active.deliverTimerInterrupt(bus);
    bool nested=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && active.snapshot().timerDeliveries==deliveries+1,"Loop IRQ nesting/accounting differs");
    unsigned steps=0;
    while (active.interruptInProgress()) {
        require(steps++<4096,"Loop IRQ did not return");active.advance(1,bus,all);
        active=NonplayerLoopOperation(active.snapshot());
    }
    require(active.registers()==before && memory.word(0x40,0x6c)==101,"Loop IRQ did not restore CPU/BIOS tick");
    auto other=active;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    const auto irqInstructions=active.snapshot().timerInstructions-instructions;
    while (!active.finished()) { require(steps++<3000000,"Loop IRQ continuation stalled");active.advance(1,bus,all); }
    while (!other.finished()) {
        require(steps++<6000000,"Loop IRQ alternate stalled");other.advance(17,otherBus,all);
        other=NonplayerLoopOperation(other.snapshot());
    }
    require(active.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Loop IRQ continuation grant/snapshot differs");
    bool ended=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended && irqInstructions>0,"Finished loop admitted IRQ or IRQ did not dispatch");
    return irqInstructions;
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};require(input.bytes.size()==2396804,"Loop corpus size differs");
    uint64_t hash=14695981039346656037ull;
    for (uint8_t byte : input.bytes) { hash^=byte;hash*=1099511628211ull; }
    require(hash==0x3bc29790f3c11629ull,"Loop corpus fingerprint differs");
    for (char c : std::string("LZNPL001")) require(input.number(1)==static_cast<uint8_t>(c),"Loop magic differs");
    const auto count=input.number(4);require(count==92,"Loop domain differs");const auto base=image(root);
    const auto all=[](uint16_t n) { return n; };
    uint64_t comparisons=0,replays=0,dispatches=0,totalWrites=0,totalEvents=0,calls=0,returns=0,irqInstructions=0;
    std::array<unsigned,4> outcomes{};
    constexpr std::array<std::array<uint16_t,2>,10> targets{{
        {{0x1000,0x7ebb}},{{0x1000,0x7ee4}},{{0x1000,0x62da}},{{0x1000,0x6350}},{{0x1000,0x6500}},
        {{0x1000,0x654e}},{{0x1000,0x65a2}},{{0x1000,0x7018}},{{0x1000,0x73e5}},{{0x18ac,0x5d2}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Loop row order differs");const auto outcome=input.number(1);
        require(outcome<4,"Loop outcome differs");++outcomes[outcome];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        const auto seeds=input.number(4);require(seeds<65536,"Loop seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto address=input.number(4),size=input.number(4);
            require(size<=65536 && address>=0x1aa20 && address+size<=1048576 && input.at+size<=input.bytes.size(),
                "Loop seed exceeds memory");
            std::copy_n(input.bytes.begin()+input.at,size,initial.bytes.begin()+address);input.at+=size;
        }
        const auto trace=input.trace();compare(trace.front(),entry,index,0,true);
        const auto writeCount=input.number(4);require(writeCount<3000000,"Loop write reserve differs");
        std::vector<Write> writes;auto expected=initial;
        for (unsigned i=0;i<writeCount;++i) {
            Write item{input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require((item.size==1 || item.size==2) && item.address+item.size<=1048576,"Loop write exceeds memory");
            writes.push_back(item);expected.store(item.address,item.value,item.size);
        }
        const auto eventCount=input.number(4);require(eventCount<100000,"Loop event reserve differs");
        std::vector<Event> events;
        for (unsigned i=0;i<eventCount;++i) {
            Event item{input.number(4),{}};for (auto& word : item.words) word=static_cast<uint16_t>(input.number(2));
            require(item.row<trace.size(),"Loop event exceeds trace");events.push_back(item);
        }
        unsigned mode=0;
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();NonplayerLoopOperation active(entry,0x1000,0x200000);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };
            size_t cursor=0,eventCursor=0;compare(active.registers(),trace.front(),index,0);++comparisons;
            while (!active.finished()) {
                require(cursor+1<trace.size(),"Loop exceeded original endpoint");
                if (!mode && isEvent(active.registers())) {
                    require(eventCursor<events.size() && event(memory,active.registers(),static_cast<uint32_t>(cursor))==
                        events[eventCursor++],"Loop live-stack target/slot checkpoint differs");
                }
                const auto used=active.advance(budget,bus,copies);
                require(used>0 && used<=budget,"Loop grant did not dispatch");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Loop exceeded original endpoint");
                    const auto before=trace[cursor];
                    if (((before.cs==0x1920 && before.ip==0x91f) ||
                            (before.cs==0x18ac && before.ip==0x5d2)) && before.cx) {
                        cursor+=std::min(before.cx,limit);
                        require(cursor<trace.size(),"Loop REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                active=NonplayerLoopOperation(active.snapshot());
                compare(active.registers(),trace[cursor],index,cursor);++comparisons;
            }
            compare(active.registers(),endpoint,index,cursor,true);
            require(cursor+1==trace.size() && (mode || eventCursor==events.size()),"Loop trace/event extent differs");
            const auto actual=active.snapshot().outcome;
            require((outcome==0 && actual==NonplayerLoopOutcome::PlayerPhase) ||
                (outcome==1 && actual==NonplayerLoopOutcome::PlayerMotion) ||
                (outcome==2 && actual==NonplayerLoopOutcome::RuntimeError) ||
                (outcome==3 && actual==NonplayerLoopOutcome::DivideError),"Loop handoff differs");
            require(memory.bytes==expected.bytes && memory.writes==writes,"Loop ordered writes/complete memory differ");
            const auto done=active.snapshot();require(active.advance(19,bus,all)==0 && active.snapshot()==done,
                "Finished loop changed state");
            dispatches+=active.snapshot().dispatchedInstructions;++replays;
            if (!mode) { calls+=active.snapshot().actorCalls;returns+=active.snapshot().actorReturns; }
            ++mode;
        }
        if (outcome==0) {
            auto memory=initial;const auto bus=memory.bus();NonplayerLoopOperation active(entry,0x1000,0x200000);
            unsigned steps=0;
            while (!active.finished()) {
                require(steps++<3000000,"Loop IRQ target seek stalled");const auto r=active.registers();
                for (size_t i=0;i<targets.size();++i)
                    if (!irqSeen[i] && r.cs==targets[i][0] && r.ip==targets[i][1] &&
                            (r.flags&0x200u) && (r.cs!=0x18ac || r.cx>1)) {
                        irqInstructions+=irqCheck(active,memory,r.cs==0x18ac);irqSeen[i]=true;
                    }
                active.advance(1,bus,all);
            }
        }
        totalWrites+=writes.size();totalEvents+=events.size();
    }
    require(input.at==input.bytes.size() && outcomes==std::array<unsigned,4>{88,2,1,1} && calls==453 && returns==449,
        "Loop coverage/tail differs");
    require(std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),"Loop IRQ phase coverage differs");
    std::cout << "nonplayer_loop_original=ok cases=92 replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " events=" << totalEvents
        << " actor_calls=" << calls << " actor_returns=" << returns << " computed_irq_cases=" << targets.size()
        << " irq_instructions=" << irqInstructions << " partial_copy_irqs=1"
        << " one_live_stack=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3ffe;r.ip=0x7ebb;r.flags=2;
    Memory memory;const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    NonplayerLoopOperation active(r,0x1000,0x200000);const auto before=active.snapshot();
    require(active.advance(0,bus,all)==0 && active.snapshot()==before,"Zero loop budget changed state");
    bool masked=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { masked=true; }
    require(masked && active.snapshot()==before && memory.writes.empty(),"Masked loop IRQ changed state");
    require(active.advance(4096,bus,all)==7 && active.finished() && active.registers().ip==0x7eea &&
        active.snapshot().actorCalls==0 && active.snapshot().actorReturns==0 && memory.word(r.ds,0x2082)==1,
        "Empty original nonplayer loop differs");
    const auto done=active.snapshot();
    require(active.advance(7,bus,all)==0 && active.snapshot()==done,"Finished empty loop dispatched");
    bool ended=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished loop admitted IRQ");
    unsigned rejections=0;
    for (unsigned mutation=0;mutation<9;++mutation) {
        bool rejected=false;
        try {
            if (mutation==0) { auto wrong=r;wrong.ip=0x7ee4;NonplayerLoopOperation invalid(wrong,0x1000,0x200000); }
            if (mutation==1) { auto wrong=r;wrong.ds=0;NonplayerLoopOperation invalid(wrong,0x1000,0x200000); }
            if (mutation==2) { NonplayerLoopOperation invalid(r,0x1000,1); }
            if (mutation==3) { auto state=before;state.actorReturns=1;NonplayerLoopOperation invalid(state); }
            if (mutation==4) { auto state=before;state.outcome=NonplayerLoopOutcome::PlayerPhase;NonplayerLoopOperation invalid(state); }
            if (mutation==5) { auto state=before;state.idToggleMask=0;NonplayerLoopOperation invalid(state); }
            if (mutation==6) { auto state=before;state.outcome=static_cast<NonplayerLoopOutcome>(99);NonplayerLoopOperation invalid(state); }
            if (mutation==7) {
                auto state=before;auto child=std::get<FrameActorEntrySnapshot>(state.callee);
                child.outcome=FrameActorEntryOutcome::ActorBody;state.callee=child;NonplayerLoopOperation invalid(state);
            }
            if (mutation==8) {
                auto state=before;auto wrong=r;wrong.ip=0x7a57;
                state.callee=FrameActorEntryOperation(wrong,0x1000,0x200000).snapshot();
                NonplayerLoopOperation invalid(state);
            }
        } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected,"Invalid loop entry/snapshot admitted");++rejections;
    }
    std::cout << "nonplayer_loop_unit=ok entry_state_rejections=" << rejections
        << " masked_irq=1 empty_loop=1 terminal_gate=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==3,"Loop replay arguments differ");replay(argv[1],argv[2]); }
        return 0;
    } catch (const std::exception& error) { std::cerr << "nonplayer_loop=failed " << error.what() << '\n';return 1; }
}
