#include "core/frame_actor_entry.hpp"

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
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing frame actor input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Write {
    uint32_t address;uint8_t size;uint16_t value;
    bool operator==(const Write&) const = default;
};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned count) {
        require(count<=4 && at+count<=bytes.size(),"Truncated frame actor fixture");
        uint32_t value=0;for (unsigned i=0;i<count;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t count) {
        std::vector<DosGetTimeRegisters> result(count);
        for (auto member : {&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
                &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
                &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
                &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip})
            for (auto& r : result) r.*member=static_cast<uint16_t>(number(2));
        for (auto& r : result) r.flags=number(4);
        return result;
    }
};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t s,uint16_t o) { return (uint32_t{s}*16+o)&0xfffffu; }
    uint16_t word(uint16_t s,uint16_t o) const {
        const auto a=address(s,o);return static_cast<uint16_t>(bytes[a]|(uint16_t{bytes[(a+1u)&0xfffffu]}<<8));
    }
    void store(uint32_t a,uint16_t value,uint8_t size=2) {
        bytes[a]=static_cast<uint8_t>(value);
        if (size==2) bytes[(a+1u)&0xfffffu]=static_cast<uint8_t>(value>>8);
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
            [](uint16_t port) -> uint8_t { require(port==0x61,"Unexpected frame actor IRQ input");return 0; },
            [](uint16_t port,uint8_t) { require(port==0x20 || port==0x61,"Unexpected frame actor IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};
    require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Frame actor original MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header,"Frame actor MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);
    exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(2),segment=exe.number(2),at=0x10000+segment*16+offset;
        require(at+1<result.bytes.size(),"Frame actor relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row) {
    const bool control=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    actual.flags=expected.flags;
    if (!control || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " di=" << actual.di << '/' << expected.di << std::dec << '\n';
        throw std::runtime_error("Frame actor register/control trace differs");
    }
}
FrameActorEntryOutcome outcome(uint32_t value) {
    constexpr std::array values{FrameActorEntryOutcome::ActorBody,FrameActorEntryOutcome::TransientQueues,
        FrameActorEntryOutcome::Restart,FrameActorEntryOutcome::EndRunUi,FrameActorEntryOutcome::RuntimeError};
    return values.at(value);
}
void irqCheck(FrameActorEntryOperation operation,Memory memory,const std::vector<uint8_t>& expected,
        DosGetTimeRegisters endpoint,uint16_t cs,uint16_t ip) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;
    const auto bus=memory.bus();const auto copies=[](uint16_t n) { return n; };
    unsigned steps=0;
    while (!operation.finished() && !(operation.registers().cs==cs && operation.registers().ip==ip)) {
        require(steps++<3000000,"Frame actor IRQ target missing");operation.advance(1,bus,copies);
    }
    require(!operation.finished(),"Frame actor IRQ target was already a handoff");
    operation.deliverTimerInterrupt(bus);
    require(operation.interruptInProgress(),"Frame actor IRQ not admitted");
    bool nested=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested,"Nested frame actor IRQ admitted");
    while (!operation.finished()) {
        require(steps++<3000000,"Frame actor IRQ continuation did not finish");operation.advance(17,bus,copies);
        operation=FrameActorEntryOperation(operation.snapshot());
    }
    const auto& final=operation.snapshot();
    require(operation.registers()==endpoint,"Frame actor IRQ changed endpoint registers");
    require(final.prefixTimerInstructions+final.tailTimerInstructions==36 &&
        final.prefixTimerDeliveries+final.tailTimerDeliveries==1 && memory.word(0x40,0x6c)==101,
        "Frame actor IRQ accounting/context differs");
    require(std::equal(memory.bytes.begin()+0xa0000,memory.bytes.begin()+0xb0001,expected.begin()+0xa0000),
        "Frame actor IRQ changed VGA endpoint");
    require(std::equal(memory.bytes.begin()+0x1aa20+0x1b88,memory.bytes.begin()+0x1aa20+0x2048,
        expected.begin()+0x1aa20+0x1b88),"Frame actor IRQ changed physical actor endpoint");
    bool ended=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished frame actor admitted an IRQ");
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};
    for (char c : std::string("LZACTR01")) require(input.number(1)==static_cast<uint8_t>(c),"Frame actor magic differs");
    const auto count=input.number(4);require(count==1034,"Frame actor corpus domain differs");
    const auto base=image(root);
    uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0;
    std::array<unsigned,5> outcomes{};std::array<unsigned,4> kinds{};
    constexpr std::array<std::array<uint16_t,2>,9> targets{{
        {{0x1000,0x7a57}},{{0x1000,0x7ec2}},{{0x1000,0x432a}},{{0x1920,0xf0f}},
        {{0x1000,0x7ee1}},{{0x1000,0x6053}},{{0x1920,0x91f}},{{0x1000,0x7f59}},{{0x1000,0x7f13}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Frame actor case index differs");
        const auto result=input.number(4),kind=input.number(4);
        require(result<outcomes.size() && kind<kinds.size(),"Frame actor outcome/kind differs");++outcomes[result];++kinds[kind];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        const auto seeds=input.number(4);require(seeds<2000,"Frame actor seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Frame actor seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>1 && states<3000000,"Frame actor trace reserve differs");
        const auto trace=input.trace(states);const auto written=input.number(4);require(written<300000,"Frame actor write reserve differs");
        auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Frame actor write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));
            writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();FrameActorEntryOperation operation(entry,0x1000,0x200000);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };const auto zero=operation.snapshot();
            require(operation.advance(0,bus,copies)==0 && operation.snapshot()==zero && memory.writes.empty(),"Zero frame actor budget changed state");
            size_t cursor=0;uint64_t consumed=0;
            compare(operation.registers(),trace.at(0),index,0);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus,copies);require(used>0 && used<=budget,"Frame actor dispatch grant differs");
                consumed+=used;require(operation.snapshot().dispatchedInstructions==consumed,"Frame actor dispatch accounting differs");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Frame actor exceeded original endpoint");const auto before=trace[cursor];
                    if (((before.cs==0x1000 && (before.ip==0x116a || before.ip==0x7ec)) ||
                            (before.cs==0x1920 && before.ip==0x91f)) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Frame actor REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                require(cursor<trace.size(),"Frame actor trace exhausted");compare(operation.registers(),trace[cursor],index,cursor);++comparisons;
                operation=FrameActorEntryOperation(operation.snapshot());
            }
            const auto done=operation.snapshot();
            require(cursor+1==trace.size() && operation.registers()==endpoint,"Frame actor endpoint/all flags differ");
            require(done.outcome==outcome(result) && static_cast<unsigned>(done.actorKind)==kind,"Frame actor handoff differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Frame actor ordered writes/complete memory differ");
            require(operation.advance(19,bus,copies)==0 && operation.snapshot()==done,"Finished frame actor operation changed state");
            dispatches+=done.dispatchedInstructions;++replays;
        }
        totalWrites+=writes.size();
        if (result==0 || result==1 || result==2) for (size_t target=0;target<targets.size();++target) if (!irqSeen[target]) {
            const auto [cs,ip]=targets[target];
            if (std::any_of(trace.begin(),trace.end(),[=](const auto& r) { return r.cs==cs && r.ip==ip; })) {
                irqCheck(FrameActorEntryOperation(entry,0x1000,0x200000),initial,expected.bytes,endpoint,cs,ip);irqSeen[target]=true;
            }
        }
    }
    require(input.at==input.bytes.size() && std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),
        "Frame actor fixture tail/IRQ coverage differs");
    require(std::all_of(outcomes.begin(),outcomes.end(),[](unsigned n) { return n!=0; }) &&
        std::all_of(kinds.begin(),kinds.end(),[](unsigned n) { return n!=0; }),"Frame actor handoff coverage differs");
    std::cout << "frame_actor_entry_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " computed_irq_cases=" << irqSeen.size()
        << " later_state_injected=0 actor_body_executed=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3ffe;r.ip=0x7ebb;
    unsigned rejected=0;
    for (unsigned variant=0;variant<4;++variant) {
        auto wrong=r;if (variant==0) ++wrong.cs;if (variant==1) ++wrong.ds;if (variant==2) wrong.ip=0;
        try { FrameActorEntryOperation invalid(wrong,0x1000,variant==3 ? 1 : 0); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    auto invalid=FrameActorEntryOperation(r,0x1000,0).snapshot();r.ip=0x7a57;
    invalid.callee=FramePrefixOperation(r,0x1000,0).snapshot();invalid.timer=TimerIrqSnapshot{};
    try { FrameActorEntryOperation operation(invalid); } catch (const std::invalid_argument&) { ++rejected; }
    require(rejected==5,"Frame actor accepted invalid entry/IRQ ownership");
    Memory memory;const auto bus=memory.bus();const auto copies=[](uint16_t n) { return n; };
    r.ip=0x7903;FrameActorEntryOperation full(r,0x140,0x160,0x900,0x1000,0);
    require(std::holds_alternative<FramePrefixSnapshot>(full.snapshot().callee),"Full-prefix actor entry does not own prefix");
    const auto before=full.snapshot();
    require(full.advance(0,bus,copies)==0 && full.snapshot()==before && memory.writes.empty(),"Zero full-prefix budget changed state");
    std::cout << "frame_actor_entry_unit=ok entry_rejections=5 full_prefix_constructor=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();else { require(argc==3,"Expected frame actor fixture and original root");replay(argv[1],argv[2]); }
        return 0;
    } catch (const std::exception& error) { std::cerr << "frame_actor_entry=failed " << error.what() << '\n';return 1; }
}
