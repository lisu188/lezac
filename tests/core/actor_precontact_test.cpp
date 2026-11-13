#include "core/actor_precontact.hpp"

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
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing precontact input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Write {
    uint32_t address;uint8_t size;uint16_t value;
    bool operator==(const Write&) const = default;
};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated precontact fixture");
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected precontact IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61,"Unexpected precontact IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Precontact MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;
    exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,"Precontact MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(2),segment=exe.number(2),at=0x10000+segment*16+offset;
        require(at+1<result.bytes.size(),"Precontact relocation exceeds memory");
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
        throw std::runtime_error("Precontact register/control trace differs");
    }
}
FrameActorPrecontactOutcome outcome(uint32_t value) {
    constexpr std::array values{FrameActorPrecontactOutcome::BehaviorDispatch,FrameActorPrecontactOutcome::TransientQueues,
        FrameActorPrecontactOutcome::Restart,FrameActorPrecontactOutcome::EndRunUi,FrameActorPrecontactOutcome::RuntimeError};
    return values.at(value);
}
bool irqCheck(FrameActorPrecontactOperation operation,Memory memory,
        DosGetTimeRegisters endpoint,uint16_t cs,uint16_t ip) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;
    const auto bus=memory.bus();const auto copies=[](uint16_t n) { return n; };unsigned steps=0;
    while (!operation.finished() && !(operation.registers().cs==cs && operation.registers().ip==ip)) {
        require(steps++<3000000,"Precontact IRQ target missing");operation.advance(1,bus,copies);
    }
    require(!operation.finished(),"Precontact IRQ target already finished");
    const auto beforeRegisters=operation.registers();const auto beforeBytes=memory.bytes;
    operation.deliverTimerInterrupt(bus);
    require(operation.interruptInProgress(),"Precontact IRQ not admitted");bool nested=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested,"Nested precontact IRQ admitted");
    while (operation.interruptInProgress()) {
        require(steps++<3000000,"Precontact IRQ did not return");operation.advance(1,bus,copies);
        operation=FrameActorPrecontactOperation(operation.snapshot());
    }
    require(operation.registers()==beforeRegisters,"Precontact IRQ did not restore immediate CPU context");
    require(std::equal(memory.bytes.begin()+0xa0000,memory.bytes.begin()+0xb0001,beforeBytes.begin()+0xa0000),"Precontact IRQ handler changed VGA");
    require(std::equal(memory.bytes.begin()+0x1aa20+0x1b88,memory.bytes.begin()+0x1aa20+0x2048,
        beforeBytes.begin()+0x1aa20+0x1b88),"Precontact IRQ handler changed physical actors");
    require(std::equal(memory.bytes.begin()+0x50000,memory.bytes.begin()+0x60000,beforeBytes.begin()+0x50000),"Precontact IRQ handler changed far actors");
    auto reference=operation;auto referenceMemory=memory;const auto referenceBus=referenceMemory.bus();
    while (!reference.finished()) {
        require(steps++<3000000,"Precontact IRQ reference continuation did not finish");reference.advance(1,referenceBus,copies);
    }
    while (!operation.finished()) {
        require(steps++<3000000,"Precontact IRQ continuation did not finish");operation.advance(17,bus,copies);
        operation=FrameActorPrecontactOperation(operation.snapshot());
    }
    const auto& final=operation.snapshot();
    uint64_t instructions=final.entryTimerInstructions,deliveries=final.entryTimerDeliveries;
    if (const auto* child=std::get_if<ActorPrecontactSnapshot>(&final.callee)) {
        instructions+=child->timerInstructions;deliveries+=child->timerDeliveries;
    }
    require(operation.snapshot()==reference.snapshot() && memory.bytes==referenceMemory.bytes &&
        memory.writes==referenceMemory.writes,"Precontact IRQ continuation grant/snapshot differs");
    require(instructions==36 && deliveries==1 && memory.word(0x40,0x6c)==101,"Precontact IRQ accounting/context differs");
    bool ended=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished precontact admitted IRQ");
    return operation.registers()!=endpoint;
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};for (char c : std::string("LZPREP01")) require(input.number(1)==static_cast<uint8_t>(c),"Precontact magic differs");
    const auto count=input.number(4);require(count==3158,"Precontact corpus domain differs");const auto base=image(root);
    uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0;unsigned irqStackSensitive=0;
    std::array<unsigned,5> outcomes{};std::array<unsigned,3> domains{};
    constexpr std::array<std::array<uint16_t,2>,14> targets{{
        {{0x1000,0x7a57}},{{0x1000,0x7ec2}},{{0x1000,0x432a}},{{0x1000,0x6053}},{{0x1920,0x91f}},
        {{0x1000,0x615a}},{{0x1000,0x6253}},{{0x1000,0x6381}},{{0x1000,0x5872}},
        {{0x1000,0x58c2}},{{0x1000,0x5a75}},{{0x1000,0x6449}},{{0x1920,0x13a8}},{{0x1000,0x6500}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Precontact case index differs");const auto result=input.number(4),domain=input.number(4);
        require(result<outcomes.size() && domain<domains.size(),"Precontact outcome/domain differs");++outcomes[result];++domains[domain];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
        require(seeds<2000,"Precontact seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Precontact seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>1 && states<3000000,"Precontact trace reserve differs");
        const auto trace=input.trace(states);const auto written=input.number(4);require(written<300000,"Precontact write reserve differs");
        auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Precontact write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();FrameActorPrecontactOperation operation(entry,0x1000,0x200000);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };const auto zero=operation.snapshot();
            require(operation.advance(0,bus,copies)==0 && operation.snapshot()==zero && memory.writes.empty(),"Zero precontact budget changed state");
            size_t cursor=0;uint64_t consumed=0;compare(operation.registers(),trace.at(0),index,0);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus,copies);require(used>0 && used<=budget,"Precontact dispatch grant differs");
                consumed+=used;require(operation.snapshot().dispatchedInstructions==consumed,"Precontact dispatch accounting differs");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Precontact exceeded original endpoint");const auto before=trace[cursor];
                    if (((before.cs==0x1000 && (before.ip==0x116a || before.ip==0x7ec)) ||
                            (before.cs==0x1920 && before.ip==0x91f)) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Precontact REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                require(cursor<trace.size(),"Precontact trace exhausted");compare(operation.registers(),trace[cursor],index,cursor);++comparisons;
                operation=FrameActorPrecontactOperation(operation.snapshot());
            }
            const auto done=operation.snapshot();
            require(cursor+1==trace.size() && operation.registers()==endpoint,"Precontact endpoint/all flags differ");
            require(done.outcome==outcome(result),"Precontact handoff differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Precontact ordered writes/complete memory differ");
            require(operation.advance(19,bus,copies)==0 && operation.snapshot()==done,"Finished precontact changed state");
            dispatches+=done.dispatchedInstructions;++replays;
        }
        totalWrites+=writes.size();
        if (result==0 || result==1 || result==2) for (size_t target=0;target<targets.size();++target) if (!irqSeen[target]) {
            const auto [cs,ip]=targets[target];
            if (std::any_of(trace.begin(),trace.end(),[=](const auto& r) { return r.cs==cs && r.ip==ip; })) {
                irqStackSensitive+=irqCheck(FrameActorPrecontactOperation(entry,0x1000,0x200000),initial,endpoint,cs,ip) ? 1u : 0u;irqSeen[target]=true;
            }
        }
    }
    require(input.at==input.bytes.size() && irqStackSensitive>0 && std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),"Precontact fixture tail/IRQ coverage differs");
    require(std::all_of(outcomes.begin(),outcomes.end(),[](unsigned n) { return n!=0; }) && domains==std::array<unsigned,3>{238,796,2124},"Precontact coverage differs");
    std::cout << "actor_precontact_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " computed_irq_cases=" << irqSeen.size()
        << " irq_register_sensitive=" << irqStackSensitive
        << " later_state_injected=0 after_654e_executed=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3f9e;r.bp=0x3fdc;r.ip=0x615a;r.flags=2;
    unsigned rejected=0;
    for (unsigned variant=0;variant<4;++variant) {
        auto wrong=r;if (variant==0) ++wrong.cs;if (variant==1) ++wrong.ds;if (variant==2) wrong.ip=0;
        try { ActorPrecontactOperation invalid(wrong,0x1000,variant==3 ? 1 : 0); } catch (const std::invalid_argument&) { ++rejected; }
    }
    auto invalid=FrameActorPrecontactOperation(r,0x1000,0).snapshot();++invalid.gameSegment;
    try { FrameActorPrecontactOperation operation(invalid); } catch (const std::invalid_argument&) { ++rejected; }
    require(rejected==5,"Precontact accepted invalid entry/callee ownership");
    Memory memory;const auto bus=memory.bus();FrameActorPrecontactOperation operation(r,0x1000,0);
    const auto before=operation.snapshot();const auto copies=[](uint16_t n) { return n; };
    unsigned profiles=0,profileRejections=0;
    for (uint16_t ip : {uint16_t{0x6053},uint16_t{0x7903},uint16_t{0x7a57},uint16_t{0x7ebb},uint16_t{0x615a}}) {
        auto entry=r;entry.ip=ip;
        const auto construct=[&](uint32_t mask) {
            return ip==0x7903 ? FrameActorPrecontactOperation(entry,0x140,0x160,0x900,0x1000,mask) :
                FrameActorPrecontactOperation(entry,0x1000,mask);
        };
        for (uint32_t mask : {uint32_t{0},uint32_t{0x200000}}) {
            auto accepted=construct(mask);const auto initial=accepted.snapshot();
            require(accepted.registers()==entry,"Precontact constructor changed entry registers");
            require(accepted.advance(0,bus,copies)==0 && accepted.snapshot()==initial && memory.writes.empty(),
                "Precontact profile zero budget changed state");
            accepted=FrameActorPrecontactOperation(initial);
            require(accepted.snapshot()==initial && accepted.registers()==entry,"Precontact profile snapshot differs");
            bool blocked=false;try { accepted.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
            require(blocked && accepted.snapshot()==initial && memory.writes.empty(),"Precontact profile masked IRQ changed state");
            ++profiles;
        }
        for (uint32_t mask : {uint32_t{1},uint32_t{0x1fffff},uint32_t{0x200001},uint32_t{0x80000000},uint32_t{0xffffffff}}) {
            bool blocked=false;try { auto wrong=construct(mask);(void)wrong; } catch (const std::invalid_argument&) { blocked=true; }
            require(blocked,"Precontact constructor accepted unsupported ID mask");++profileRejections;
            auto wrong=construct(0).snapshot();wrong.idToggleMask=mask;
            std::visit([&](auto& child) { child.idToggleMask=mask; },wrong.callee);
            blocked=false;try { FrameActorPrecontactOperation restored(wrong); } catch (const std::invalid_argument&) { blocked=true; }
            require(blocked,"Precontact snapshot accepted unsupported ID mask");++profileRejections;
        }
    }
    require(profiles==10 && profileRejections==50 && memory.writes.empty(),"Precontact constructor profile coverage differs");
    require(operation.advance(0,bus,copies)==0 && operation.snapshot()==before && memory.writes.empty(),"Zero precontact budget changed state");
    bool masked=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { masked=true; }
    require(masked && operation.snapshot()==before && memory.writes.empty(),"Masked precontact admitted IRQ");
    r.ip=0x7903;FrameActorPrecontactOperation full(r,0x140,0x160,0x900,0x1000,0);
    const auto fullBefore=full.snapshot();
    require(full.advance(0,bus,copies)==0 && full.snapshot()==fullBefore && memory.writes.empty(),"Zero full-prefix precontact budget changed state");
    std::cout << "actor_precontact_unit=ok entry_rejections=5 live_stack=1 masked_irq_rejected=1 full_prefix_constructor=1"
        << " constructor_profiles=" << profiles << " profile_rejections=" << profileRejections << '\n';
}
}
int main(int argc,char** argv) {
    try { if (argc==1) unit();else { require(argc==3,"Expected precontact fixture and original root");replay(argv[1],argv[2]); }return 0; }
    catch (const std::exception& error) { std::cerr << "actor_precontact=failed " << error.what() << '\n';return 1; }
}
