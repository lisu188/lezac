#include "core/actor_update.hpp"

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
constexpr size_t kProjectionBytes=124154658;
constexpr uint64_t kProjectionFingerprint=0x5d2c973510037512ull;
constexpr std::array members{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
    &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
    &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
    &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip};
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    explicit Reader(const std::filesystem::path& path,size_t expected) {
        require(std::filesystem::file_size(path)==expected,"Actor update input size differs");
        std::ifstream input(path,std::ios::binary);require(input.good(),"Missing actor update input");
        bytes={std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
        require(bytes.size()==expected,"Actor update input extent differs");
    }
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated actor update fixture");
        uint32_t value=0;for (unsigned i=0;i<n;++i) value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;for (auto member : members) r.*member=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace() {
        const auto count=number(4);require(count>1 && count<=3000000,"Actor update trace reserve differs");
        std::vector<DosGetTimeRegisters> rows;rows.reserve(count);DosGetTimeRegisters previous{};
        for (unsigned i=0;i<count;++i) {
            const auto mask=number(2);require(mask<0x4000 && (i || mask==0x3fff),"Actor delta mask differs");
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
            [](uint16_t p) -> uint8_t { require(p==0x61,"Unexpected actor IRQ input");return 0; },
            [](uint16_t p,uint8_t) { require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected actor IRQ output"); }
        };
    }
};
Memory image(const std::filesystem::path& root) {
    Reader exe(root/"LEZAC.EXE",52384);
    require(fingerprint(exe.bytes)==0x2ae32f89b95e200bull,"Actor update MZ fingerprint differs");
    require(exe.number(2)==0x5a4d,"Actor update MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<exe.bytes.size() && table+relocations*4<=header &&
        exe.bytes.size()-header+0x10000<=1048576,"Actor update MZ layout differs");
    Memory result;std::copy(exe.bytes.begin()+header,exe.bytes.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto offset=exe.number(4),at=0x10000+(offset>>16)*16+(offset&65535);
        require(at+1<result.bytes.size(),"Actor update relocation exceeds memory");
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
        throw std::runtime_error("Actor update register/control trace differs");
    }
}
struct Driver {
    std::optional<FrameActorEntryOperation> caller;
    std::optional<ActorUpdateOperation> actor;
    explicit Driver(DosGetTimeRegisters entry) {
        if (entry.ip==0x6053) actor.emplace(entry,kGame,kIdToggle);
        else { require(entry.ip==0x7ebb,"Actor replay entry differs");caller.emplace(entry,kGame,kIdToggle); }
    }
    DosGetTimeRegisters registers() const { return actor ? actor->registers() : caller->registers(); }
    bool finished() const { return actor && actor->finished(); }
    void restore() {
        if (actor) actor=ActorUpdateOperation(actor->snapshot());
        else caller=FrameActorEntryOperation(caller->snapshot());
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const ActorUpdateOperation::CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (actor) {
                const auto before=actor->snapshot().dispatchedInstructions;
                require(actor->advance(1,bus,copies)==1 && actor->snapshot().dispatchedInstructions==before+1,
                    "Actor dispatch accounting differs");
            } else {
                require(caller->advance(1,bus,copies)==1,"Actual actor caller did not dispatch");
                const auto r=caller->registers();
                if (!caller->interruptInProgress() && r.cs==kGame && r.ip==0x6053)
                    actor.emplace(r,kGame,kIdToggle);
                else require(!caller->finished(),"Actual caller bypassed actor");
            }
            ++used;
        }
        return used;
    }
};
uint64_t irqCheck(ActorUpdateOperation active,Memory memory,bool partial) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto all=[](uint16_t n) { return n; };
    if (partial) {
        const auto before=active.registers();const auto writes=memory.writes.size();
        require(before.cx>1,"Actor partial-copy IRQ lacks bytes");
        active.advance(1,bus,[](uint16_t) { return uint16_t{1}; });
        require(active.registers().ip==before.ip && active.registers().cx==before.cx-1 &&
            memory.writes.size()==writes+1,"Actor partial-copy transfer differs");
    }
    const auto before=active.registers();const auto deliveries=active.snapshot().timerDeliveries;
    const auto instructions=active.snapshot().timerInstructions;
    active.deliverTimerInterrupt(bus);
    bool nested=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { nested=true; }
    require(nested && active.snapshot().timerDeliveries==deliveries+1,"Actor IRQ nesting/accounting differs");
    unsigned steps=0;
    while (active.interruptInProgress()) {
        require(steps++<4096,"Actor IRQ did not return");active.advance(1,bus,all);
        active=ActorUpdateOperation(active.snapshot());
    }
    const auto irqInstructions=active.snapshot().timerInstructions-instructions;
    require(irqInstructions==36 && active.registers()==before && memory.word(0x40,0x6c)==101,
        "Actor IRQ did not restore CPU/tick/accounting");
    auto other=active;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!active.finished()) { require(steps++<3000000,"Actor IRQ continuation stalled");active.advance(1,bus,all); }
    while (!other.finished()) {
        require(steps++<6000000,"Actor IRQ alternate stalled");other.advance(17,otherBus,all);
        other=ActorUpdateOperation(other.snapshot());
    }
    require(active.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Actor IRQ continuation grant/snapshot differs");
    bool ended=false;try { active.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { ended=true; }
    require(ended,"Returned actor admitted IRQ");return irqInstructions;
}
void replay(const char* path,const char* root) {
    Reader input(path,kProjectionBytes);
    require(fingerprint(input.bytes)==kProjectionFingerprint,"Actor update corpus fingerprint differs");
    for (char c : std::string("LZACT001")) require(input.number(1)==static_cast<uint8_t>(c),"Actor update magic differs");
    const auto count=input.number(4);require(count==7188,"Actor update corpus domain differs");
    const auto base=image(root);
    uint64_t replays=0,comparisons=0,dispatches=0,totalWrites=0,playerCalls=0,nonplayerCalls=0,irqInstructions=0;
    std::array<unsigned,3> outcomes{};
    constexpr std::array<std::array<uint16_t,2>,11> targets{{
        {{0x1000,0x6053}},{{0x1000,0x615a}},{{0x1000,0x654e}},{{0x1000,0x65a2}},{{0x1000,0x65a8}},
        {{0x1000,0x6737}},{{0x1000,0x7018}},{{0x1000,0x732c}},{{0x1000,0x73e5}},{{0x1000,0x7780}},{{0x1920,0x91f}}
    }};
    std::array<bool,targets.size()> irqSeen{};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Actor update row order differs");const auto outcome=input.number(1);
        require(outcome<outcomes.size(),"Actor update outcome differs");++outcomes[outcome];
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        const auto seeds=input.number(4);require(seeds<65536,"Actor update seed reserve differs");
        for (unsigned i=0;i<seeds;++i) {
            const auto address=input.number(4),size=input.number(4);
            require(size<=65536 && address>=0x1aa20 && address+size<=1048576 && input.at+size<=input.bytes.size(),
                "Actor update seed exceeds memory");
            std::copy_n(input.bytes.begin()+input.at,size,initial.bytes.begin()+address);input.at+=size;
        }
        const auto trace=input.trace();compare(trace.front(),entry,index,0,true);
        const auto contains=[&](uint16_t ip) {
            return std::ranges::any_of(trace,[&](const auto& r) { return r.cs==kGame && r.ip==ip; });
        };
        require(contains(0x6053),"Actor update skipped actual entry");
        playerCalls+=contains(0x7f59);nonplayerCalls+=contains(0x7ee1);
        if (!outcome) require(trace[trace.size()-2].ip==0x7780,"Actor update omitted RET");
        const auto writeCount=input.number(4);require(writeCount<3000000,"Actor update write reserve differs");
        std::vector<Write> writes;auto expected=initial;
        for (unsigned i=0;i<writeCount;++i) {
            Write item{input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require((item.size==1 || item.size==2) && item.address+item.size<=1048576,"Actor update write exceeds memory");
            writes.push_back(item);expected.store(item.address,item.value,item.size);
        }
        require(input.number(4)==0,"Actor update reserved event field differs");
        unsigned mode=0;
        for (uint16_t limit : {uint16_t{1},uint16_t{2},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
            auto memory=initial;const auto bus=memory.bus();Driver active(entry);
            const auto copies=[=](uint16_t n) { return std::min(n,limit); };
            size_t cursor=0;compare(active.registers(),trace.front(),index,0);++comparisons;
            while (!active.finished()) {
                require(cursor+1<trace.size(),"Actor update exceeded original endpoint");
                if (!mode && active.actor) {
                    const auto r=active.registers();
                    for (size_t target=0;target<targets.size();++target)
                        if (!irqSeen[target] && r.cs==targets[target][0] && r.ip==targets[target][1] &&
                            (target+1<targets.size() || r.cx>1)) {
                            irqInstructions+=irqCheck(*active.actor,memory,target+1==targets.size());
                            irqSeen[target]=true;
                        }
                }
                const auto used=active.advance(budget,bus,copies);
                require(used>0 && used<=budget,"Actor update grant stalled");
                for (uint64_t step=0;step<used;++step) {
                    require(cursor+1<trace.size(),"Actor update trace exceeded endpoint");const auto before=trace[cursor];
                    if (((before.cs==0x1920 && before.ip==0x91f) ||
                        (before.cs==0x18ac && before.ip==0x5d2)) && before.cx) {
                        cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Actor update REP trace truncated");
                        if (trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0) ++cursor;
                    } else ++cursor;
                }
                active.restore();compare(active.registers(),trace[cursor],index,cursor);++comparisons;
            }
            compare(active.registers(),endpoint,index,cursor,true);require(cursor+1==trace.size(),"Actor trace extent differs");
            const auto actual=active.actor->snapshot().outcome;
            require((outcome==0 && actual==ActorUpdateOutcome::Returned) ||
                (outcome==1 && actual==ActorUpdateOutcome::RuntimeError) ||
                (outcome==2 && actual==ActorUpdateOutcome::DivideError),"Actor outcome differs from original");
            require(memory.writes==writes && memory.bytes==expected.bytes,"Actor ordered writes or complete memory differ");
            ++replays;dispatches+=active.actor->snapshot().dispatchedInstructions;
            const auto saved=active.actor->snapshot();
            require(active.advance(17,bus,copies)==0 && active.actor->snapshot()==saved,"Finished actor dispatched work");
            ++mode;
        }
        totalWrites+=writes.size();
    }
    require(input.at==input.bytes.size(),"Actor update fixture tail differs");
    require(std::ranges::all_of(irqSeen,[](bool yes) { return yes; }),"Actor IRQ target coverage differs");
    std::cout<<"actor_update_original=ok cases="<<count<<" replays="<<replays<<" comparisons="<<comparisons
        <<" dispatches="<<dispatches<<" writes="<<totalWrites<<" player_calls="<<playerCalls
        <<" nonplayer_calls="<<nonplayerCalls<<" returns="<<outcomes[0]<<" runtime_errors="<<outcomes[1]
        <<" divide_errors="<<outcomes[2]<<" computed_irq_cases="<<irqSeen.size()<<" irq_instructions="<<irqInstructions
        <<" partial_copy_irqs=1 full_memory=1 canonical_mz=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r{};r.cs=kGame;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fde;r.bp=0x3fdc;r.ip=0x6053;r.flags=0x202;
    ActorUpdateOperation active(r,kGame,kIdToggle);Memory memory;const auto bus=memory.bus();
    const auto all=[](uint16_t n) { return n; };
    const auto initial=active.snapshot();
    require(active.advance(0,bus,all)==0 && active.snapshot()==initial,"Zero actor budget changed state");
    unsigned rejected=0;
    const auto reject=[&](ActorUpdateSnapshot s) {
        try { (void)ActorUpdateOperation(s); } catch (const std::invalid_argument&) { ++rejected; }
    };
    auto s=initial;s.gameSegment=0x1001;reject(s);
    s=initial;s.idToggleMask=1;reject(s);
    s=initial;s.outcome=static_cast<ActorUpdateOutcome>(255);reject(s);
    s=initial;s.timerInstructions=1;reject(s);
    s=initial;std::get<FrameActorContactSnapshot>(s.callee).idToggleMask=0;reject(s);
    s=initial;std::get<FrameActorContactSnapshot>(s.callee).outcome=FrameActorContactOutcome::TileBehavior;reject(s);
    s=initial;s.outcome=ActorUpdateOutcome::Returned;reject(s);
    s=initial;s.outcome=ActorUpdateOutcome::RuntimeError;reject(s);
    s=initial;s.outcome=ActorUpdateOutcome::DivideError;reject(s);
    r.ip=0x7ebb;s=initial;s.callee=FrameActorContactOperation(r,kGame,kIdToggle).snapshot();reject(s);r.ip=0x6053;
    const auto beforeHelpers=rejected;
    for (const auto entry : {ActorMotionEntry::TileFracture,ActorMotionEntry::TileSample,ActorMotionEntry::Friction}) {
        r.ip=entry==ActorMotionEntry::TileFracture ? 0x370e : entry==ActorMotionEntry::TileSample ? 0x5afd : 0x5b86;
        s=initial;s.callee=ActorMotionOperation(r,kGame,kIdToggle,entry).snapshot();reject(s);
    }
    require(rejected==beforeHelpers+3,"Actor update admitted a standalone helper phase");
    auto returned=initial;r.ip=0x7f5c;r.sp=returned.callerSp;
    ActorFinishSnapshot tail{r,kGame,kIdToggle};tail.outcome=ActorFinishOutcome::Returned;
    returned.callee=tail;returned.outcome=ActorUpdateOutcome::Returned;
    s=returned;++s.callerSs;reject(s);s=returned;++s.callerSp;reject(s);s=returned;++s.callerBp;reject(s);
    s=returned;tail.registers.cs=0x1920;tail.registers.ip=0xe2;s.callee=tail;
    s.outcome=ActorUpdateOutcome::RuntimeError;reject(s);
    require(rejected==17,"Actor update rejection coverage differs");
    r.ip=0x6054;bool wrongEntry=false;
    try { (void)ActorUpdateOperation(r,kGame,kIdToggle); } catch (const std::invalid_argument&) { wrongEntry=true; }
    require(wrongEntry,"Actor update admitted wrong entry");r.ip=0x6053;r.flags&=~uint32_t{0x200};
    ActorUpdateOperation masked(r,kGame,kIdToggle);const auto before=masked.snapshot();bool blocked=false;
    try { masked.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { blocked=true; }
    require(blocked && masked.snapshot()==before && memory.writes.empty(),"Masked actor IRQ changed state");
    ActorUpdateOperation ended(returned);const auto terminal=ended.snapshot();bool stopped=false;
    try { ended.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { stopped=true; }
    require(stopped && ended.advance(17,bus,all)==0 && ended.snapshot()==terminal,"Returned actor changed state");
    std::cout<<"actor_update_unit=ok state_rejections=17 entry_rejection=1 masked_irq=1 zero_budget=1 terminal_no_work=1\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else if (argc==3) replay(argv[1],argv[2]);
        else throw std::runtime_error("Expected fixture and canonical root");
        return 0;
    } catch (const std::exception& error) { std::cerr<<"actor_update=failed "<<error.what()<<'\n';return 1; }
}
