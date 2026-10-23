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
        if (ip==0x7ee4 || ip==0x7ee8) s.actorCalls=s.actorReturns=s.nonplayerCalls=1;
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
    s=completedPlayer;s.postCalls=s.postReturns=1;
    std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x8044;
    (void)FrameActorPassOperation(s);
    constexpr std::array<uint16_t,196> bossGameIps{
        0x432a,0x432b,0x432d,0x4330,0x4335,0x4338,0x433b,0x433d,0x4340,0x4343,
        0x4346,0x4348,0x434b,0x434e,0x4350,0x4353,0x4356,0x4359,0x435d,0x4360,
        0x4363,0x4366,0x4369,0x436b,0x436d,0x4370,0x4374,0x4377,0x437a,0x437d,
        0x4382,0x4384,0x4387,0x438a,0x438e,0x438f,0x4391,0x4393,0x4396,0x439a,
        0x439c,0x439e,0x43a1,0x43a5,0x43a8,0x43ab,0x43ad,0x43af,0x43b1,0x43b3,
        0x43b5,0x43b7,0x43ba,0x43be,0x43c0,0x43c2,0x43c7,0x43ca,0x43ce,0x43d1,
        0x43d5,0x43d6,0x43d8,0x43da,0x43dd,0x43e1,0x43e3,0x43e5,0x43e8,0x43ec,
        0x43ef,0x43f3,0x43f5,0x43f7,0x43f9,0x43fb,0x43fd,0x43ff,0x4402,0x4406,
        0x4408,0x440a,0x440f,0x4411,0x4413,0x4416,0x441a,0x441b,0x441c,0x441e,
        0x4420,0x4423,0x4427,0x442a,0x442d,0x4431,0x4433,0x4435,0x4438,0x443c,
        0x443e,0x4440,0x4443,0x4446,0x444a,0x444d,0x4451,0x4453,0x4456,0x4459,
        0x445b,0x445d,0x445f,0x4461,0x4463,0x4467,0x446b,0x446f,0x4470,0x4471,
        0x4472,0x4475,0x4479,0x447b,0x447d,0x4482,0x4483,0x4484,0x4485,0x448a,
        0x448f,0x4490,0x4491,0x4494,0x4498,0x4499,0x449b,0x449d,0x44a0,0x44a3,
        0x44a5,0x44a7,0x44a9,0x44aa,0x44ab,0x44ad,0x44af,0x44b2,0x44b6,0x44b9,
        0x44bd,0x44bf,0x44c1,0x44c3,0x44c5,0x44c7,0x44c9,0x44cd,0x44d1,0x44d5,
        0x44d6,0x44d7,0x44d8,0x44db,0x44df,0x44e1,0x44e3,0x44e8,0x44e9,0x44ea,
        0x44eb,0x44f0,0x44f5,0x44f6,0x44f7,0x44fa,0x44fe,0x44ff,0x4501,0x4503,
        0x4506,0x450a,0x450c,0x450e,0x4510,0x4511,0x4512,0x4514,0x4516,0x4519,
        0x451d,0x4520,0x4523,0x4525,0x4528,0x4529};
    constexpr std::array<uint16_t,247> bossLibraryIps{
        0xe2,0x4df,0x4e2,0x4e4,0x4e6,0x4e8,0x4ea,0x4ee,0x4f0,0x4f1,
        0x4f4,0x92a,0x92c,0x92e,0x930,0x931,0x932,0x934,0x936,0x938,
        0x93a,0x93c,0x93e,0x93f,0x940,0x942,0x944,0xca5,0xca8,0xcaa,
        0xcac,0xcae,0xcb0,0xcb1,0xcb3,0xcb5,0xcb9,0xcbb,0xcbd,0xcbf,
        0xcc1,0xcc5,0xcc9,0xcca,0xccc,0xcce,0xcd0,0xcd2,0xcd4,0xcd6,
        0xcd8,0xcda,0xcdb,0xcdd,0xcdf,0xce1,0xce3,0xce5,0xce7,0xce9,
        0xceb,0xced,0xcf0,0xcf2,0xcf4,0xcf6,0xcf8,0xcfb,0xd79,0xd7a,
        0xd7b,0xd7c,0xd7e,0xd80,0xd82,0xd84,0xd86,0xd87,0xd8b,0xd8e,
        0xd91,0xd94,0xd96,0xd98,0xd99,0xd9c,0xd9e,0xd9f,0xda1,0xda3,
        0xda5,0xda6,0xda8,0xdaa,0xdac,0xdad,0xdaf,0xdb1,0xdb2,0xdb4,
        0xdb6,0xdba,0xdbe,0xdc2,0xdc4,0xdc6,0xdc8,0xdc9,0xdcb,0xdce,
        0xdd0,0xdd2,0xdd4,0xdd6,0xdd8,0xdda,0xddc,0xdde,0xde0,0xde2,
        0xde4,0xde6,0xde8,0xdea,0xdec,0xdee,0xdf0,0xdf2,0xdf3,0xdf5,
        0xdf7,0xdf9,0xdfa,0xdfd,0xdff,0xe01,0xe03,0xe05,0xe07,0xe09,
        0xe0a,0xe0b,0xe0c,0xe0d,0xe0f,0xe11,0xe14,0xe16,0xe18,0xe1a,
        0xe1c,0xe1d,0xe21,0xe4e,0xe50,0xe52,0xe54,0xe56,0xe58,0xe5a,
        0xe5c,0xe5e,0xe61,0xe64,0xe66,0xe69,0xe6b,0xe6d,0xe6f,0xe71,
        0xe73,0xe75,0xe77,0xe79,0xe7b,0xe7d,0xe7f,0xe81,0xe83,0xe85,
        0xe87,0xe89,0xe8c,0xe8d,0xe8e,0xe90,0xe92,0xe94,0xe97,0xe99,
        0xe9b,0xe9d,0xea0,0xea3,0xea5,0xea7,0xea9,0xeac,0xeaf,0xeb1,
        0xeb3,0xeb5,0xeb7,0xeb9,0xebc,0xebe,0xec0,0xec2,0xec4,0xec6,
        0xec8,0xeca,0xecd,0xed0,0xed2,0xed4,0xed6,0xed8,0xeda,0xedd,
        0xee0,0xee1,0xee2,0xee3,0xee4,0xee6,0xee8,0xefb,0xefe,0xf00,
        0xf01,0xf03,0xf05,0xf08,0xf0a,0xf0f,0xf12,0xf13,0xf15,0xf18,
        0xf1a,0xf23,0xf26,0xf29,0xf2c,0xf2f,0xf32};
    unsigned bossBoundaries=0;
    auto bossState=[&](uint16_t cs,uint16_t ip) {
        auto state=initial;state.dispatchedInstructions=1;
        auto& entry=std::get<FrameActorEntrySnapshot>(state.callee);
        auto cpu=std::get<FrameActorCallerSnapshot>(entry.callee).registers;cpu.cs=cs;cpu.ip=ip;
        entry.callee=BossLinksSnapshot{cpu,kGame};
        if (cs==0x1920 && ip==0xe2) {
            entry.outcome=FrameActorEntryOutcome::RuntimeError;
            std::get<BossLinksSnapshot>(entry.callee).outcome=BossLinksOutcome::RuntimeError;
            state.outcome=FrameActorPassOutcome::RuntimeError;
        }
        return state;
    };
    for (uint16_t ip=0x432a;ip<=0x4529;++ip) {
        s=bossState(kGame,ip);
        if (std::find(bossGameIps.begin(),bossGameIps.end(),ip)==bossGameIps.end()) reject(s);
        else { (void)FrameActorPassOperation(s);++bossBoundaries; }
    }
    for (uint16_t ip=0;ip<0x1820;++ip) {
        s=bossState(0x1920,ip);
        if (std::find(bossLibraryIps.begin(),bossLibraryIps.end(),ip)==bossLibraryIps.end()) reject(s);
        else { (void)FrameActorPassOperation(s);++bossBoundaries; }
    }
    for (uint16_t ip : {uint16_t{0x4329},uint16_t{0x452a}}) reject(bossState(kGame,ip));
    for (uint16_t ip : {uint16_t{0x1820},uint16_t{0xffff}}) reject(bossState(0x1920,ip));
    reject(bossState(0x2000,0x432a));
    unsigned bossHistoryControls=0,callerHistoryControls=0;
    const auto rejectBossHistory=[&](const FrameActorPassSnapshot& base) {
        for (unsigned history=0;history<3;++history) {
            auto state=base;state.dispatchedInstructions+=2;
            state.nonplayerCalls=history==1 ? 0 : 1;
            state.playerCalls=state.postCalls=state.postReturns=history==0 ? 0 : 1;
            state.actorCalls=state.actorReturns=state.nonplayerCalls+state.playerCalls;
            reject(state);++bossHistoryControls;
        }
    };
    for (uint16_t ip : bossGameIps) rejectBossHistory(bossState(kGame,ip));
    for (uint16_t ip : bossLibraryIps) rejectBossHistory(bossState(0x1920,ip));
    for (uint16_t ip : {uint16_t{0x7ee4},uint16_t{0x7ee8}}) {
        for (bool completedPlayerOnly : {false,true}) {
            s=initial;s.dispatchedInstructions=2;
            std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
            if (completedPlayerOnly) s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=1;
            reject(s);
        }
    }
    Memory bossMemory;const auto bossBus=bossMemory.bus();
    bossMemory.bytes[Memory::address(0x1aa2,0x79f9)]=1;
    FrameActorPassOperation bossActive(initial);bossActive.advance(3,bossBus,all);
    require(bossActive.registers().cs==kGame && bossActive.registers().ip==0x432a,"Pass boss CALL boundary differs");
    auto bossInterrupted=bossActive;bossInterrupted.deliverTimerInterrupt(bossBus);
    (void)FrameActorPassOperation(bossInterrupted.snapshot());
    rejectBossHistory(bossInterrupted.snapshot());
    s=bossInterrupted.snapshot();
    std::get<BossLinksSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x432c;reject(s);
    bossActive.advance(4,bossBus,all);
    require(bossActive.registers().cs==0x1920 && bossActive.registers().ip==0x4df,"Pass boss RTL boundary differs");
    bossActive.deliverTimerInterrupt(bossBus);(void)FrameActorPassOperation(bossActive.snapshot());
    rejectBossHistory(bossActive.snapshot());
    s=bossActive.snapshot();
    std::get<BossLinksSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x4e0;reject(s);
    r.ip=0x6053;
    s=initial;auto& animation=std::get<FrameActorEntrySnapshot>(s.callee).callee.emplace<ActorAnimationSnapshot>();
    animation.registers=r;animation.gameSegment=kGame;reject(s);
    auto actorState=initial;actorState.actorCalls=1;actorState.nonplayerCalls=1;actorState.actorKind=FrameActorPassKind::Nonplayer;
    actorState.dispatchedInstructions=1;
    r.sp=0x3fde;actorState.callee=ActorUpdateOperation(r,kGame,kIdToggle).snapshot();
    (void)FrameActorPassOperation(actorState);
    s=actorState;s.dispatchedInstructions=3;s.actorCalls=2;s.actorReturns=1;
    s.playerCalls=s.postCalls=s.postReturns=1;reject(s);
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
    unsigned playerSetupControls=0,playerCapControls=0;
    for (bool irq : {false,true}) {
        for (uint16_t ip : callerIps) {
            if (!((ip>=0x7f3c && ip<=0x7f59) || ip==0x804b)) continue;
            s=irq ? irqState : initial;s.dispatchedInstructions=2;
            s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=2;
            std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
            reject(s);++playerSetupControls;
            s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=1;
            (void)FrameActorPassOperation(s);
        }
        s=irq ? irqState : initial;s.dispatchedInstructions=3;
        s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=3;
        std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x8044;
        reject(s);++playerCapControls;
    }
    s=initial;s.dispatchedInstructions=3;
    s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=3;
    s.outcome=FrameActorPassOutcome::TransientQueues;
    std::get<FrameActorEntrySnapshot>(s.callee).outcome=FrameActorEntryOutcome::TransientQueues;
    std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x804e;
    reject(s);++playerCapControls;
    s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=2;
    (void)FrameActorPassOperation(s);
    s=actorState;s.actorKind=FrameActorPassKind::Player;s.dispatchedInstructions=3;
    s.actorCalls=s.playerCalls=3;s.actorReturns=s.postCalls=s.postReturns=2;s.nonplayerCalls=0;
    reject(s);++playerCapControls;
    s=postState;s.dispatchedInstructions=3;
    s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=3;s.postReturns=2;
    reject(s);++playerCapControls;
    for (bool irq : {false,true}) {
        for (uint16_t ip : callerIps) {
            if (ip>0x7f3a) continue;
            for (bool nonplayerHistory : {false,true}) {
                s=irq ? irqState : initial;s.dispatchedInstructions=3;
                s.nonplayerCalls=nonplayerHistory ? 1 : 0;
                s.playerCalls=s.postCalls=s.postReturns=1;
                s.actorCalls=s.actorReturns=s.nonplayerCalls+1;
                std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
                reject(s);++callerHistoryControls;
            }
            if (ip<=0x7ec5) {
                s=irq ? irqState : initial;s.dispatchedInstructions=3;
                s.actorCalls=s.actorReturns=s.nonplayerCalls=1;
                std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
                reject(s);++callerHistoryControls;
            }
        }
    }
    s=initial;s.dispatchedInstructions=3;s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=1;
    s.outcome=FrameActorPassOutcome::Restart;
    std::get<FrameActorEntrySnapshot>(s.callee).outcome=FrameActorEntryOutcome::Restart;
    std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x77dc;
    reject(s);++callerHistoryControls;
    s.playerCalls=s.postCalls=s.postReturns=0;s.nonplayerCalls=1;
    (void)FrameActorPassOperation(s);
    s=irqState;++std::get<FrameActorEntrySnapshot>(s.callee).timer->dataSegment;reject(s);
    s=irqState;std::get<FrameActorEntrySnapshot>(s.callee).timer->idToggleMask=0;reject(s);
    s=irqState;s.dispatchedInstructions=2;s.actorCalls=s.actorReturns=s.playerCalls=1;reject(s);
    s=irqState;
    std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=0x7ebc;reject(s);
    for (uint16_t ip : {uint16_t{0x7ee4},uint16_t{0x7ee8}}) {
        for (bool completedPlayerOnly : {false,true}) {
            s=irqState;s.dispatchedInstructions=2;
            std::get<FrameActorCallerSnapshot>(std::get<FrameActorEntrySnapshot>(s.callee).callee).registers.ip=ip;
            if (completedPlayerOnly) s.actorCalls=s.actorReturns=s.playerCalls=s.postCalls=s.postReturns=1;
            reject(s);
        }
    }
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
    require(rejected==7940 && callerBoundaries==50 && bossBoundaries==443 &&
        bossHistoryControls==1335 && callerHistoryControls==157 && playerSetupControls==22 &&
        playerCapControls==5,"Pass rejection coverage differs");
    std::cout<<"frame_actor_pass_unit=ok state_rejections="<<rejected<<" phase_controls=3 entry_rejection=1 masked_irq=1 zero_budget=1 terminal_controls=2 caller_boundaries="<<callerBoundaries<<" skipped_post_controls=4 boss_boundaries="<<bossBoundaries<<" boss_irq_controls=2 nonplayer_return_controls=8 boss_history_controls="<<bossHistoryControls<<" caller_history_controls="<<callerHistoryControls<<" actor_history_controls=1 player_setup_controls="<<playerSetupControls<<" player_cap_controls="<<playerCapControls<<'\n';
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
