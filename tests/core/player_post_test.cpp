#include "core/actor_update.hpp"
#include "core/player_post.hpp"

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
constexpr size_t kProjectionBytes=31367046;
constexpr uint64_t kProjectionFingerprint=0x1d61f06fc0792038ull;
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    explicit Reader(const std::filesystem::path& path,size_t expected) {
        require(std::filesystem::file_size(path)==expected,"Player post input size differs");
        std::ifstream input(path,std::ios::binary);require(input.good(),"Missing player post input");
        bytes={std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
        require(bytes.size()==expected,"Player post input extent differs");
    }
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated player post fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace() {
        const auto count=number(4);require(count>1 && count<=3000000,"Player post trace reserve differs");
        std::vector<DosGetTimeRegisters> rows;rows.reserve(count);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<count;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i || mask==0x3fff),"Player post delta mask differs");
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected player post IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected player post IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe(root/"LEZAC.EXE",52384);
    require(fingerprint(exe.bytes)==0x2ae32f89b95e200bull,"Player post MZ fingerprint differs");
    require(exe.number(2)==0x5a4d,"Player post MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header &&
        exe.bytes.size()-header+0x10000<=1048576,"Player post MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Player post relocation exceeds memory");
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
        throw std::runtime_error("Player post register/control trace differs");
    }
}
struct Driver {
    std::optional<FrameActorEntryOperation> caller;
    std::optional<ActorUpdateOperation> actor;
    std::optional<PlayerPostOperation> post;
    explicit Driver(DosGetTimeRegisters entry) {
        if (entry.cs==0x1920) post.emplace(entry,kGame,kIdToggle,PlayerPostEntry::ScoreDivide);
        else if (entry.ip==0x7f5c) post.emplace(entry,kGame,kIdToggle);
        else if (entry.ip==0x6053) actor.emplace(entry,kGame,kIdToggle);
        else { require(entry.ip==0x7ebb,"Player post replay entry differs");caller.emplace(entry,kGame,kIdToggle); }
    }
    DosGetTimeRegisters registers() const {
        return post ? post->registers() : actor ? actor->registers() : caller->registers();
    }
    bool finished() const {
        return post ? post->finished() : actor && actor->finished();
    }
    void restore() {
        if (post) post=PlayerPostOperation(post->snapshot());
        else if (actor) actor=ActorUpdateOperation(actor->snapshot());
        else caller=FrameActorEntryOperation(caller->snapshot());
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const PlayerPostOperation::CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (post) {
                const auto before=post->snapshot();const auto r=post->registers();
                const auto transfers=r.cs==kGame && (r.ip==0x116a || r.ip==0x56a8 || r.ip==0x56b3) ? copies(r.cx) : 0;
                require(post->advance(1,bus,copies)==1 &&
                    post->snapshot().dispatchedInstructions==before.dispatchedInstructions+1 &&
                    post->snapshot().stringTransfers==before.stringTransfers+transfers,
                    "Player post dispatch/copy accounting differs");
            }
            else if (actor) {
                require(actor->advance(1,bus,copies)==1,"Actor before player post did not dispatch");
                if (actor->snapshot().outcome==ActorUpdateOutcome::Returned) {
                    const auto r=actor->registers();require(r.cs==kGame && r.ip==0x7f5c,"Actor skipped player post");
                    post.emplace(r,kGame,kIdToggle);
                }
            } else {
                require(caller->advance(1,bus,copies)==1,"Actual player caller did not dispatch");
                const auto r=caller->registers();
                if (!caller->interruptInProgress() && r.cs==kGame && r.ip==0x6053)
                    actor.emplace(r,kGame,kIdToggle);
                else require(!caller->finished(),"Actual caller bypassed player actor");
            }
            ++used;
        }
        return used;
    }
};
uint64_t irqCheck(PlayerPostOperation active,Memory memory,uint8_t partialSize) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    if (partialSize) {
        const auto before=active.registers();const auto writes=memory.writes.size();
        require(before.cx>1,"Player post partial-copy IRQ lacks transfers");
        active.advance(1,bus,[](uint16_t) { return uint16_t{1}; });
        require(active.registers().ip==before.ip && active.registers().cx==before.cx-1 &&
            memory.writes.size()==writes+1 && memory.writes.back().size==partialSize,
            "Player post partial-copy transfer differs");
    }
    const auto before=active.registers();const auto deliveries=active.snapshot().timerDeliveries;
    const auto instructions=active.snapshot().timerInstructions;
    active.deliverTimerInterrupt(bus);
    bool nested=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && active.snapshot().timerDeliveries==deliveries+1,"Player post IRQ nesting/accounting differs");
    unsigned steps=0;
    while (active.interruptInProgress()) {
        require(steps++<4096,"Player post IRQ did not return");active.advance(1,bus,all);
        active=PlayerPostOperation(active.snapshot());
    }
    const auto irqInstructions=active.snapshot().timerInstructions-instructions;
    require(irqInstructions==36 && active.registers()==before && memory.word(0x40,0x6c)==101,
        "Player post IRQ did not restore CPU/tick/accounting");
    auto other=active;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!active.finished()) { require(steps++<3000000,"Player post IRQ continuation stalled");active.advance(1,bus,all); }
    while (!other.finished()) {
        require(steps++<6000000,"Player post IRQ alternate stalled");other.advance(17,otherBus,all);
        other=PlayerPostOperation(other.snapshot());
    }
    require(active.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Player post IRQ continuation grant/snapshot differs");
    bool ended=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Finished player post admitted IRQ");return irqInstructions;
}
void replay(const char* path,const char* root) {
    Reader input(path,kProjectionBytes);
    require(fingerprint(input.bytes)==kProjectionFingerprint,"Player post corpus fingerprint differs");
    for (char c : std::string("LZPST001")) require(input.number(1)==static_cast<uint8_t>(c),"Player post magic differs");
    const auto count=input.number(4);require(count==3102,"Player post corpus domain differs");
    const auto base=image(root);
    uint64_t replays=0,comparisons=0,dispatches=0,totalWrites=0,playerCalls=0,wholePaths=0,wholeLifePaths=0,irqInstructions=0;
    std::array<unsigned,3> outcomes{};
    constexpr std::array<std::array<uint16_t,3>,14> targets{{
        {{0x1000,0x7f5c,0}},{{0x1000,0x7f75,0}},{{0x1000,0x7fac,0}},{{0x1000,0x30d0,0}},
        {{0x1000,0x568a,0}},{{0x1000,0x56a8,1}},{{0x1000,0x11b0,0}},
        {{0x1920,0x94e,0}},{{0x1920,0x975,0}},{{0x1920,0x9ab,0}},
        {{0x1000,0x1287,0}},{{0x1000,0x1239,0}},{{0x1000,0x116a,2}},{{0x1000,0x8041,0}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Player post row order differs");const auto outcome=input.number(1);
        require(outcome<outcomes.size(),"Player post outcome differs");++outcomes[outcome];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        const auto seeds=input.number(4);require(seeds<65536,"Player post seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto address=input.number(4),size=input.number(4);
            require(size<=65536 && address>=0x1aa20 && address+size<=1048576 && input.at+size<=input.bytes.size(),
                "Player post seed exceeds memory");
            std::copy_n(input.bytes.begin()+input.at,size,initial.bytes.begin()+address);input.at+=size;
        }
        const auto trace=input.trace();compare(trace.front(),entry,index,0,true);
        const auto contains=[&](uint16_t ip) {
            return std::ranges::any_of(trace,[&](const auto& r) { return r.cs==kGame && r.ip==ip; });
        };
        playerCalls+=contains(0x7f59);wholePaths+=contains(0x6053);
        wholeLifePaths+=contains(0x6053) && contains(0x30a3);
        const auto writeCount=input.number(4);require(writeCount<3000000,"Player post write reserve differs");
        std::vector<Write> writes;auto expected=initial;
        for (unsigned i=0;i<writeCount;++i) {
            Write item{input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require((item.size==1 || item.size==2) && item.address+item.size<=1048576,"Player post write exceeds memory");
            writes.push_back(item);expected.store(item.address,item.value,item.size);
        }
        require(input.number(4)==0,"Player post reserved event field differs");
        unsigned mode=0;
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();Driver active(entry);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };
            size_t cursor=0;compare(active.registers(),trace.front(),index,0);++comparisons;
            while (!active.finished()) {
                require(cursor+1<trace.size(),"Player post exceeded original endpoint");
                if (!mode && active.post) {
                    const auto r=active.registers();
                    for (size_t target=0;target<targets.size();++target)
                        if (!irqSeen[target] && r.cs==targets[target][0] && r.ip==targets[target][1] &&
                            (!targets[target][2] || r.cx>1)) {
                            irqInstructions+=irqCheck(*active.post,memory,static_cast<uint8_t>(targets[target][2]));
                            irqSeen[target]=true;
                        }
                }
                const auto used=active.advance(budget,bus,copies);
                require(used>0 && used<=budget,"Player post grant stalled");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Player post trace exceeded endpoint");const auto before=trace[cursor];
                    if (((before.cs==0x1920 && before.ip==0x91f) ||
                        (before.cs==0x18ac && before.ip==0x5d2) ||
                        (before.cs==kGame && (before.ip==0x116a || before.ip==0x56a8 || before.ip==0x56b3))) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Player post REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                active.restore();compare(active.registers(),trace[cursor],index,cursor);++comparisons;
            }
            compare(active.registers(),endpoint,index,cursor,true);require(cursor+1==trace.size(),"Player post trace extent differs");
            require(active.post.has_value(),"Whole actor stopped before post continuation");
            const auto actual=active.post->snapshot().outcome;
            require((outcome==0 && actual==PlayerPostOutcome::Caller) ||
                (outcome==1 && actual==PlayerPostOutcome::Returned) ||
                (outcome==2 && actual==PlayerPostOutcome::RuntimeError),"Player post outcome differs from original");
            if (memory.writes!=writes || memory.bytes!=expected.bytes) {
                std::cerr<<"write_case="<<index<<" mode="<<mode<<" writes="<<memory.writes.size()<<'/'<<writes.size()<<'\n';
                const auto mismatch=std::mismatch(memory.writes.begin(),memory.writes.end(),writes.begin(),writes.end());
                if (mismatch.first!=memory.writes.end() && mismatch.second!=writes.end())
                    std::cerr<<"first_write="<<std::hex<<mismatch.first->address<<'/'<<mismatch.second->address
                        <<" value="<<mismatch.first->value<<'/'<<mismatch.second->value<<std::dec<<'\n';
                throw std::runtime_error("Player post ordered writes or complete memory differ");
            }
            ++replays;dispatches+=active.post->snapshot().dispatchedInstructions;
            const auto saved=active.post->snapshot();
            require(active.advance(17,bus,copies)==0 && active.post->snapshot()==saved,"Finished player post dispatched work");
            ++mode;
        }
        totalWrites+=writes.size();
    }
    require(input.at==input.bytes.size(),"Player post fixture tail differs");
    for (size_t i=0;i<irqSeen.size();++i) if (!irqSeen[i]) std::cerr<<"missing_irq_target="<<std::hex<<targets[i][0]<<':'<<targets[i][1]<<std::dec<<'\n';
    require(std::ranges::all_of(irqSeen,[](bool yes) { return yes; }),"Player post IRQ target coverage differs");
    require(outcomes==std::array<unsigned,3>{2422,600,80} && playerCalls==24 && wholePaths==50 && wholeLifePaths==32,
        "Player post path coverage differs");
    std::cout<<"player_post_original=ok cases="<<count<<" replays="<<replays<<" comparisons="<<comparisons
        <<" dispatches="<<dispatches<<" writes="<<totalWrites<<" player_calls="<<playerCalls
        <<" whole_actor_paths="<<wholePaths<<" whole_life_loss_paths="<<wholeLifePaths
        <<" caller_returns="<<outcomes[0]<<" divide_returns="<<outcomes[1]<<" runtime_errors="<<outcomes[2]
        <<" computed_irq_cases="<<irqSeen.size()<<" irq_instructions="<<irqInstructions
        <<" partial_copy_irqs=2 full_memory=1 canonical_mz=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=kGame;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3fdc;r.ip=0x7f5c;r.flags=0x202;
    PlayerPostOperation active(r,kGame,kIdToggle);Memory memory;const auto bus=memory.bus();
    const auto all=[](uint16_t n) { return n; };
    const auto initial=active.snapshot();
    require(active.advance(0,bus,all)==0 && active.snapshot()==initial,"Zero player post budget changed state");
    unsigned rejected=0;
    const auto reject=[&](PlayerPostSnapshot s) {
        try { (void)PlayerPostOperation(s); } catch (const std::invalid_argument&) { ++rejected; }
    };
    auto s=initial;s.gameSegment=0x1001;reject(s);
    s=initial;s.idToggleMask=1;reject(s);
    s=initial;s.entry=static_cast<PlayerPostEntry>(255);reject(s);
    s=initial;s.outcome=static_cast<PlayerPostOutcome>(255);reject(s);
    s=initial;s.timerInstructions=1;reject(s);
    s=initial;s.registers.ds=0x4000;reject(s);
    s=initial;s.registers.ip=0x8044;reject(s);
    s=initial;s.registers.cs=0x1920;s.registers.ip=0xe2;reject(s);
    s=initial;s.outcome=PlayerPostOutcome::Returned;reject(s);
    s=initial;s.outcome=PlayerPostOutcome::Caller;reject(s);
    s=initial;s.outcome=PlayerPostOutcome::RuntimeError;reject(s);
    s=initial;s.entry=PlayerPostEntry::ScoreDivide;reject(s);
    s=initial;s.entry=PlayerPostEntry::ScoreDivide;s.registers.cs=0x1920;s.registers.ip=0x4df;reject(s);
    s=initial;s.entry=PlayerPostEntry::ScoreDivide;s.registers.cs=0x1920;s.registers.ip=0x945;
    s.registers.ds=0x4000;reject(s);
    auto terminal=initial;terminal.registers.ip=0x8044;terminal.outcome=PlayerPostOutcome::Caller;
    s=terminal;++s.callerSs;reject(s);s=terminal;++s.callerSp;reject(s);s=terminal;++s.callerBp;reject(s);
    require(rejected==17,"Player post rejection coverage differs");
    r.ip=0x7f5d;bool wrongEntry=false;
    try { (void)PlayerPostOperation(r,kGame,kIdToggle); } catch (const std::invalid_argument&) { wrongEntry=true; }
    require(wrongEntry,"Player post admitted wrong entry");r.ip=0x7f5c;r.flags&=~uint32_t{0x200};
    PlayerPostOperation masked(r,kGame,kIdToggle);const auto before=masked.snapshot();bool blocked=false;
    try { masked.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked && masked.snapshot()==before && memory.writes.empty(),"Masked player post IRQ changed state");
    PlayerPostOperation ended(terminal);const auto saved=ended.snapshot();bool stopped=false;
    try { ended.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { stopped=true; }
    require(stopped && ended.advance(17,bus,all)==0 && ended.snapshot()==saved,"Finished player post changed state");
    for (uint16_t returnIp : {uint16_t{0x7f00},uint16_t{0x8044}}) {
        auto divide=initial;divide.entry=PlayerPostEntry::ScoreDivide;divide.registers.cs=0x1920;
        divide.registers.ip=0x9ab;divide.registers.sp=0x3fe0;
        memory.store(Memory::address(r.ss,0x3fe0),returnIp);memory.store(Memory::address(r.ss,0x3fe2),kGame);
        PlayerPostOperation farReturn(divide);
        require(farReturn.advance(1,bus,all)==1 && farReturn.snapshot().outcome==PlayerPostOutcome::Returned &&
            farReturn.registers().ip==returnIp && farReturn.registers().sp==initial.callerSp && memory.writes.empty(),
            "Player post signed helper RETF boundary precedence differs");
        require(farReturn.advance(1,bus,all)==0,"Signed helper returned twice");
    }
    std::cout<<"player_post_unit=ok state_rejections=17 entry_rejection=1 masked_irq=1 zero_budget=1 terminal_no_work=1 far_return_controls=2\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else if (argc==3) replay(argv[1],argv[2]);
        else throw std::runtime_error("Expected fixture and canonical root");
        return 0;
    } catch (const std::exception& error) { std::cerr<<"player_post=failed "<<error.what()<<'\n';return 1; }
}
