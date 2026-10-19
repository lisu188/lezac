#include "core/actor_finish.hpp"

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
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing finish input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Write {
    uint32_t address;uint8_t size;uint16_t value;
    bool operator==(const Write&) const = default;
};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated finish fixture");
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
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected finish IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected finish IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Finish MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,"Finish MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(2),segment=exe.number(2),at=0x10000+segment*16+offset;
        require(at+1<result.bytes.size(),"Finish relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row) {
    const bool control=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;actual.flags=expected.flags;
    if (!control || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " dx=" << actual.dx << '/' << expected.dx << " di=" << actual.di << '/' << expected.di << std::dec << '\n';
        throw std::runtime_error("Finish register/control trace differs");
    }
}
FrameActorFinishOutcome outcome(uint32_t value) {
    constexpr std::array values{FrameActorFinishOutcome::TileBehavior,FrameActorFinishOutcome::ActorReturned,
        FrameActorFinishOutcome::TransientQueues,FrameActorFinishOutcome::Restart,
        FrameActorFinishOutcome::EndRunUi,FrameActorFinishOutcome::RuntimeError};
    return values.at(value);
}
struct IrqResult { bool registerSensitive,targetLocalsSensitive,soundActive;uint64_t instructions; };
IrqResult irqCheck(FrameActorFinishOperation operation,Memory memory,
        DosGetTimeRegisters endpoint,const Memory& originalFinal,bool actorEndpoint,uint16_t actorBp,uint16_t cs,uint16_t ip,uint16_t ds) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;
    const auto bus=memory.bus();const auto copies=[](uint16_t n) { return n; };unsigned steps=0;
    const auto reached=[&] {
        const auto now=operation.registers();
        return now.cs==cs && now.ip==ip && (!ds || (now.ds==ds && now.cx==2));
    };
    const auto seekingCopies=[&](uint16_t n) {
        const auto now=operation.registers();
        return ds && now.cs==cs && now.ip==ip && now.ds==ds && now.cx>2 ?
            std::min(n,static_cast<uint16_t>(now.cx-2u)) : n;
    };
    while (!operation.finished() && !reached()) {
        require(steps++<3000000,"Finish IRQ target missing");operation.advance(1,bus,seekingCopies);
    }
    require(!operation.finished(),"Finish IRQ target already finished");
    const auto beforeRegisters=operation.registers();const auto beforeBytes=memory.bytes;
    require(!ds || (beforeRegisters.ds==beforeRegisters.ss && beforeRegisters.cx==2 &&
        !memory.writes.empty() && memory.writes.back().size==1 &&
        memory.writes.back().address==Memory::address(beforeRegisters.es,static_cast<uint16_t>(beforeRegisters.di-1u))),
        "Finish late-copy IRQ did not follow an actual byte transfer");
    const bool activeSound=memory.bytes[0x1aa20+0x79c4]!=0;
    operation.deliverTimerInterrupt(bus);
    require(operation.interruptInProgress(),"Finish IRQ not admitted");bool nested=false;
    uint64_t admitted=operation.snapshot().prefixTimerDeliveries;
    if (const auto* child=std::get_if<ActorFinishSnapshot>(&operation.snapshot().callee)) admitted+=child->timerDeliveries;
    require(admitted==1,"Finish IRQ delivery was not accounted immediately");
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested,"Nested finish IRQ admitted");
    while (operation.interruptInProgress()) {
        require(steps++<3000000,"Finish IRQ did not return");operation.advance(1,bus,copies);
        operation=FrameActorFinishOperation(operation.snapshot());
    }
    require(operation.registers()==beforeRegisters,"Finish IRQ did not restore immediate CPU context");
    require(std::equal(memory.bytes.begin()+0xa0000,memory.bytes.begin()+0xb0001,beforeBytes.begin()+0xa0000),"Finish IRQ handler changed VGA");
    require(std::equal(memory.bytes.begin()+0x1aa20+0x1b88,memory.bytes.begin()+0x1aa20+0x2048,
        beforeBytes.begin()+0x1aa20+0x1b88),"Finish IRQ handler changed physical actors");
    require(std::equal(memory.bytes.begin()+0x50000,memory.bytes.begin()+0x60000,beforeBytes.begin()+0x50000),"Finish IRQ handler changed far actors");
    auto reference=operation;auto referenceMemory=memory;const auto referenceBus=referenceMemory.bus();
    while (!reference.finished()) {
        require(steps++<3000000,"Finish IRQ reference did not finish");reference.advance(1,referenceBus,copies);
    }
    while (!operation.finished()) {
        require(steps++<3000000,"Finish IRQ continuation did not finish");operation.advance(17,bus,copies);
        operation=FrameActorFinishOperation(operation.snapshot());
    }
    const auto& final=operation.snapshot();
    uint64_t instructions=final.prefixTimerInstructions,deliveries=final.prefixTimerDeliveries;
    if (const auto* child=std::get_if<ActorFinishSnapshot>(&final.callee)) {
        instructions+=child->timerInstructions;deliveries+=child->timerDeliveries;
    }
    require(operation.snapshot()==reference.snapshot() && memory.bytes==referenceMemory.bytes &&
        memory.writes==referenceMemory.writes,"Finish IRQ continuation grant/snapshot differs");
    require(instructions>=36 && instructions<4096 && deliveries==1 && memory.word(0x40,0x6c)==101,"Finish IRQ accounting/context differs");
    bool ended=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished finish admitted IRQ");
    const bool targetLocalsSensitive=actorEndpoint &&
        (memory.word(endpoint.ss,static_cast<uint16_t>(actorBp-4u))!=originalFinal.word(endpoint.ss,static_cast<uint16_t>(actorBp-4u)) ||
         memory.word(endpoint.ss,static_cast<uint16_t>(actorBp-6u))!=originalFinal.word(endpoint.ss,static_cast<uint16_t>(actorBp-6u)));
    return {operation.registers()!=endpoint,targetLocalsSensitive,activeSound,instructions};
}
void replay(const char* path,const char* root,bool oneGrant) {
    Reader input{read(path)};for (char c : std::string("LZFINI01")) require(input.number(1)==static_cast<uint8_t>(c),"Finish magic differs");
    const auto count=input.number(4);require(count==6136,"Finish corpus domain differs");const auto base=image(root);
    uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0,irqInstructions=0;
    unsigned irqStackSensitive=0,irqTargetSensitive=0,soundIrqs=0;std::array<unsigned,6> outcomes{};std::array<unsigned,5> domains{};
    constexpr std::array<std::array<uint16_t,3>,43> targets{{
        {{0x1000,0x7a57}},{{0x1000,0x7ec2}},{{0x1000,0x432a}},{{0x1000,0x6053}},{{0x1920,0x91f}},
        {{0x1000,0x615a}},{{0x1000,0x5872}},{{0x1000,0x5a75}},{{0x1920,0x13a8}},{{0x1000,0x6500}},
        {{0x1000,0x654e}},{{0x1000,0x655b}},{{0x1000,0x6592}},{{0x1000,0x5cb0}},
        {{0x1000,0x5d23}},{{0x1000,0x5d7a}},{{0x1000,0x5dc9}},{{0x1000,0x5e1f}},
        {{0x1000,0x5f3c}},{{0x1000,0x3a56}},{{0x1000,0x5f9d}},{{0x1000,0x5bcc}},
        {{0x1000,0x5740}},{{0x1000,0x165a}},{{0x1000,0x585a}},{{0x1000,0x6006}},{{0x1000,0x6044}},
        {{0x1000,0x73e5}},{{0x1000,0x73fd}},{{0x1000,0x56b6}},{{0x1000,0x74bb}},
        {{0x1000,0x754a}},{{0x1000,0x75b0}},{{0x1000,0x414a}},{{0x1000,0x3fa6}},
        {{0x1920,0xf01}},{{0x1920,0x1021}},{{0x1920,0x1034}},{{0x1000,0x495}},
        {{0x1920,0x91f,0x7000}},{{0x1000,0x2f9f}},{{0x18ac,0x517}},{{0x1000,0x7780}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Finish case index differs");const auto result=input.number(4),domain=input.number(4);
        require(result<outcomes.size() && domain<domains.size(),"Finish outcome/domain differs");++outcomes[result];++domains[domain];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
        require(seeds<2000,"Finish seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Finish seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>1 && states<3000000,"Finish trace reserve differs");
        const auto trace=input.trace(states);const auto written=input.number(4);require(written<300000,"Finish write reserve differs");
        auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Finish write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            if (oneGrant && (limit!=65535 || budget!=1)) continue;
            auto memory=initial;const auto bus=memory.bus();FrameActorFinishOperation operation(entry,0x1000,0x200000);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };const auto zero=operation.snapshot();
            require(operation.advance(0,bus,copies)==0 && operation.snapshot()==zero && memory.writes.empty(),"Zero finish budget changed state");
            size_t cursor=0;uint64_t consumed=0;compare(operation.registers(),trace.at(0),index,0);++comparisons;
            while (!operation.finished()) {
                uint64_t used=0;
                try { used=operation.advance(budget,bus,copies); }
                catch (...) {
                    const auto stopped=operation.registers();
                    std::cerr << "case=" << index << " row=" << cursor << " stopped=" << std::hex
                        << stopped.cs << ':' << stopped.ip << std::dec << '\n';throw;
                }
                require(used>0 && used<=budget,"Finish dispatch grant differs");
                consumed+=used;require(operation.snapshot().dispatchedInstructions==consumed,"Finish dispatch accounting differs");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Finish exceeded original endpoint");const auto before=trace[cursor];
                    if (((before.cs==0x1000 && (before.ip==0x116a || before.ip==0x7ec)) ||
                            (before.cs==0x1920 && before.ip==0x91f)) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Finish REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                require(cursor<trace.size(),"Finish trace exhausted");compare(operation.registers(),trace[cursor],index,cursor);++comparisons;
                operation=FrameActorFinishOperation(operation.snapshot());
            }
            const auto done=operation.snapshot();
            require(cursor+1==trace.size() && operation.registers()==endpoint,"Finish endpoint/all flags differ");
            require(done.outcome==outcome(result),"Finish handoff differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Finish ordered writes/complete memory differ");
            require(operation.advance(19,bus,copies)==0 && operation.snapshot()==done,"Finished finish changed state");
            dispatches+=done.dispatchedInstructions;++replays;
        }
        totalWrites+=writes.size();
        if (result<=3) for (size_t target=0;target<targets.size();++target) if (!irqSeen[target]) {
            const auto [cs,ip,ds]=targets[target];
            if (std::any_of(trace.begin(),trace.end(),[=](const auto& r) { return r.cs==cs && r.ip==ip && (!ds || r.ds==ds); })) {
                const auto actor=std::find_if(trace.begin(),trace.end(),[](const auto& r) { return r.cs==0x1000 && r.ip==0x73e5; });
                const auto actorBp=actor==trace.end() ? endpoint.bp : actor->bp;
                const auto irq=irqCheck(FrameActorFinishOperation(entry,0x1000,0x200000),initial,endpoint,expected,result<2,actorBp,cs,ip,ds);
                irqStackSensitive+=irq.registerSensitive ? 1u : 0u;soundIrqs+=irq.soundActive ? 1u : 0u;
                irqTargetSensitive+=irq.targetLocalsSensitive ? 1u : 0u;
                irqInstructions+=irq.instructions;irqSeen[target]=true;
            }
        }
    }
    if (input.at!=input.bytes.size() || !soundIrqs ||
            !std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; })) {
        std::cerr << "finish_tail=" << input.at << '/' << input.bytes.size()
            << " irq_register_sensitive=" << irqStackSensitive << " irq_target_locals_sensitive=" << irqTargetSensitive
            << " sound_irq_cases=" << soundIrqs << " missing_irq=";
        for (size_t i=0;i<targets.size();++i) if (!irqSeen[i]) std::cerr << std::hex << targets[i][0] << ':' << targets[i][1] << ' ';
        std::cerr << std::dec << '\n';
    }
    require(input.at==input.bytes.size() && soundIrqs>0 &&
        std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),"Finish fixture tail/IRQ coverage differs");
    require(std::all_of(outcomes.begin(),outcomes.end(),[](unsigned n) { return n!=0; }) &&
        domains==std::array<unsigned,5>{238,796,2124,2412,566},"Finish coverage differs");
    std::cout << "actor_finish_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " computed_irq_cases=" << irqSeen.size()
        << " irq_register_sensitive=" << irqStackSensitive << " irq_target_locals_sensitive=" << irqTargetSensitive
        << " sound_irq_cases=" << soundIrqs << " irq_instructions=" << irqInstructions
        << " one_grant=" << oneGrant
        << " later_state_injected=0 tile_behavior_executed=0 motion_integration_executed=1 actor_near_return_executed=1 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3f9e;r.bp=0x3fdc;r.ip=0x73e5;r.flags=2;
    unsigned rejected=0;
    for (unsigned variant=0;variant<4;++variant) {
        auto wrong=r;if (variant==0) ++wrong.cs;if (variant==1) ++wrong.ds;if (variant==2) wrong.ip=0;
        try { ActorFinishOperation invalid(wrong,0x1000,variant==3 ? 1 : 0); } catch (const std::invalid_argument&) { ++rejected; }
    }
    auto invalid=FrameActorFinishOperation(r,0x1000,0).snapshot();++invalid.gameSegment;
    try { FrameActorFinishOperation operation(invalid); } catch (const std::invalid_argument&) { ++rejected; }
    require(rejected==5,"Finish accepted invalid entry/callee ownership");
    Memory memory;const auto bus=memory.bus();const auto copies=[](uint16_t n) { return n; };
    unsigned profiles=0,profileRejections=0;
    for (uint16_t ip : {uint16_t{0x73e5},uint16_t{0x654e},uint16_t{0x6053},uint16_t{0x7903},uint16_t{0x7a57},uint16_t{0x7ebb},uint16_t{0x615a}}) {
        auto entry=r;entry.ip=ip;
        const auto construct=[&](uint32_t mask) {
            return ip==0x7903 ? FrameActorFinishOperation(entry,0x140,0x160,0x900,0x1000,mask) :
                FrameActorFinishOperation(entry,0x1000,mask);
        };
        for (uint32_t mask : {uint32_t{0},uint32_t{0x200000}}) {
            auto accepted=construct(mask);const auto initial=accepted.snapshot();
            require(accepted.registers()==entry,"Finish constructor changed entry registers");
            require(accepted.advance(0,bus,copies)==0 && accepted.snapshot()==initial && memory.writes.empty(),"Finish zero budget changed state");
            accepted=FrameActorFinishOperation(initial);
            require(accepted.snapshot()==initial && accepted.registers()==entry,"Finish profile snapshot differs");
            bool blocked=false;try { accepted.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
            require(blocked && accepted.snapshot()==initial && memory.writes.empty(),"Finish masked IRQ changed state");++profiles;
        }
        for (uint32_t mask : {uint32_t{1},uint32_t{0x1fffff},uint32_t{0x200001},uint32_t{0x80000000},uint32_t{0xffffffff}}) {
            bool blocked=false;try { auto wrong=construct(mask);(void)wrong; } catch (const std::invalid_argument&) { blocked=true; }
            require(blocked,"Finish constructor accepted unsupported ID mask");++profileRejections;
            auto wrong=construct(0).snapshot();wrong.idToggleMask=mask;
            std::visit([&](auto& child) { child.idToggleMask=mask; },wrong.callee);
            blocked=false;try { FrameActorFinishOperation restored(wrong); } catch (const std::invalid_argument&) { blocked=true; }
            require(blocked,"Finish snapshot accepted unsupported ID mask");++profileRejections;
        }
    }
    require(profiles==14 && profileRejections==70 && memory.writes.empty(),"Finish constructor coverage differs");
    Memory irqMemory;const auto irqBus=irqMemory.bus();r.flags=0x202;
    ActorFinishOperation active(r,0x1000,0);active.deliverTimerInterrupt(irqBus);const auto irq=active.snapshot();
    require(ActorFinishOperation(irq).interruptInProgress(),"Finish IRQ snapshot lost ownership");
    unsigned irqRejections=0;
    for (unsigned variant=0;variant<6;++variant) {
        auto wrong=irq;
        if (variant==0) wrong.outcome=ActorFinishOutcome::Returned;
        if (variant==1) ++wrong.timer->gameSegment;
        if (variant==2) ++wrong.timer->dataSegment;
        if (variant==3) wrong.timer->idToggleMask=0x200000;
        if (variant==4) wrong.timer->biosWrapper=false;
        if (variant==5) wrong.timer->returned=true;
        try { ActorFinishOperation restored(wrong); } catch (const std::invalid_argument&) { ++irqRejections; }
    }
    require(irqRejections==6,"Finish accepted malformed IRQ ownership");
    auto borrowed=ActorFinishOperation(r,0x1000,0).snapshot();
    borrowed.registers.cs=0x1920;borrowed.registers.ip=0x91f;borrowed.registers.ds=borrowed.registers.ss;
    require(ActorFinishOperation(borrowed).registers()==borrowed.registers,"Move snapshot rejected borrowed DS");
    std::cout << "actor_finish_unit=ok entry_rejections=5 constructor_profiles=14 profile_rejections=70 irq_rejections=6 borrowed_ds=1 live_stack=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();else {
            require(argc==3 || (argc==4 && std::string(argv[3])=="--one-grant"),"Expected finish fixture and original root");
            replay(argv[1],argv[2],argc==4);
        }
        return 0;
    }
    catch (const std::exception& error) { std::cerr << "actor_finish=failed " << error.what() << '\n';return 1; }
}
