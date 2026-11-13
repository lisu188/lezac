#include "core/actor_tile_flags.hpp"
#include "core/player_motion.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <optional>
#include <string>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool yes,const char* message) { if (!yes) throw std::runtime_error(message); }
constexpr uint16_t kGameSegment=0x1000;
constexpr uint32_t kIdToggleMask=0x200000;
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    explicit Reader(const std::filesystem::path& path) {
        std::ifstream in(path,std::ios::binary);require(in.good(),"Missing player fixture");
        bytes={std::istreambuf_iterator<char>(in),std::istreambuf_iterator<char>()};
    }
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated player fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace() {
        const auto count=number(4);require(count>1 && count<=3000000,"Player trace reserve differs");
        std::vector<DosGetTimeRegisters> rows;rows.reserve(count);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<count;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i || mask==0x3fff),"Player delta mask differs");
            for (unsigned c=0;c<members.size();++c)
                if (mask&(1u<<c)) previous.*members[c]=static_cast<uint16_t>(number(2));
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected player IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected player IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    const auto path=root/"LEZAC.EXE";
    require(std::filesystem::file_size(path)==52384,"Player MZ size differs");
    Reader exe(path);uint64_t hash=14695981039346656037ull;
    for (uint8_t byte : exe.bytes) { hash^=byte;hash*=1099511628211ull; }
    require(hash==0x2ae32f89b95e200bull,"Player MZ fingerprint differs");
    require(exe.number(2)==0x5a4d,"Player MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header && exe.bytes.size()-header+0x10000<=1048576,
        "Player MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Player relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,bool endpoint=false) {
    const auto flags=actual.flags;
    const bool defined=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    if (!endpoint) actual.flags=expected.flags;
    if (!defined || actual!=expected) {
        std::cerr<<"case="<<index<<" row="<<row<<" actual="<<std::hex<<actual.cs<<':'<<actual.ip
            <<" expected="<<expected.cs<<':'<<expected.ip<<" ax="<<actual.ax<<'/'<<expected.ax
            <<" bx="<<actual.bx<<'/'<<expected.bx<<" dx="<<actual.dx<<'/'<<expected.dx
            <<" sp="<<actual.sp<<'/'<<expected.sp<<" bp="<<actual.bp<<'/'<<expected.bp
            <<" flags="<<flags<<'/'<<expected.flags<<std::dec<<'\n';
        throw std::runtime_error("Player register/control trace differs");
    }
}
struct Driver {
    std::optional<FrameActorContactOperation> prefix;
    std::optional<ActorTileFlagsOperation> tiles;
    std::optional<PlayerMotionOperation> player;
    explicit Driver(DosGetTimeRegisters r) {
        if (r.ip==0x6737) player.emplace(r,kGameSegment,kIdToggleMask);
        else prefix.emplace(r,kGameSegment,kIdToggleMask);
    }
    DosGetTimeRegisters registers() const { return player ? player->registers() : tiles ? tiles->registers() : prefix->registers(); }
    bool finished() const { return player && player->finished(); }
    void restore() {
        if (player) player=PlayerMotionOperation(player->snapshot());
        else if (tiles) tiles=ActorTileFlagsOperation(tiles->snapshot());
        else prefix=FrameActorContactOperation(prefix->snapshot());
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const PlayerMotionOperation::CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (player) require(player->advance(1,bus,copies)==1,"Player did not dispatch");
            else if (tiles) {
                require(tiles->advance(1,bus)==1,"Player tile flags did not dispatch");
                if (tiles->finished()) {
                    require(tiles->snapshot().outcome==ActorTileFlagsOutcome::Motion,"Player bypassed motion");
                    player.emplace(tiles->registers(),kGameSegment,kIdToggleMask);
                }
            } else {
                require(prefix->advance(1,bus,copies)==1,"Player caller did not dispatch");
                if (prefix->finished()) {
                    const auto r=prefix->registers();
                    if (prefix->snapshot().outcome==FrameActorContactOutcome::TileBehavior) tiles.emplace(r,kGameSegment,kIdToggleMask);
                    else {
                        require(prefix->snapshot().outcome==FrameActorContactOutcome::RuntimeError,"Player caller bypassed body");
                        player.emplace(PlayerMotionSnapshot{ActorFinishSnapshot{r,0x1000,0x200000},PlayerMotionOutcome::RuntimeError});
                    }
                }
            }
            ++used;
        }
        return used;
    }
};
uint64_t irqCheck(PlayerMotionOperation active,Memory memory,bool partial) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    if (partial) {
        const auto before=active.registers();const auto writes=memory.writes.size();
        require(before.cx>1,"Player partial-copy IRQ lacks bytes");
        active.advance(1,bus,[](uint16_t) { return uint16_t{1}; });
        require(active.registers().ip==before.ip && active.registers().cx==before.cx-1 &&
            memory.writes.size()==writes+1,"Player partial copy did not transfer one byte");
    }
    const auto before=active.registers();const auto deliveries=active.snapshot().cpu.timerDeliveries;
    const auto instructions=active.snapshot().cpu.timerInstructions;
    active.deliverTimerInterrupt(bus);
    bool nested=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && active.snapshot().cpu.timerDeliveries==deliveries+1,"Player IRQ nesting/accounting differs");
    unsigned steps=0;
    while (active.interruptInProgress()) {
        require(steps++<4096,"Player IRQ did not return");active.advance(1,bus,all);
        active=PlayerMotionOperation(active.snapshot());
    }
    require(active.registers()==before && memory.word(0x40,0x6c)==101,"Player IRQ did not restore CPU/BIOS tick");
    auto other=active;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    const auto irqInstructions=active.snapshot().cpu.timerInstructions-instructions;
    while (!active.finished()) { require(steps++<3000000,"Player IRQ continuation stalled");active.advance(1,bus,all); }
    while (!other.finished()) {
        require(steps++<6000000,"Player IRQ alternate stalled");other.advance(17,otherBus,all);
        other=PlayerMotionOperation(other.snapshot());
    }
    require(active.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Player IRQ continuation grant/snapshot differs");
    bool ended=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended && irqInstructions>0,"Finished player admitted IRQ or IRQ did not dispatch");
    return irqInstructions;
}
void replay(const char* path,const char* root) {
    require(std::filesystem::file_size(path)==49667615,"Player corpus size differs");
    Reader input(path);
    require(input.bytes.size()==49667615,"Player corpus size differs");
    uint64_t hash=14695981039346656037ull;
    for (uint8_t byte : input.bytes) { hash^=byte;hash*=1099511628211ull; }
    require(hash==0xd893dad2e979faa6ull,"Player corpus fingerprint differs");
    for (char c : std::string("LZPLY001")) require(input.number(1)==static_cast<uint8_t>(c),"Player magic differs");
    const auto count=input.number(4);require(count==7028,"Player domain differs");const auto base=image(root);
    uint64_t comparisons=0,replays=0,dispatches=0,totalWrites=0,callers=0,irqInstructions=0;
    std::array<unsigned,3> outcomes{};
    constexpr std::array<std::array<uint16_t,2>,13> targets{{
        {{0x1000,0x6737}},{{0x1000,0x6807}},{{0x1000,0x6834}},{{0x1000,0x6a5e}},
        {{0x1000,0x6abb}},{{0x1000,0x6b52}},{{0x1000,0x6bd5}},{{0x1000,0x6cb3}},
        {{0x1000,0x6e42}},{{0x1000,0x6ff7}},{{0x1000,0x5715}},{{0x1000,0x5999}},{{0x1920,0x91f}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Player row order differs");const auto outcome=input.number(1);
        require(outcome<outcomes.size(),"Player outcome differs");++outcomes[outcome];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        callers+=entry.ip==0x7ebb;
        const auto seeds=input.number(4);require(seeds<65536,"Player seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto address=input.number(4),size=input.number(4);
            require(size<=65536 && address>=0x1aa20 && address+size<=1048576 && input.at+size<=input.bytes.size(),
                "Player seed exceeds memory");
            std::copy_n(input.bytes.begin()+input.at,size,initial.bytes.begin()+address);input.at+=size;
        }
        const auto trace=input.trace();compare(trace.front(),entry,index,0,true);
        const auto writeCount=input.number(4);require(writeCount<3000000,"Player write reserve differs");
        std::vector<Write> writes;auto expected=initial;
        for (unsigned i=0;i<writeCount;++i) {
            Write item{input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require((item.size==1 || item.size==2) && item.address+item.size<=1048576,"Player write exceeds memory");
            writes.push_back(item);expected.store(item.address,item.value,item.size);
        }
        require(input.number(4)==0,"Player reserved event field differs");
        unsigned mode=0;
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();Driver active(entry);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };
            size_t cursor=0;compare(active.registers(),trace.front(),index,0);++comparisons;
            while (!active.finished()) {
                require(cursor+1<trace.size(),"Player exceeded original endpoint");
                if (!mode && active.player) {
                    const auto r=active.registers();
                    for (size_t target=0;target<targets.size();++target)
                        if (!irqSeen[target] && r.cs==targets[target][0] && r.ip==targets[target][1] &&
                                (target+1<targets.size() || r.cx>1)) {
                            irqInstructions+=irqCheck(*active.player,memory,target+1==targets.size());
                            irqSeen[target]=true;
                        }
                }
                const auto used=active.advance(budget,bus,copies);
                require(used>0 && used<=budget,"Player grant did not dispatch");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Player exceeded original endpoint");
                    const auto before=trace[cursor];
                    if (((before.cs==0x1920 && before.ip==0x91f) ||
                            (before.cs==0x18ac && before.ip==0x5d2)) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Player REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                active.restore();compare(active.registers(),trace[cursor],index,cursor);++comparisons;
            }
            compare(active.registers(),endpoint,index,cursor,true);
            require(cursor+1==trace.size(),"Player trace extent differs");
            const auto actual=active.player->snapshot().outcome;
            require((outcome==0 && actual==PlayerMotionOutcome::Terrain) ||
                (outcome==1 && actual==PlayerMotionOutcome::RuntimeError) ||
                (outcome==2 && actual==PlayerMotionOutcome::DivideError),"Player outcome differs from original");
            if (memory.writes!=writes || memory.bytes!=expected.bytes) {
                const auto mismatch=std::mismatch(memory.writes.begin(),memory.writes.end(),writes.begin(),writes.end());
                std::cerr<<"case="<<index<<" writes="<<memory.writes.size()<<'/'<<writes.size()
                    <<" first="<<(mismatch.first-memory.writes.begin())<<'\n';
                throw std::runtime_error("Player ordered writes or complete memory differ");
            }
            ++replays;dispatches+=active.player->snapshot().cpu.dispatchedInstructions;
            const auto saved=active.player->snapshot();require(active.player->advance(17,bus,copies)==0 &&
                active.player->snapshot()==saved,"Finished player dispatched work");
            ++mode;
        }
        totalWrites+=writes.size();
    }
    require(input.at==input.bytes.size(),"Player fixture tail differs");
    require(std::ranges::all_of(irqSeen,[](bool yes) { return yes; }),"Player computed IRQ target coverage differs");
    std::cout<<"player_motion_original=ok cases="<<count<<" replays="<<replays<<" comparisons="<<comparisons
        <<" dispatches="<<dispatches<<" writes="<<totalWrites<<" actual_callers="<<callers
        <<" runtime_faults="<<outcomes[1]<<" computed_irq_cases="<<irqSeen.size()<<" irq_instructions="<<irqInstructions
        <<" partial_copy_irqs=1 full_memory=1 canonical_mz=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fa2;r.bp=0x3fdc;r.ip=0x6737;r.flags=0x202;
    PlayerMotionOperation active(r,0x1000,0x200000);Memory memory;const auto bus=memory.bus();
    const auto all=[](uint16_t n) { return n; };
    require(active.advance(0,bus,all)==0 && active.registers()==r,"Zero player budget changed state");
    unsigned rejected=0;
    const auto reject=[&](PlayerMotionSnapshot state) {
        try { (void)PlayerMotionOperation(state); } catch (const std::invalid_argument&) { ++rejected; }
    };
    auto s=active.snapshot();s.cpu.gameSegment=0x1001;reject(s);
    s=active.snapshot();s.cpu.idToggleMask=1;reject(s);
    s=active.snapshot();s.cpu.outcome=ActorFinishOutcome::Returned;reject(s);
    s=active.snapshot();s.outcome=static_cast<PlayerMotionOutcome>(255);reject(s);
    s=active.snapshot();s.outcome=PlayerMotionOutcome::Terrain;reject(s);
    s=active.snapshot();s.outcome=PlayerMotionOutcome::RuntimeError;reject(s);
    s=active.snapshot();s.outcome=PlayerMotionOutcome::DivideError;reject(s);
    s=active.snapshot();s.cpu.registers.ip=0x732c;reject(s);
    s=active.snapshot();s.cpu.registers.cs=0x1920;s.cpu.registers.ip=0xe2;reject(s);
    require(rejected==9,"Player state rejection coverage differs");
    r.ip=0x6738;bool wrongEntry=false;
    try { (void)PlayerMotionOperation(r,0x1000,0x200000); } catch (const std::invalid_argument&) { wrongEntry=true; }
    require(wrongEntry,"Player admitted wrong entry");
    s=active.snapshot();s.cpu.registers.flags&=~uint32_t{0x200};
    PlayerMotionOperation masked(s);bool blocked=false;
    try { masked.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked,"Masked player admitted IRQ");
    std::cout<<"player_motion_unit=ok state_rejections=9 entry_rejection=1 masked_irq=1 zero_budget=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else if (argc==3) replay(argv[1],argv[2]);
        else throw std::runtime_error("Expected fixture and canonical root");
        return 0;
    } catch (const std::exception& error) { std::cerr<<"player_motion=failed "<<error.what()<<'\n';return 1; }
}
