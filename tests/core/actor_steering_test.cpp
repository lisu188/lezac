#include "core/actor_steering.hpp"

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
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing steering input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated steering fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t n) {
        std::vector<DosGetTimeRegisters> rows;rows.reserve(n);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<n;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i!=0 || mask==0x3fff),"Steering register delta mask differs");
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected steering IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected steering IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Steering MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,"Steering MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Steering relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row) {
    const bool flags=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    const auto actualFlags=actual.flags;actual.flags=expected.flags;
    if (!flags || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " bx=" << actual.bx << '/' << expected.bx << " cx=" << actual.cx << '/' << expected.cx
            << " dx=" << actual.dx << '/' << expected.dx << " sp=" << actual.sp << '/' << expected.sp
            << " flags=" << actualFlags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Steering register/control trace differs");
    }
}
uint64_t irqCheck(ActorSteeringOperation operation,Memory memory) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    const auto before=operation.registers();operation.deliverTimerInterrupt(bus);bool nested=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && operation.snapshot().cpu.timerDeliveries==1,"Steering IRQ nesting/accounting differs");
    unsigned steps=0;
    while (operation.interruptInProgress()) {
        require(steps++<4096,"Steering IRQ did not return");operation.advance(1,bus,all);operation=ActorSteeringOperation(operation.snapshot());
    }
    require(operation.registers()==before && memory.word(0x40,0x6c)==101,"Steering IRQ did not restore CPU/clock");
    auto other=operation;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!operation.finished()) { require(steps++<3000000,"Steering IRQ continuation stalled");operation.advance(1,bus,all); }
    while (!other.finished()) { require(steps++<6000000,"Steering IRQ alternate stalled");other.advance(17,otherBus,all);other=ActorSteeringOperation(other.snapshot()); }
    require(operation.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Steering IRQ continuation grant/snapshot differs");
    bool ended=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished steering admitted IRQ");return operation.snapshot().cpu.timerInstructions;
}
void replay(const char* path,const char* root,bool oneGrant) {
    Reader input{read(path)};for (char c : std::string("LZSTEER1")) require(input.number(1)==static_cast<uint8_t>(c),"Steering magic differs");
    const auto count=input.number(4);require(count==3736,"Steering corpus domain differs");const auto base=image(root);
    uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0,irqInstructions=0;
    std::array<unsigned,2> outcomes{};std::array<unsigned,3> domains{};
    constexpr std::array<std::array<uint16_t,2>,14> targets{{
        {{0x1000,0x346b}},{{0x1000,0x3471}},{{0x1000,0x3480}},{{0x1000,0x34cf}},
        {{0x1000,0x3519}},{{0x1000,0x3531}},{{0x1000,0x3556}},{{0x1000,0x3584}},{{0x1000,0x7126}},
        {{0x1920,0xfc2}},{{0x1920,0xfe3}},{{0x1920,0xff8}},{{0x1920,0x1017}},{{0x1920,0x101e}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Steering case index differs");const auto result=input.number(4),domain=input.number(4);
        require(result<outcomes.size() && domain<domains.size(),"Steering outcome/domain differs");++outcomes[result];++domains[domain];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
        require(seeds<64,"Steering seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Steering seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>1 && states<3000000,"Steering trace reserve differs");
        const auto trace=input.trace(states);require(trace.front()==entry && trace.back()==endpoint,"Steering trace endpoints differ");
        const auto written=input.number(4);require(written<300000,"Steering write reserve differs");
        auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Steering write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        const auto mode=static_cast<ActorSteeringEntry>(domain);
        for (uint64_t budget : {1u,17u,4096u}) {
            if (oneGrant && budget!=1) continue;
            auto memory=initial;const auto bus=memory.bus();ActorSteeringOperation operation(entry,0x1000,0x200000,mode);
            const auto before=operation.snapshot();const auto all=[](uint16_t n) { return n; };
            require(operation.advance(0,bus,all)==0 && operation.snapshot()==before && memory.writes.empty(),"Zero steering budget changed state");
            size_t cursor=0;compare(operation.registers(),trace.at(0),index,0);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus,all);require(used>0 && used<=budget,"Steering dispatch grant differs");
                cursor+=used;require(cursor<trace.size(),"Steering exceeded original endpoint");
                operation=ActorSteeringOperation(operation.snapshot());compare(operation.registers(),trace[cursor],index,cursor);++comparisons;
            }
            const auto done=operation.snapshot();
            require(cursor+1==trace.size() && operation.registers()==endpoint,"Steering endpoint/all flags differ");
            require(done.outcome==(result==0 ? ActorSteeringOutcome::Returned : ActorSteeringOutcome::RuntimeError),"Steering return/error differs");
            require(done.cpu.dispatchedInstructions==cursor && done.cpu.timerDeliveries==0 && done.cpu.transferredBytes==0,"Steering accounting differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Steering ordered writes/complete memory differ");
            require(operation.advance(19,bus,all)==0 && operation.snapshot()==done,"Finished steering changed state");
            dispatches+=done.cpu.dispatchedInstructions;++replays;
        }
        totalWrites+=writes.size();
        if (!std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; })) {
            auto memory=initial;const auto bus=memory.bus();ActorSteeringOperation operation(entry,0x1000,0x200000,mode);
            unsigned steps=0;
            while (!operation.finished()) {
                require(steps++<3000000,"Steering IRQ seek stalled");const auto r=operation.registers();
                for (size_t i=0;i<targets.size();++i) if (!irqSeen[i] && r.cs==targets[i][0] && r.ip==targets[i][1] && (r.flags&0x200u)) {
                    irqInstructions+=irqCheck(operation,memory);irqSeen[i]=true;
                }
                operation.advance(1,bus,[](uint16_t n) { return n; });
            }
        }
    }
    require(input.at==input.bytes.size() && domains==std::array<unsigned,3>{2136,64,1536} &&
        std::all_of(outcomes.begin(),outcomes.end(),[](unsigned n) { return n!=0; }) &&
        std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),"Steering coverage/tail differs");
    std::cout << "actor_steering_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " computed_irq_cases=" << targets.size()
        << " irq_instructions=" << irqInstructions << " one_grant=" << oneGrant
        << " live_caller_cases=64 square_root_cases=1536 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3f8c;r.bp=0x3fdc;r.ip=0x346b;r.flags=2;
    Memory memory;ActorSteeringOperation operation(r,0x1000,0x200000,ActorSteeringEntry::Vector);
    const auto before=operation.snapshot();const auto all=[](uint16_t n) { return n; };
    require(operation.advance(0,memory.bus(),all)==0 && operation.snapshot()==before,"Zero steering unit budget changed state");
    bool masked=false;try { operation.deliverTimerInterrupt(memory.bus()); } catch (const std::logic_error&) { masked=true; }
    require(masked && memory.writes.empty() && operation.snapshot()==before,"Masked steering IRQ changed state");
    for (unsigned mutation=0;mutation<7;++mutation) {
        bool rejected=false;
        try {
            if (mutation==0) { auto other=r;other.cs=0x1920;ActorSteeringOperation invalid(other,0x1000,0x200000,ActorSteeringEntry::Vector); }
            if (mutation==1) { auto other=r;other.ds=0;ActorSteeringOperation invalid(other,0x1000,0x200000,ActorSteeringEntry::Vector); }
            if (mutation==2) { auto other=r;other.ip=0x346c;ActorSteeringOperation invalid(other,0x1000,0x200000,ActorSteeringEntry::Vector); }
            if (mutation==3) { ActorSteeringOperation invalid(r,0x1000,1,ActorSteeringEntry::Vector); }
            if (mutation==4) { auto state=before;state.entry=static_cast<ActorSteeringEntry>(99);ActorSteeringOperation invalid(state); }
            if (mutation==5) { auto state=before;state.outcome=ActorSteeringOutcome::RuntimeError;ActorSteeringOperation invalid(state); }
            if (mutation==6) { auto state=before;state.cpu.outcome=ActorFinishOutcome::Returned;ActorSteeringOperation invalid(state); }
        } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected,"Invalid steering entry/snapshot was admitted");
    }
    Reader bad{{0,0}};bool rejected=false;try { (void)bad.trace(1); } catch (const std::runtime_error&) { rejected=true; }
    require(rejected,"Partial first delta row was admitted");
    std::cout << "actor_steering_unit=ok entry_state_rejections=7 masked_irq=1 invalid_delta=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==3 || (argc==4 && std::string(argv[3])=="--one-grant"),"Steering replay arguments differ");replay(argv[1],argv[2],argc==4); }
        return 0;
    } catch (const std::exception& e) { std::cerr << "actor_steering=failed " << e.what() << '\n';return 1; }
}
