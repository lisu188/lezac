#include "core/frame_actor_pass.hpp"

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
constexpr uint16_t kGame=0x1000;
constexpr uint32_t kIdToggle=0x200000;
constexpr size_t kProjectionBytes=35707847;
constexpr uint64_t kProjectionFingerprint=0x4310d227f97d1b8aull;
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    explicit Reader(const std::filesystem::path& path,size_t expected) {
        require(std::filesystem::file_size(path)==expected,"Frame actor pass input size differs");
        std::ifstream input(path,std::ios::binary);require(input.good(),"Missing frame actor pass input");
        bytes={std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
        require(bytes.size()==expected,"Frame actor pass input extent differs");
    }
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated frame actor pass fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace() {
        const auto count=number(4);require(count>1 && count<=3000000,"Frame actor pass trace reserve differs");
        std::vector<DosGetTimeRegisters> rows;rows.reserve(count);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<count;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i || mask==0x3fff),"Frame actor pass delta mask differs");
            for (unsigned c=0;c<members.size();++c)
                if (mask&(1u<<c)) previous.*members[c]=static_cast<uint16_t>(number(2));
            if (mask&0x2000u) previous.flags=number(4);
            rows.push_back(previous);
        }
        return rows;
    }
};
uint64_t fingerprint(const std::vector<uint8_t>& raw) {
    uint64_t value=14695981039346656037ull;
    for (uint8_t byte : raw) { value^=byte;value*=1099511628211ull; }return value;
}
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected frame actor pass IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected frame actor pass IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe(root/"LEZAC.EXE",52384);
    require(fingerprint(exe.bytes)==0x2ae32f89b95e200bull,"Frame actor pass MZ fingerprint differs");
    require(exe.number(2)==0x5a4d,"Frame actor pass MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header &&
        exe.bytes.size()-header+0x10000<=1048576,"Frame actor pass MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Frame actor pass relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,bool endpoint=false) {
    const auto flags=actual.flags;const bool defined=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    if (!endpoint) actual.flags=expected.flags;
    if (!defined || actual!=expected) {
        std::cerr<<"case="<<index<<" row="<<row<<" actual="<<std::hex<<actual.cs<<':'<<actual.ip
            <<" expected="<<expected.cs<<':'<<expected.ip<<" sp="<<actual.sp<<'/'<<expected.sp
            <<" bp="<<actual.bp<<'/'<<expected.bp<<" flags="<<flags<<'/'<<expected.flags<<std::dec<<'\n';
        for (auto member : members) std::cerr<<std::hex<<(actual.*member)<<'/'<<(expected.*member)<<' ';
        std::cerr<<std::dec<<'\n';
        throw std::runtime_error("Frame actor pass register/control trace differs");
    }
}
uint64_t irqCheck(FrameActorPassOperation active,Memory memory,uint8_t partialSize) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    if (partialSize) {
        const auto before=active.registers();const auto writes=memory.writes.size();
        require(before.cx>1,"Pass partial-copy IRQ lacks transfers");
        active.advance(1,bus,[](uint16_t) { return uint16_t{1}; });
        require(active.registers().ip==before.ip && active.registers().cx==before.cx-1 &&
            memory.writes.size()==writes+1 && memory.writes.back().size==partialSize,
            "Pass partial-copy transfer differs");
    }
    const auto before=active.registers();const auto saved=active.snapshot();
    active.deliverTimerInterrupt(bus);
    bool nested=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && active.snapshot().timerDeliveries==saved.timerDeliveries+1,"Pass IRQ nesting/accounting differs");
    unsigned steps=0;
    while (active.interruptInProgress()) {
        require(steps++<4096,"Pass IRQ did not return");active.advance(1,bus,all);
        active=FrameActorPassOperation(active.snapshot());
    }
    const auto instructions=active.snapshot().timerInstructions-saved.timerInstructions;
    require(instructions==36 && active.registers()==before && memory.word(0x40,0x6c)==101 &&
        active.snapshot().dispatchedInstructions==saved.dispatchedInstructions+36,"Pass IRQ CPU/tick/accounting differs");
    auto other=active;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!active.finished()) { require(steps++<3000000,"Pass IRQ continuation stalled");active.advance(1,bus,all); }
    while (!other.finished()) {
        require(steps++<6000000,"Pass IRQ alternate stalled");other.advance(17,otherBus,all);
        other=FrameActorPassOperation(other.snapshot());
    }
    require(active.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Pass IRQ continuation grant/snapshot differs");
    bool ended=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished pass admitted IRQ");return instructions;
}
void replay(const char* path,const char* root) {
    Reader input(path,kProjectionBytes);
    require(fingerprint(input.bytes)==kProjectionFingerprint,"Pass corpus fingerprint differs");
    for (char c : std::string("LZAPAS01")) require(input.number(1)==static_cast<uint8_t>(c),"Pass magic differs");
    const auto count=input.number(4);require(count==876,"Pass corpus domain differs");const auto base=image(root);
    uint64_t replays=0,comparisons=0,dispatches=0,totalWrites=0,actorCalls=0,actorReturns=0,npcCalls=0,playerCalls=0;
    uint64_t postCalls=0,postReturns=0,bothPlayers=0,bossCalls=0,prefixSkips=0,irqInstructions=0;
    std::array<unsigned,4> outcomes{};
    struct Target { uint16_t cs,ip,marker;int kind;uint8_t partial,minPosts; };
    constexpr std::array<Target,19> targets{{
        {0x1000,0x7ebb,0,0,0,0},{0x1000,0x432a,0,0,0,0},{0x1000,0x7ee1,0,0,0,0},
        {0x1000,0x6053,0,1,0,0},{0x1000,0x7780,0,1,0,0},{0x1000,0x7ee4,0,0,0,0},
        {0x1000,0x7f59,1,0,0,0},{0x1000,0x7f59,2,0,0,0},
        {0x1000,0x6053,1,2,0,0},{0x1000,0x6053,2,2,0,0},
        {0x1000,0x7f5c,1,2,0,0},{0x1000,0x7f5c,2,2,0,0},
        {0x1000,0x30d0,0,2,0,0},{0x1000,0x56a8,0,2,1,0},{0x1000,0x116a,0,2,2,0},
        {0x1920,0x91f,0,2,1,0},{0x1000,0x8044,1,0,0,1},{0x1000,0x8044,2,0,0,2},
        {0x1000,0x8049,2,0,0,2}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Pass row order differs");const auto outcome=input.number(1);
        require(outcome<outcomes.size(),"Pass outcome differs");++outcomes[outcome];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        const auto seeds=input.number(4);require(seeds<65536,"Pass seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto address=input.number(4),size=input.number(4);
            require(size<=65536 && address>=0x1aa20 && address+size<=1048576 && input.at+size<=input.bytes.size(),
                "Pass seed exceeds memory");
            std::copy_n(input.bytes.begin()+input.at,size,initial.bytes.begin()+address);input.at+=size;
        }
        const auto trace=input.trace();compare(trace.front(),entry,index,0,true);
        uint64_t calls=0,returns=0,npcs=0,players=0,posts=0,postEnds=0,bosses=0,skips=0;
        bool inPost=false;
        for (const auto& r : trace) if (r.cs==kGame) {
            calls+=r.ip==0x6053;returns+=r.ip==0x7ee4 || r.ip==0x7f5c;
            npcs+=r.ip==0x7ee1;players+=r.ip==0x7f59;posts+=r.ip==0x7f5c;bosses+=r.ip==0x432a;
            if (r.ip==0x7f5c) inPost=true;
            if (r.ip==0x8044) { if (inPost) ++postEnds;else ++skips;inPost=false; }
        }
        const auto writeCount=input.number(4);require(writeCount<3000000,"Pass write reserve differs");
        std::vector<Write> writes;auto expected=initial;
        for (unsigned i=0;i<writeCount;++i) {
            Write item{input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require((item.size==1 || item.size==2) && item.address+item.size<=1048576,"Pass write exceeds memory");
            writes.push_back(item);expected.store(item.address,item.value,item.size);
        }
        require(input.number(4)==0,"Pass reserved event field differs");
        unsigned mode=0;
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();FrameActorPassOperation active(entry,kGame,kIdToggle);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };
            size_t cursor=0;compare(active.registers(),trace.front(),index,0);++comparisons;
            while (!active.finished()) {
                require(cursor+1<trace.size(),"Pass exceeded original endpoint");
                if (!mode) {
                    const auto r=active.registers();const auto& state=active.snapshot();
                    for (size_t target=0;target<targets.size();++target) {
                        const auto& t=targets[target];
                        if (!irqSeen[target] && r.cs==t.cs && r.ip==t.ip &&
                            (!t.marker || memory.word(0x1aa2,0x2082)==t.marker) &&
                            static_cast<int>(state.actorKind)==t.kind && state.postReturns>=t.minPosts &&
                            (!t.partial || r.cx>1)) {
                            irqInstructions+=irqCheck(active,memory,t.partial);irqSeen[target]=true;
                        }
                    }
                }
                const auto before=active.snapshot().dispatchedInstructions;
                const auto used=active.advance(budget,bus,copies);
                require(used>0 && used<=budget && active.snapshot().dispatchedInstructions==before+used,
                    "Pass grant/dispatch accounting differs");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Pass trace exceeded endpoint");const auto r=trace[cursor];
                    if (((r.cs==0x1920 && r.ip==0x91f) || (r.cs==0x18ac && r.ip==0x5d2) ||
                        (r.cs==kGame && (r.ip==0x116a || r.ip==0x56a8 || r.ip==0x56b3))) && r.cx) {
                        cursor+=std::min(r.cx,limit);require(cursor<trace.size(),"Pass REP trace truncated");
                        if (trace[cursor].cs==r.cs && trace[cursor].ip==r.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                active=FrameActorPassOperation(active.snapshot());
                compare(active.registers(),trace[cursor],index,cursor);++comparisons;
            }
            compare(active.registers(),endpoint,index,cursor,true);require(cursor+1==trace.size(),"Pass trace extent differs");
            const auto& state=active.snapshot();
            constexpr std::array terminal{FrameActorPassOutcome::TransientQueues,FrameActorPassOutcome::Restart,
                FrameActorPassOutcome::RuntimeError,FrameActorPassOutcome::DivideError};
            require(state.outcome==terminal[outcome] && state.actorCalls==calls && state.actorReturns==returns &&
                state.nonplayerCalls==npcs && state.playerCalls==players && state.postCalls==posts && state.postReturns==postEnds &&
                !state.timerInstructions && !state.timerDeliveries,"Pass outcome/call accounting differs");
            if (memory.writes!=writes || memory.bytes!=expected.bytes) {
                std::cerr<<"write_case="<<index<<" mode="<<mode<<" writes="<<memory.writes.size()<<'/'<<writes.size()<<'\n';
                throw std::runtime_error("Pass ordered writes or complete memory differ");
            }
            ++replays;dispatches+=state.dispatchedInstructions;const auto saved=state;
            require(active.advance(17,bus,copies)==0 && active.snapshot()==saved,"Finished pass dispatched work");++mode;
        }
        totalWrites+=writes.size();actorCalls+=calls;actorReturns+=returns;npcCalls+=npcs;playerCalls+=players;
        postCalls+=posts;postReturns+=postEnds;bothPlayers+=players==2;bossCalls+=bosses;prefixSkips+=skips;
    }
    require(input.at==input.bytes.size(),"Pass fixture tail differs");
    for (size_t i=0;i<irqSeen.size();++i) if (!irqSeen[i])
        std::cerr<<"missing_irq_target="<<std::hex<<targets[i].cs<<':'<<targets[i].ip<<std::dec<<" marker="<<targets[i].marker<<'\n';
    require(std::ranges::all_of(irqSeen,[](bool yes) { return yes; }),"Pass IRQ target coverage differs");
    require(outcomes==std::array<unsigned,4>{806,30,22,18} && actorCalls==3398 && actorReturns==3370 &&
        npcCalls==2244 && playerCalls==1154 && postCalls==1152 && postReturns==1152 &&
        bothPlayers==540 && bossCalls==36 && prefixSkips==460,"Pass path coverage differs");
    std::cout<<"frame_actor_pass_original=ok cases="<<count<<" replays="<<replays<<" comparisons="<<comparisons
        <<" dispatches="<<dispatches<<" writes="<<totalWrites<<" actor_calls="<<actorCalls<<" actor_returns="<<actorReturns
        <<" nonplayer_calls="<<npcCalls<<" player_calls="<<playerCalls<<" post_calls="<<postCalls<<" post_returns="<<postReturns
        <<" both_players="<<bothPlayers<<" boss_calls="<<bossCalls<<" prefix_skips="<<prefixSkips
        <<" queues="<<outcomes[0]<<" restarts="<<outcomes[1]<<" runtime_errors="<<outcomes[2]<<" divide_errors="<<outcomes[3]
        <<" computed_irq_cases="<<irqSeen.size()<<" irq_instructions="<<irqInstructions
        <<" partial_copy_irqs=3 full_memory=1 canonical_mz=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=kGame;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3fdc;r.ip=0x7ebb;r.flags=0x202;
    FrameActorPassOperation active(r,kGame,kIdToggle);Memory memory;const auto bus=memory.bus();
    const auto all=[](uint16_t n) { return n; };const auto initial=active.snapshot();
    require(active.advance(0,bus,all)==0 && active.snapshot()==initial,"Zero pass budget changed state");
    unsigned rejected=0;
    const auto reject=[&](FrameActorPassSnapshot s) {
        bool failed=false;try { (void)FrameActorPassOperation(s); } catch (const std::invalid_argument&) { failed=true; }
        if (!failed) std::cerr<<"accepted_invalid_snapshot="<<rejected<<'\n';
        require(failed,"Pass admitted invalid snapshot");++rejected;
    };
    auto s=initial;s.gameSegment=0x1001;reject(s);
    s=initial;s.idToggleMask=1;reject(s);
    s=initial;s.actorKind=static_cast<FrameActorPassKind>(255);reject(s);
    s=initial;s.outcome=static_cast<FrameActorPassOutcome>(255);reject(s);
    s=initial;s.timerInstructions=1;reject(s);
    s=initial;++s.callerSs;reject(s);
    s=initial;s.actorReturns=1;reject(s);
    s=initial;s.playerCalls=1;reject(s);
    s=initial;s.postCalls=1;reject(s);
    s=initial;s.postReturns=1;reject(s);
    s=initial;s.actorCalls=1;s.nonplayerCalls=1;reject(s);
    s=initial;s.actorKind=FrameActorPassKind::Nonplayer;reject(s);
    s=initial;std::get<FrameActorEntrySnapshot>(s.callee).prefixTimerInstructions=1;reject(s);
    s=initial;std::get<FrameActorEntrySnapshot>(s.callee).tailTimerDeliveries=1;reject(s);
    s=initial;std::get<FrameActorEntrySnapshot>(s.callee).actorKind=FrameActorEntryKind::NonPlayer;reject(s);
    s=initial;std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x804e;reject(s);
    s=initial;std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x77dc;reject(s);
    s=initial;std::get<FrameActorEntrySnapshot>(s.callee).outcome=FrameActorEntryOutcome::ActorBody;reject(s);
    s=initial;s.outcome=FrameActorPassOutcome::TransientQueues;reject(s);
    s=initial;s.outcome=FrameActorPassOutcome::RuntimeError;reject(s);
    s=initial;s.outcome=FrameActorPassOutcome::DivideError;reject(s);
    constexpr std::array<uint16_t,50> callerIps{
        0x7ebb,0x7ec0,0x7ec2,0x7ec5,0x7ecb,0x7ece,0x7ed0,0x7ed4,0x7ed6,0x7edb,
        0x7edf,0x7ee0,0x7ee1,0x7ee4,0x7ee8,0x7eea,0x7eef,0x7ef1,0x7ef6,0x7ef8,
        0x7efc,0x7f01,0x7f03,0x7f09,0x7f0b,0x7f0f,0x7f13,0x7f18,0x7f1a,0x7f1e,
        0x7f23,0x7f28,0x7f2a,0x7f2d,0x7f2f,0x7f34,0x7f3a,0x7f3c,0x7f40,0x7f44,
        0x7f49,0x7f4b,0x7f4e,0x7f53,0x7f57,0x7f58,0x7f59,0x8044,0x8049,0x804b};
    unsigned callerBoundaries=0;
    for (uint16_t ip=0x7ebb;ip<=0x804b;++ip) {
        if (ip>0x7f59 && ip<0x8044) continue;
        s=initial;s.dispatchedInstructions=1;
        std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
        if (std::find(callerIps.begin(),callerIps.end(),ip)==callerIps.end()) reject(s);
        else { (void)FrameActorPassOperation(s);++callerBoundaries; }
    }
    auto completedPlayer=initial;completedPlayer.dispatchedInstructions=2;
    completedPlayer.actorCalls=completedPlayer.actorReturns=completedPlayer.playerCalls=1;
    reject(completedPlayer);
    for (const auto outcome : {FrameActorPassOutcome::TransientQueues,FrameActorPassOutcome::Restart}) {
        s=completedPlayer;s.outcome=outcome;auto& entry=std::get<FrameActorEntrySnapshot>(s.callee);
        entry.outcome=outcome==FrameActorPassOutcome::TransientQueues ? FrameActorEntryOutcome::TransientQueues : FrameActorEntryOutcome::Restart;
        std::get<FrameActorCallerSnapshot>(entry.callee).registers.ip=outcome==FrameActorPassOutcome::TransientQueues ? 0x804e : 0x77dc;
        reject(s);
    }
    s=completedPlayer;s.postCalls=s.postReturns=1;(void)FrameActorPassOperation(s);
    r.ip=0x6053;
    s=initial;auto& animation=std::get<FrameActorEntrySnapshot>(s.callee).callee.emplace<ActorAnimationSnapshot>();
    animation.registers=r;animation.gameSegment=kGame;reject(s);
    auto actorState=initial;actorState.actorCalls=1;actorState.nonplayerCalls=1;actorState.actorKind=FrameActorPassKind::Nonplayer;
    actorState.dispatchedInstructions=1;
    r.sp=0x3fde;actorState.callee=ActorUpdateOperation(r,kGame,kIdToggle).snapshot();
    (void)FrameActorPassOperation(actorState);
    s=actorState;++std::get<ActorUpdateSnapshot>(s.callee).callerSs;reject(s);
    s=actorState;++std::get<ActorUpdateSnapshot>(s.callee).callerSp;reject(s);
    s=actorState;std::get<ActorUpdateSnapshot>(s.callee).dispatchedInstructions=2;reject(s);
    s=actorState;s.actorKind=FrameActorPassKind::None;reject(s);
    auto postState=initial;postState.actorCalls=1;postState.actorReturns=1;postState.playerCalls=1;
    postState.dispatchedInstructions=2;
    postState.postCalls=1;postState.actorKind=FrameActorPassKind::Player;
    r.ip=0x7f5c;r.sp=0x3fe4;postState.callee=PlayerPostOperation(r,kGame,kIdToggle).snapshot();
    (void)FrameActorPassOperation(postState);
    s=postState;++std::get<PlayerPostSnapshot>(s.callee).callerBp;reject(s);
    s=postState;s.postCalls=0;reject(s);
    s=postState;r.cs=0x1920;r.ip=0x945;r.sp=0x3fe0;
    s.callee=PlayerPostOperation(r,kGame,kIdToggle,PlayerPostEntry::ScoreDivide).snapshot();reject(s);
    r.cs=kGame;r.ip=0x432a;r.sp=0x3fe4;
    s=initial;auto& caller=std::get<FrameActorEntrySnapshot>(s.callee);
    auto& links=caller.callee.emplace<BossLinksSnapshot>();
    links.registers=r;links.gameSegment=kGame;links.outcome=BossLinksOutcome::Returned;reject(s);
    s=initial;r.cs=0x1920;r.ip=0xe2;
    auto& errorCaller=std::get<FrameActorEntrySnapshot>(s.callee);
    auto& errorLinks=errorCaller.callee.emplace<BossLinksSnapshot>();
    errorLinks.registers=r;errorLinks.gameSegment=kGame;errorCaller.outcome=FrameActorEntryOutcome::RuntimeError;
    s.outcome=FrameActorPassOutcome::RuntimeError;reject(s);
    for (uint16_t ip : {uint16_t{0x30a3},uint16_t{0x7f5c},uint16_t{0x1239},uint16_t{0x78e7}}) {
        s=initial;
        std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
        reject(s);
    }
    s=initial;auto& runningCaller=std::get<FrameActorEntrySnapshot>(s.callee);
    auto& runningLinks=runningCaller.callee.emplace<BossLinksSnapshot>();
    runningLinks.registers=r;
    runningLinks.registers.cs=0x1920;runningLinks.registers.ip=0xe2;runningLinks.gameSegment=kGame;
    reject(s);
    Memory irqMemory;const auto irqBus=irqMemory.bus();
    FrameActorPassOperation interrupted(initial);interrupted.deliverTimerInterrupt(irqBus);
    const auto irqState=interrupted.snapshot();
    (void)FrameActorPassOperation(irqState);
    s=irqState;++std::get<FrameActorEntrySnapshot>(s.callee).timer->dataSegment;reject(s);
    s=irqState;std::get<FrameActorEntrySnapshot>(s.callee).timer->idToggleMask=0;reject(s);
    s=irqState;s.dispatchedInstructions=2;s.actorCalls=s.actorReturns=s.playerCalls=1;reject(s);
    s=irqState;
    std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x7ebc;reject(s);
    r.cs=kGame;
    r.ip=0x7ebc;bool wrongEntry=false;
    try { (void)FrameActorPassOperation(r,kGame,kIdToggle); } catch (const std::invalid_argument&) { wrongEntry=true; }
    require(wrongEntry,"Pass admitted wrong entry");r.ip=0x7ebb;r.flags&=~uint32_t{0x200};
    FrameActorPassOperation masked(r,kGame,kIdToggle);const auto before=masked.snapshot();bool blocked=false;
    try { masked.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked && masked.snapshot()==before && memory.writes.empty(),"Masked pass IRQ changed state");
    for (const auto outcome : {FrameActorPassOutcome::TransientQueues,FrameActorPassOutcome::Restart}) {
        auto terminal=initial;terminal.outcome=outcome;auto& entry=std::get<FrameActorEntrySnapshot>(terminal.callee);
        auto& cpu=std::get<FrameActorCallerSnapshot>(entry.callee).registers;
        cpu.ip=outcome==FrameActorPassOutcome::TransientQueues ? 0x804e : 0x77dc;
        entry.outcome=outcome==FrameActorPassOutcome::TransientQueues ? FrameActorEntryOutcome::TransientQueues : FrameActorEntryOutcome::Restart;
        FrameActorPassOperation ended(terminal);const auto saved=ended.snapshot();bool stopped=false;
        try { ended.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { stopped=true; }
        require(stopped && ended.advance(17,bus,all)==0 && ended.snapshot()==saved,"Finished pass changed state");
    }
    require(rejected==160 && callerBoundaries==50,"Pass rejection coverage differs");
    std::cout<<"frame_actor_pass_unit=ok state_rejections="<<rejected<<" phase_controls=3 entry_rejection=1 masked_irq=1 zero_budget=1 terminal_controls=2 caller_boundaries="<<callerBoundaries<<" skipped_post_controls=4\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else if (argc==3) replay(argv[1],argv[2]);
        else throw std::runtime_error("Expected fixture and canonical root");
        return 0;
    } catch (const std::exception& error) { std::cerr<<"frame_actor_pass=failed "<<error.what()<<'\n';return 1; }
}
