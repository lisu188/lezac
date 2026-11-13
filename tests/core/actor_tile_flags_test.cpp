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
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing tile flags input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Write { uint32_t address;uint8_t size;uint16_t value;bool operator==(const Write&) const = default; };
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated tile flags fixture");
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected tile IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected tile IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe{read(root/"LEZAC.EXE")};require(exe.bytes.size()>28 && exe.number(2)==0x5a4d,"Tile MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,"Tile MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(2),segment=exe.number(2),at=0x10000+segment*16+offset;
        require(at+1<result.bytes.size(),"Tile relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
// Test-only continuous composition: no memory/register injection at the handoff.
struct Execution {
    std::optional<FrameActorContactOperation> prefix;
    std::optional<ActorTileFlagsOperation> tile;
    uint64_t dispatched=0;
    explicit Execution(DosGetTimeRegisters r) {
        if (r.ip==0x65a2) tile.emplace(r,uint16_t{0x1000},uint32_t{0x200000});
        else prefix.emplace(r,uint16_t{0x1000},uint32_t{0x200000});
    }
    DosGetTimeRegisters registers() const { return tile ? tile->registers() : prefix->registers(); }
    bool finished() const { return tile && tile->finished(); }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,uint16_t limit) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (tile) {
                require(tile->advance(1,bus)==1,"Tile failed to dispatch");
                tile=ActorTileFlagsOperation(tile->snapshot());
            } else {
                require(prefix->advance(1,bus,[=](uint16_t n) { return std::min(n,limit); })==1,"Tile prefix failed to dispatch");
                prefix=FrameActorContactOperation(prefix->snapshot());
                if (prefix->finished()) {
                    require(prefix->snapshot().outcome==FrameActorContactOutcome::TileBehavior,"Tile prefix did not reach classifier");
                    tile.emplace(prefix->registers(),uint16_t{0x1000},uint32_t{0x200000});
                }
            }
            ++used;++dispatched;
        }
        return used;
    }
};
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,bool exactFlags) {
    const bool flags=((actual.flags^expected.flags)&(exactFlags ? ~uint32_t{0} : ~uint32_t{0x8d5}))==0;
    const auto actualFlags=actual.flags;actual.flags=expected.flags;
    if (!flags || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " flags=" << actualFlags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Tile register/flag trace differs");
    }
}
uint64_t irqCheck(ActorTileFlagsOperation operation,Memory memory) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;
    const auto bus=memory.bus();const auto before=operation.registers();
    operation.deliverTimerInterrupt(bus);bool nested=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && operation.snapshot().timerDeliveries==1,"Tile IRQ nesting/accounting differs");
    unsigned steps=0;
    while (operation.interruptInProgress()) {
        require(steps++<4096,"Tile IRQ did not return");operation.advance(1,bus);operation=ActorTileFlagsOperation(operation.snapshot());
    }
    require(operation.registers()==before && memory.word(0x40,0x6c)==101,"Tile IRQ did not restore CPU/clock");
    auto other=operation;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!operation.finished()) { require(steps++<8192,"Tile IRQ continuation stalled");operation.advance(1,bus); }
    while (!other.finished()) { require(steps++<8192,"Tile IRQ alternate stalled");other.advance(17,otherBus);other=ActorTileFlagsOperation(other.snapshot()); }
    require(operation.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Tile IRQ continuation grant/snapshot differs");
    bool ended=false;try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished tile admitted IRQ");return operation.snapshot().timerInstructions;
}
void replay(const char* path,const char* root,bool oneGrant) {
    Reader input{read(path)};for (char c : std::string("LZTILE01")) require(input.number(1)==static_cast<uint8_t>(c),"Tile magic differs");
    const auto count=input.number(4);require(count==5972,"Tile corpus domain differs");const auto base=image(root);
    uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0,irqInstructions=0;
    std::array<unsigned,3> outcomes{};std::array<unsigned,2> domains{};
    constexpr std::array<uint16_t,12> targets{0x65a2,0x65da,0x65e5,0x65ee,0x6643,0x666b,0x6691,0x66fa,0x670f,0x6717,0x672c,0x6734};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Tile case index differs");const auto result=input.number(4),domain=input.number(4);
        require(result<outcomes.size() && domain<domains.size(),"Tile outcome/domain differs");++outcomes[result];++domains[domain];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
        require(seeds<2000,"Tile seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto at=input.number(4),size=input.number(4);
            require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Tile seed exceeds memory");
            std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
        }
        const auto states=input.number(4);require(states>1 && states<100000,"Tile trace reserve differs");
        const auto trace=input.trace(states);const auto written=input.number(4);require(written<300000,"Tile write reserve differs");
        auto expected=initial;std::vector<Write> writes;
        for (unsigned i=0;i<written;++i) {
            const auto at=input.number(4),size=input.number(1),value=input.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Tile write exceeds memory");
            expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
        }
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            if (oneGrant && (limit!=65535 || budget!=1)) continue;
            auto memory=initial;const auto bus=memory.bus();Execution operation(entry);
            require(operation.advance(0,bus,limit)==0 && operation.dispatched==0 && memory.writes.empty(),"Zero tile budget changed state");
            size_t cursor=0;compare(operation.registers(),trace.at(0),index,0,domain==0);++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus,limit);require(used>0 && used<=budget,"Tile dispatch grant differs");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Tile exceeded original endpoint");const auto before=trace[cursor];
                    if (before.cs==0x1920 && before.ip==0x91f && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Tile REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                require(cursor<trace.size(),"Tile trace exhausted");const auto& row=trace[cursor];
                compare(operation.registers(),row,index,cursor,domain==0 || (row.cs==0x1000 && row.ip>=0x65a6 && row.ip<=0x6737) || row.ip==0x7018);++comparisons;
            }
            const auto done=operation.tile->snapshot();
            require(cursor+1==trace.size() && operation.registers()==endpoint,"Tile endpoint/all flags differ");
            constexpr std::array results{ActorTileFlagsOutcome::Expiry,ActorTileFlagsOutcome::Motion,ActorTileFlagsOutcome::Behavior};
            require(done.outcome==results.at(result),"Tile handoff differs");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Tile ordered writes/complete memory differ");
            require(operation.advance(19,bus,limit)==0 && operation.tile->snapshot()==done,"Finished tile changed state");
            dispatches+=operation.dispatched;++replays;
        }
        totalWrites+=writes.size();
        if (domain==0 && (entry.flags&0x200u) && entry.bp==0x3fdc) {
            auto memory=initial;const auto bus=memory.bus();ActorTileFlagsOperation operation(entry,0x1000,0x200000);
            while (!operation.finished()) {
                for (size_t i=0;i<targets.size();++i) if (!irqSeen[i] && operation.registers().ip==targets[i]) {
                    irqInstructions+=irqCheck(operation,memory);irqSeen[i]=true;
                }
                operation.advance(1,bus);
            }
        }
    }
    require(input.at==input.bytes.size() && domains==std::array<unsigned,2>{5932,40} &&
        std::all_of(outcomes.begin(),outcomes.end(),[](unsigned n) { return n!=0; }) &&
        std::all_of(irqSeen.begin(),irqSeen.end(),[](bool yes) { return yes; }),"Tile coverage/tail differs");
    std::cout << "actor_tile_flags_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " computed_irq_cases=" << targets.size()
        << " irq_instructions=" << irqInstructions << " one_grant=" << oneGrant
        << " continuous_actor_cases=40 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3000;r.bp=0x3fdc;r.ip=0x65a2;r.flags=2;
    unsigned rejected=0;
    for (unsigned variant=0;variant<4;++variant) {
        auto wrong=r;if (variant==0) ++wrong.cs;if (variant==1) ++wrong.ds;if (variant==2) wrong.ip=0;
        try { ActorTileFlagsOperation invalid(wrong,0x1000,variant==3 ? 1 : 0); } catch (const std::invalid_argument&) { ++rejected; }
    }
    for (auto outcome : {ActorTileFlagsOutcome::Expiry,ActorTileFlagsOutcome::Motion,ActorTileFlagsOutcome::Behavior}) {
        auto wrong=ActorTileFlagsOperation(r,0x1000,0).snapshot();wrong.outcome=outcome;
        try { ActorTileFlagsOperation invalid(wrong); } catch (const std::invalid_argument&) { ++rejected; }
    }
    Memory memory;const auto bus=memory.bus();ActorTileFlagsOperation operation(r,0x1000,0);bool masked=false;
    try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { masked=true; }
    require(rejected==7 && masked && memory.writes.empty(),"Tile ownership/masked IRQ rejection differs");
    std::cout << "actor_tile_flags_unit=ok entry_state_rejections=7 masked_irq=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==3 || (argc==4 && std::string(argv[3])=="--one-grant"),"Tile replay arguments differ");replay(argv[1],argv[2],argc==4); }
        return 0;
    } catch (const std::exception& e) { std::cerr << "actor_tile_flags=failed " << e.what() << '\n';return 1; }
}
