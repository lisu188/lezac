#pragma once

#include "core/actor_finish.hpp"
#include "core/frame_hud.hpp"

namespace lezac::core {

enum class PlayerPostEntry { Caller, ScoreDivide };
enum class PlayerPostOutcome { Running, Caller, Returned, RuntimeError };
struct PlayerPostSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0,callerSs=0,callerSp=0,callerBp=0;
    uint32_t idToggleMask=0;
    PlayerPostEntry entry=PlayerPostEntry::Caller;
    PlayerPostOutcome outcome=PlayerPostOutcome::Running;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0,stringTransfers=0;
    bool operator==(const PlayerPostSnapshot&) const = default;
};

// Original player return -> health/life/score HUD -> 8044 caller continuation.
// ScoreDivide separately executes the actual signed RTL helper and far return.
class PlayerPostOperation {
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    PlayerPostOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle,
                        PlayerPostEntry entry=PlayerPostEntry::Caller)
        : state_{r,game,r.ss,static_cast<uint16_t>(r.sp+(entry==PlayerPostEntry::ScoreDivide ? 4u : 0u)),
            r.bp,idToggle,entry} {
        if (r.ds!=static_cast<uint16_t>(game+0xaa2) ||
            (entry==PlayerPostEntry::Caller ? (r.cs!=game || r.ip!=0x7f5c) :
             (r.cs!=static_cast<uint16_t>(game+0x920) || r.ip!=0x945)))
            throw std::invalid_argument("Player post entry differs");
        validate();
    }
    explicit PlayerPostOperation(PlayerPostSnapshot state) : state_(std::move(state)) { validate(); }
    const PlayerPostSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return state_.timer ? fromTimer(state_.timer->registers) : state_.registers; }
    bool finished() const noexcept { return state_.outcome!=PlayerPostOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || state_.timer || !(state_.registers.flags&0x200u))
            throw std::logic_error("Player post IRQ is not eligible");
        auto r=state_.registers;
        r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,static_cast<uint16_t>(r.flags));
        r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,r.cs);
        r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,r.ip);
        r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
        state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation irq(*state_.timer);
                if (irq.advance(1,bus)!=1) throw std::domain_error("Player post IRQ did not dispatch");
                ++state_.timerInstructions;
                if (irq.returned()) { state_.registers=fromTimer(irq.snapshot().registers);state_.timer.reset(); }
                else state_.timer=irq.snapshot();
            } else {
                const auto before=state_.registers;
                const bool returned=state_.entry==PlayerPostEntry::ScoreDivide && before.cs==library() && before.ip==0x9ab;
                instruction(bus,copies);
                const auto& r=state_.registers;
                if (returned) state_.outcome=PlayerPostOutcome::Returned;
                else if (r.cs==state_.gameSegment && r.ip==0x8044) state_.outcome=PlayerPostOutcome::Caller;
                if (r.cs==library() && r.ip==0xe2) state_.outcome=PlayerPostOutcome::RuntimeError;
            }
            ++used;++state_.dispatchedInstructions;
            if (finished()) validate();
        }
        return used;
    }
private:
    PlayerPostSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    void validate() const {
        const auto& r=state_.registers;
        if (registers().ss!=state_.callerSs ||
            (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            (state_.entry!=PlayerPostEntry::Caller && state_.entry!=PlayerPostEntry::ScoreDivide) ||
            (state_.outcome!=PlayerPostOutcome::Running && state_.outcome!=PlayerPostOutcome::Caller &&
             state_.outcome!=PlayerPostOutcome::Returned && state_.outcome!=PlayerPostOutcome::RuntimeError) ||
            state_.timerInstructions>state_.dispatchedInstructions ||
            (r.cs!=state_.gameSegment && r.cs!=library()) ||
            (r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) &&
                !(r.cs==state_.gameSegment && r.ip>=0x30d0 && r.ip<=0x30d8)) ||
            (state_.outcome==PlayerPostOutcome::Running &&
                ((r.cs==library() && r.ip==0xe2) || (r.cs==state_.gameSegment && r.ip==0x8044))) ||
            (state_.outcome==PlayerPostOutcome::Running && state_.entry==PlayerPostEntry::ScoreDivide &&
                (r.cs!=library() || r.ip<0x945 || r.ip>0x9b0)) ||
            (state_.outcome==PlayerPostOutcome::Caller &&
                (state_.entry!=PlayerPostEntry::Caller || r.cs!=state_.gameSegment || r.ip!=0x8044)) ||
            (state_.outcome==PlayerPostOutcome::Returned &&
                (state_.entry!=PlayerPostEntry::ScoreDivide || r.cs!=state_.gameSegment)) ||
            (state_.outcome==PlayerPostOutcome::RuntimeError && (r.cs!=library() || r.ip!=0xe2)) ||
            ((state_.outcome==PlayerPostOutcome::Caller || state_.outcome==PlayerPostOutcome::Returned) &&
                (r.sp!=state_.callerSp || r.bp!=state_.callerBp)) ||
            (state_.timer && (finished() || state_.timer->returned || !state_.timer->biosWrapper ||
                state_.timer->gameSegment!=state_.gameSegment ||
                state_.timer->dataSegment!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
                state_.timer->idToggleMask!=state_.idToggleMask)))
            throw std::invalid_argument("Player post continuation ownership differs");
        if (state_.timer) (void)TimerIrqOperation(*state_.timer);
    }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value,bool byte=false) {
        value=static_cast<uint16_t>(value&(byte ? 255u : 65535u));
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value,byte);return value;
    }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false,bool byte=false,bool carry=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u,extra=carry && flag(1) ? 1u : 0u;
        const uint32_t wide=subtract ? uint32_t{a}-b-extra : uint32_t{a}+b+extra;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t f=valueFlags(value,byte)|((a^b^value)&16u);
        if (subtract ? uint32_t{a}<uint32_t{b}+extra : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^value)&sign) : (~(a^b)&(a^value)&sign)) f|=0x800;
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|f;return value;
    }
    uint16_t increment(uint16_t value,bool subtract=false,bool byte=false) {
        const auto carry=state_.registers.flags&1u;value=arithmetic(value,1,subtract,byte);
        state_.registers.flags=(state_.registers.flags&~uint32_t{1})|carry;return value;
    }
    uint16_t shift(uint16_t value,unsigned count) {
        for (unsigned i=0;i<count;++i) {
            const auto old=value;value=static_cast<uint16_t>(value<<1);
            state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value)|16u|
                (old&0x8000u ? 1u : 0u)|((old^value)&0x8000u ? 0x800u : 0u);
        }
        return value;
    }
    uint16_t rotateCarry(uint16_t value) {
        const auto carry=flag(1);const auto next=value>>15;
        value=static_cast<uint16_t>((value<<1)|(carry ? 1u : 0u));
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x801})|next|
            (((value>>15)^next) ? 0x800u : 0u);return value;
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.registers;const auto game=state_.gameSegment;
        if (r.cs==library() && r.ip>=0x945 && r.ip<=0x9b0) { divisionInstruction(bus);return; }
        if ((r.cs==library() && r.ip>=0x4df && r.ip<=0x4f4) ||
            (r.cs==game && r.ip>=0x6ab && r.ip<0x709)) {
            ActorFinishOperation child(ActorFinishSnapshot{r,game,state_.idToggleMask});
            if (child.advance(1,bus,copies)!=1) throw std::domain_error("Player post runtime helper stalled");
            r=child.registers();return;
        }
        if (r.cs!=game) throw std::domain_error("Player post left recovered code");
        if (r.ip>=0x1156 && r.ip<=0x1173) {
            FrameHudOperation child(FrameHudSnapshot{r,game,0,state_.idToggleMask,true});
            if (child.advance(1,bus,copies)!=1) throw std::domain_error("Player score font helper stalled");
            r=child.registers();state_.stringTransfers+=child.snapshot().stringTransfers;return;
        }
        if (r.ip>=0x165a && r.ip<=0x167d) {
            ActorContactOperation child(ActorContactSnapshot{r,game,state_.idToggleMask});
            if (child.advance(1,bus)!=1) throw std::domain_error("Player post sound helper stalled");
            r=child.registers();return;
        }
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto data=[&](uint16_t at) { return bus.readByte(r.ds,at); };
        const auto word=[&](uint16_t at) { return bus.readWord(r.ds,at); };
        const auto bd=[&](uint16_t at,uint8_t value) { bus.writeByte(r.ds,at,value); };
        const auto wd=[&](uint16_t at,uint16_t value) { bus.writeWord(r.ds,at,value); };
        const auto local=[&](int at) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+at)); };
        const auto lb=[&](int at) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+at)); };
        const auto store=[&](int at,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+at),value); };
        const auto al=[&](uint16_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|(value&255u)); };
        const auto dl=[&](uint8_t value) { r.dx=static_cast<uint16_t>((r.dx&0xff00u)|value); };
        const auto zeroAh=[&] { r.ax&=255u;(void)logic(0,true); };
        const auto branch=[&](bool yes,uint16_t target,uint16_t next) { r.ip=yes ? target : next; };
        const auto call=[&](uint16_t target,uint16_t next) { push(next);r.ip=target; };
        const auto farCall=[&](uint16_t target,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=target; };
        const auto les=[&](uint16_t at) { r.di=word(at);r.es=word(static_cast<uint16_t>(at+2u)); };
        const auto localLes=[&](int at) { r.di=local(at);r.es=local(at+2); };
        const auto multiplyActor=[&](uint16_t value) {
            const int32_t product=int32_t{std::bit_cast<int16_t>(value)}*38;
            r.di=static_cast<uint16_t>(product);
            r.flags=(r.flags&~uint32_t{0x801})|((product < -32768 || product > 32767) ? 0x801u : 0u);
        };
        switch (r.ip) {
        case 0x7f5c:multiplyActor(word(0x2082));r.ip=0x7f61;break;
        case 0x7f61:arithmetic(data(static_cast<uint16_t>(r.di+0x1b77u)),2,true,true);r.ip=0x7f66;break;
        case 0x7f66:branch(flag(0x40),0x7f79,0x7f68);break;
        case 0x7f68:r.di=word(0x2082);r.ip=0x7f6c;break;
        case 0x7f6c:al(data(static_cast<uint16_t>(r.di+0x79e7u)));r.ip=0x7f70;break;
        case 0x7f70:multiplyActor(word(0x2082));r.ip=0x7f75;break;
        case 0x7f75:bd(static_cast<uint16_t>(r.di+0x1b86u),static_cast<uint8_t>(arithmetic(data(static_cast<uint16_t>(r.di+0x1b86u)),r.ax&255u,true,true)));r.ip=0x7f79;break;
        case 0x7f79:r.di=word(0x2082);r.ip=0x7f7d;break;
        case 0x7f7d:arithmetic(data(static_cast<uint16_t>(r.di+0x79e7u)),0,true,true);r.ip=0x7f82;break;
        case 0x7f82:branch(flag(1)||flag(0x40),0x7f92,0x7f84);break;
        case 0x7f84:wd(0x2074,45);r.ip=0x7f8a;break;
        case 0x7f8a:bd(0x799f,4);r.ip=0x7f8f;break;
        case 0x7f8f:call(0x165a,0x7f92);break;
        case 0x7f92:multiplyActor(word(0x2082));r.ip=0x7f97;break;
        case 0x7f97:al(data(static_cast<uint16_t>(r.di+0x1b86u)));r.ip=0x7f9b;break;
        case 0x7f9b:zeroAh();r.ip=0x7f9d;break;
        case 0x7f9d:wd(0x2074,r.ax);r.ip=0x7fa0;break;
        case 0x7fa0:arithmetic(word(0x2074),200,true);r.ip=0x7fa6;break;
        case 0x7fa6:branch(flag(1)||flag(0x40),0x7faf,0x7fa8);break;
        case 0x7fa8:al(data(0x2082));r.ip=0x7fab;break;
        case 0x7fab:push(r.ax);r.ip=0x7fac;break;
        case 0x7fac:call(0x30a3,0x7faf);break;
        case 0x7faf:r.di=word(0x2082);r.ip=0x7fb3;break;
        case 0x7fb3:al(data(static_cast<uint16_t>(r.di+0x79ebu)));r.ip=0x7fb7;break;
        case 0x7fb7:zeroAh();r.ip=0x7fb9;break;
        case 0x7fb9:arithmetic(r.ax,word(0x2074),true);r.ip=0x7fbd;break;
        case 0x7fbd:branch(flag(0x40),0x7fdb,0x7fbf);break;
        case 0x7fbf:al(data(0x2074));r.ip=0x7fc2;break;
        case 0x7fc2:r.di=word(0x2082);r.ip=0x7fc6;break;
        case 0x7fc6:bd(static_cast<uint16_t>(r.di+0x79ebu),static_cast<uint8_t>(r.ax));r.ip=0x7fca;break;
        case 0x7fca:r.di=word(0x2082);r.ip=0x7fce;break;
        case 0x7fce:r.di=shift(r.di,1);r.ip=0x7fd0;break;
        case 0x7fd0:r.ax=word(static_cast<uint16_t>(r.di+0x79f2u));r.ip=0x7fd4;break;
        case 0x7fd4:r.ax=increment(r.ax);r.ip=0x7fd5;break;
        case 0x7fd5:wd(0x2072,r.ax);r.ip=0x7fd8;break;
        case 0x7fd8:call(0x568a,0x7fdb);break;
        case 0x7fdb:arithmetic(word(0x2082),1,true);r.ip=0x7fe0;break;
        case 0x7fe0:branch(!flag(0x40),0x7ff5,0x7fe2);break;
        case 0x7fe2:r.ax=logic(0);r.ip=0x7fe4;break;
        case 0x7fe4:wd(0x2072,r.ax);r.ip=0x7fe7;break;
        case 0x7fe7:r.ax=0x785a;r.ip=0x7fea;break;
        case 0x7fea:r.dx=r.ds;r.ip=0x7fec;break;
        case 0x7fec:wd(0x78b6,r.ax);r.ip=0x7fef;break;
        case 0x7fef:wd(0x78b8,r.dx);r.ip=0x7ff3;break;
        case 0x7ff3:r.ip=0x8007;break;
        case 0x7ff5:r.ax=word(0x2084);r.ip=0x7ff8;break;
        case 0x7ff8:wd(0x2072,r.ax);r.ip=0x7ffb;break;
        case 0x7ffb:r.ax=0x7888;r.ip=0x7ffe;break;
        case 0x7ffe:r.dx=r.ds;r.ip=0x8000;break;
        case 0x8000:wd(0x78b6,r.ax);r.ip=0x8003;break;
        case 0x8003:wd(0x78b8,r.dx);r.ip=0x8007;break;
        case 0x8007:les(0x78b6);r.ip=0x800b;break;
        case 0x800b:arithmetic(bus.readByte(r.es,static_cast<uint16_t>(r.di+44u)),2,true,true);r.ip=0x8010;break;
        case 0x8010:branch(!flag(1),0x8044,0x8012);break;
        case 0x8012:les(0x78b6);r.ip=0x8016;break;
        case 0x8016:arithmetic(bus.readByte(r.es,static_cast<uint16_t>(r.di+44u)),0,true,true);r.ip=0x801b;break;
        case 0x801b:branch(!flag(0x40),0x8026,0x801d);break;
        case 0x801d:les(0x78b6);r.ip=0x8021;break;
        case 0x8021:push(r.es);r.ip=0x8022;break;
        case 0x8022:push(r.di);r.ip=0x8023;break;
        case 0x8023:call(0x11b0,0x8026);break;
        case 0x8026:r.di=word(0x2082);r.ip=0x802a;break;
        case 0x802a:r.di=shift(r.di,1);r.ip=0x802c;break;
        case 0x802c:r.ax=word(static_cast<uint16_t>(r.di+0x79f2u));r.ip=0x8030;break;
        case 0x8030:r.ax=arithmetic(r.ax,0xdc00);r.ip=0x8033;break;
        case 0x8033:wd(0x2074,r.ax);r.ip=0x8036;break;
        case 0x8036:push(word(0x2072));r.ip=0x803a;break;
        case 0x803a:call(0x1287,0x803d);break;
        case 0x803d:push(word(0x2072));r.ip=0x8041;break;
        case 0x8041:call(0x1239,0x8044);break;
        case 0x568a:r.cx=word(0x2074);r.ip=0x568e;break;
        case 0x568e:arithmetic(r.cx,100,true);r.ip=0x5691;break;
        case 0x5691:branch(!flag(1)&&!flag(0x40),0x56b5,0x5693);break;
        case 0x5693:r.ax=0xa000;r.ip=0x5696;break;
        case 0x5696:r.es=r.ax;r.ip=0x5698;break;
        case 0x5698:r.ax=165;r.ip=0x569b;break;
        case 0x569b:r.bx=320;r.ip=0x569e;break;
        case 0x569e: {
            const uint32_t product=uint32_t{r.ax}*r.bx;r.ax=static_cast<uint16_t>(product);
            r.dx=static_cast<uint16_t>(product>>16);r.flags=(r.flags&~uint32_t{0x801})|(r.dx ? 0x801u : 0u);r.ip=0x56a0;break;
        }
        case 0x56a0:r.di=r.ax;r.ip=0x56a2;break;
        case 0x56a2:r.di=arithmetic(r.di,word(0x2072));r.ip=0x56a6;break;
        case 0x56a6:al(14);r.ip=0x56a8;break;
        case 0x56a8:case 0x56b3: {
            const auto count=copies(r.cx);
            if (count>r.cx || (r.cx && !count)) throw std::domain_error("Health bar REP grant differs");
            for (unsigned n=0;n<count;++n) {
                bus.writeByte(r.es,r.di,static_cast<uint8_t>(r.ax));r.di=static_cast<uint16_t>(r.di+(flag(0x400) ? -1 : 1));
            }
            r.cx=static_cast<uint16_t>(r.cx-count);state_.stringTransfers+=count;
            if (!r.cx) r.ip=static_cast<uint16_t>(r.ip+2u);
            break;
        }
        case 0x56aa:r.cx=100;r.ip=0x56ad;break;
        case 0x56ad:r.cx=arithmetic(r.cx,word(0x2074),true);r.ip=0x56b1;break;
        case 0x56b1:al(1);r.ip=0x56b3;break;
        case 0x56b5:r.ip=pop();break;
        case 0x30a3:push(r.bp);r.ip=0x30a4;break;
        case 0x30a4:r.bp=r.sp;r.ip=0x30a6;break;
        case 0x30a6:r.ax=4;r.ip=0x30a9;break;
        case 0x30a9:farCall(0x4df,0x30ae);break;
        case 0x30ae:r.sp=arithmetic(r.sp,4,true);r.ip=0x30b1;break;
        case 0x30b1:wd(0x2074,86);r.ip=0x30b7;break;
        case 0x30b7:bd(0x799f,5);r.ip=0x30bc;break;
        case 0x30bc:call(0x165a,0x30bf);break;
        case 0x30bf:r.si=logic(0);r.ip=0x30c1;break;
        case 0x30c1:r.bx=static_cast<uint16_t>((r.bx&0xff00u)|data(0x79b4));r.ip=0x30c5;break;
        case 0x30c5:r.cx=word(0x78ba);r.ip=0x30c9;break;
        case 0x30c9:r.dx=logic(0);r.ip=0x30cb;break;
        case 0x30cb:push(r.ds);r.ip=0x30cc;break;
        case 0x30cc:r.ds=word(0xc1fe);r.ip=0x30d0;break;
        case 0x30d0:al(bus.readByte(r.ds,r.si));r.si=static_cast<uint16_t>(r.si+(flag(0x400) ? -1 : 1));r.ip=0x30d1;break;
        case 0x30d1:arithmetic(r.ax&255u,r.bx&255u,true,true);r.ip=0x30d3;break;
        case 0x30d3:branch(!flag(0x40),0x30d6,0x30d5);break;
        case 0x30d5:r.dx=increment(r.dx);r.ip=0x30d6;break;
        case 0x30d6:r.cx=static_cast<uint16_t>(r.cx-1u);r.ip=r.cx ? 0x30d0 : 0x30d8;break;
        case 0x30d8:r.ds=pop();r.ip=0x30d9;break;
        case 0x30d9:wd(0x2074,r.dx);r.ip=0x30dd;break;
        case 0x30dd:r.ax=word(0x2088);r.ip=0x30e0;break;
        case 0x30e0:r.ax=arithmetic(r.ax,word(0x2074));r.ip=0x30e4;break;
        case 0x30e4:arithmetic(r.ax,word(0x2086),true);r.ip=0x30e8;break;
        case 0x30e8:branch(flag(1),0x30f1,0x30ea);break;
        case 0x30ea:bd(0x79ca,1);r.ip=0x30ef;break;
        case 0x30ef:r.ip=0x30f6;break;
        case 0x30f1:bd(0x79ca,0);r.ip=0x30f6;break;
        case 0x30f6:al(lb(4));r.ip=0x30f9;break;
        case 0x30f9:zeroAh();r.ip=0x30fb;break;
        case 0x30fb:multiplyActor(r.ax);r.ip=0x30fe;break;
        case 0x30fe:r.di=arithmetic(r.di,0x1b62);r.ip=0x3102;break;
        case 0x3102:store(-4,r.di);r.ip=0x3105;break;
        case 0x3105:store(-2,r.ds);r.ip=0x3108;break;
        case 0x3108:localLes(-4);r.ip=0x310b;break;
        case 0x310b:r.di=arithmetic(r.di,22);r.ip=0x310f;break;
        case 0x310f:push(r.es);r.ip=0x3110;break;
        case 0x3110:push(r.di);r.ip=0x3111;break;
        case 0x3111:al(data(0x6c));r.ip=0x3114;break;
        case 0x3114:push(r.ax);r.ip=0x3115;break;
        case 0x3115:al(data(0x6d));r.ip=0x3118;break;
        case 0x3118:push(r.ax);r.ip=0x3119;break;
        case 0x3119:push(3);r.ip=0x311b;break;
        case 0x311b:push(1);r.ip=0x311d;break;
        case 0x311d:call(0x6ab,0x3120);break;
        case 0x3120:localLes(-4);r.ip=0x3123;break;
        case 0x3123:bus.writeByte(r.es,static_cast<uint16_t>(r.di+21u),2);r.ip=0x3128;break;
        case 0x3128:localLes(-4);r.ip=0x312b;break;
        case 0x312b:bus.writeWord(r.es,static_cast<uint16_t>(r.di+16u),60);r.ip=0x3131;break;
        case 0x3131:localLes(-4);r.ip=0x3134;break;
        case 0x3134:bus.writeByte(r.es,static_cast<uint16_t>(r.di+36u),100);r.ip=0x3139;break;
        case 0x3139:r.sp=r.bp;r.bp=pop();r.ip=0x313a;break;
        case 0x313a:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;
        case 0x11b0:push(r.bp);r.ip=0x11b1;break;
        case 0x11b1:r.bp=r.sp;r.ip=0x11b3;break;
        case 0x11b3:r.ax=8;r.ip=0x11b6;break;
        case 0x11b6:farCall(0x4df,0x11bb);break;
        case 0x11bb:r.sp=arithmetic(r.sp,8,true);r.ip=0x11be;break;
        case 0x11be:localLes(4);r.ip=0x11c1;break;
        case 0x11c1:r.ax=bus.readWord(r.es,r.di);r.ip=0x11c4;break;
        case 0x11c4:r.dx=bus.readWord(r.es,static_cast<uint16_t>(r.di+2u));r.ip=0x11c8;break;
        case 0x11c8:store(-4,r.ax);r.ip=0x11cb;break;
        case 0x11cb:store(-2,r.dx);r.ip=0x11ce;break;
        case 0x11ce:r.ax=logic(0);r.ip=0x11d0;break;
        case 0x11d0:store(-6,r.ax);r.ip=0x11d3;break;
        case 0x11d3:r.ax=local(-4);r.ip=0x11d6;break;
        case 0x11d6:r.dx=local(-2);r.ip=0x11d9;break;
        case 0x11d9:r.cx=10;r.ip=0x11dc;break;
        case 0x11dc:r.bx=logic(0);r.ip=0x11de;break;
        case 0x11de:farCall(0x945,0x11e3);break;
        case 0x11e3:r.ax=r.cx;r.ip=0x11e5;break;
        case 0x11e5:r.dx=r.bx;r.ip=0x11e7;break;
        case 0x11e7:bus.writeByte(r.ss,static_cast<uint16_t>(r.bp-7u),static_cast<uint8_t>(r.ax));r.ip=0x11ea;break;
        case 0x11ea:al(lb(-7));r.ip=0x11ed;break;
        case 0x11ed:zeroAh();r.ip=0x11ef;break;
        case 0x11ef:r.ax=shift(r.ax,6);r.ip=0x11f2;break;
        case 0x11f2:r.ax=arithmetic(r.ax,word(0x2070));r.ip=0x11f6;break;
        case 0x11f6:r.dx=r.ax;r.ip=0x11f8;break;
        case 0x11f8:r.ax=local(-6);r.ip=0x11fb;break;
        case 0x11fb:r.ax=shift(r.ax,1);r.ip=0x11fd;break;
        case 0x11fd:localLes(4);r.ip=0x1200;break;
        case 0x1200:r.di=arithmetic(r.di,r.ax);r.ip=0x1202;break;
        case 0x1202:bus.writeWord(r.es,static_cast<uint16_t>(r.di+24u),r.dx);r.ip=0x1206;break;
        case 0x1206:r.ax=local(-4);r.ip=0x1209;break;
        case 0x1209:r.dx=local(-2);r.ip=0x120c;break;
        case 0x120c:r.cx=10;r.ip=0x120f;break;
        case 0x120f:r.bx=logic(0);r.ip=0x1211;break;
        case 0x1211:farCall(0x945,0x1216);break;
        case 0x1216:store(-4,r.ax);r.ip=0x1219;break;
        case 0x1219:store(-2,r.dx);r.ip=0x121c;break;
        case 0x121c:store(-6,increment(local(-6)));r.ip=0x121f;break;
        case 0x121f:r.ax=local(-4);r.ip=0x1222;break;
        case 0x1222:r.ax=logic(r.ax|local(-2));r.ip=0x1225;break;
        case 0x1225:branch(flag(0x40),0x122d,0x1227);break;
        case 0x1227:arithmetic(local(-6),8,true);r.ip=0x122b;break;
        case 0x122b:branch(!flag(0x40),0x11d3,0x122d);break;
        case 0x122d:localLes(4);r.ip=0x1230;break;
        case 0x1230:bus.writeByte(r.es,static_cast<uint16_t>(r.di+44u),1);r.ip=0x1235;break;
        case 0x1235:r.sp=r.bp;r.bp=pop();r.ip=0x1236;break;
        case 0x1236:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);break;
        case 0x1239:case 0x1287:push(r.bp);r.ip=static_cast<uint16_t>(r.ip+1u);break;
        case 0x123a:case 0x1288:r.bp=r.sp;r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x123c:case 0x128a:r.ax=logic(0);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x123e:farCall(0x4df,0x1243);break;
        case 0x1243:r.ax=0xa000;r.ip=0x1246;break;
        case 0x1246:push(r.ax);r.ip=0x1247;break;
        case 0x1247:r.es=pop();r.ip=0x1248;break;
        case 0x1248:r.ax=word(0x2074);r.ip=0x124b;break;
        case 0x124b:wd(0x2072,r.ax);r.ip=0x124e;break;
        case 0x124e:r.bx=16;r.ip=0x1251;break;
        case 0x1251:r.bx=arithmetic(r.bx,local(4));r.ip=0x1254;break;
        case 0x1254:r.cx=9;r.ip=0x1257;break;
        case 0x1257:dl(static_cast<uint8_t>(logic(0,true)));r.ip=0x1259;break;
        case 0x1259:push(r.cx);r.ip=0x125a;break;
        case 0x125a:r.ax=word(static_cast<uint16_t>(r.bx+0x785eu));r.ip=0x125e;break;
        case 0x125e:arithmetic(r.dx&255u,1,true,true);r.ip=0x1261;break;
        case 0x1261:branch(flag(0x40),0x1269,0x1263);break;
        case 0x1263:arithmetic(r.ax,word(0x2070),true);r.ip=0x1267;break;
        case 0x1267:branch(flag(0x40),0x1271,0x1269);break;
        case 0x1269:wd(0x2074,r.ax);r.ip=0x126c;break;
        case 0x126c:call(0x1156,0x126f);break;
        case 0x126f:dl(1);r.ip=0x1271;break;
        case 0x1271:wd(0x2072,arithmetic(word(0x2072),9));r.ip=0x1276;break;
        case 0x1276:r.bx=arithmetic(r.bx,2,true);r.ip=0x1279;break;
        case 0x1279:r.cx=pop();r.ip=0x127a;break;
        case 0x127a:arithmetic(r.cx,2,true);r.ip=0x127d;break;
        case 0x127d:branch(!flag(0x40),0x1281,0x127f);break;
        case 0x127f:dl(1);r.ip=0x1281;break;
        case 0x1281:r.cx=static_cast<uint16_t>(r.cx-1u);r.ip=r.cx ? 0x1259 : 0x1283;break;
        case 0x1283:r.sp=r.bp;r.bp=pop();r.ip=0x1284;break;
        case 0x1284:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;
        case 0x128c:farCall(0x4df,0x1291);break;
        case 0x1291:r.bx=16;r.ip=0x1294;break;
        case 0x1294:r.bx=arithmetic(r.bx,local(4));r.ip=0x1297;break;
        case 0x1297:dl(static_cast<uint8_t>(logic(0,true)));r.ip=0x1299;break;
        case 0x1299:r.cx=9;r.ip=0x129c;break;
        case 0x129c:r.ax=word(static_cast<uint16_t>(r.bx+0x785eu));r.ip=0x12a0;break;
        case 0x12a0:arithmetic(r.ax,word(static_cast<uint16_t>(r.bx+0x7872u)),true);r.ip=0x12a4;break;
        case 0x12a4:branch(flag(0x40),0x12c4,0x12a6);break;
        case 0x12a6:r.ax=arithmetic(r.ax,8);r.ip=0x12a9;break;
        case 0x12a9:logic(r.cx&1u);r.ip=0x12ad;break;
        case 0x12ad:branch(flag(0x40),0x12b2,0x12af);break;
        case 0x12af:r.ax=arithmetic(r.ax,8);r.ip=0x12b2;break;
        case 0x12b2:dl(static_cast<uint8_t>(increment(r.dx&255u,false,true)));r.ip=0x12b4;break;
        case 0x12b4:r.ax=arithmetic(r.ax,640,true);r.ip=0x12b7;break;
        case 0x12b7:arithmetic(r.ax,word(0x2070),true);r.ip=0x12bb;break;
        case 0x12bb:branch(!flag(1),0x12c0,0x12bd);break;
        case 0x12bd:r.ax=arithmetic(r.ax,640);r.ip=0x12c0;break;
        case 0x12c0:wd(static_cast<uint16_t>(r.bx+0x785eu),r.ax);r.ip=0x12c4;break;
        case 0x12c4:r.bx=arithmetic(r.bx,2,true);r.ip=0x12c7;break;
        case 0x12c7:r.cx=static_cast<uint16_t>(r.cx-1u);r.ip=r.cx ? 0x129c : 0x12c9;break;
        case 0x12c9:arithmetic(r.dx&255u,0,true,true);r.ip=0x12cc;break;
        case 0x12cc:branch(!flag(0x40),0x12d7,0x12ce);break;
        case 0x12ce:al(2);r.ip=0x12d0;break;
        case 0x12d0:r.bx=local(4);r.ip=0x12d3;break;
        case 0x12d3:bd(static_cast<uint16_t>(r.bx+0x7886u),static_cast<uint8_t>(r.ax));r.ip=0x12d7;break;
        case 0x12d7:r.sp=r.bp;r.bp=pop();r.ip=0x12d8;break;
        case 0x12d8:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;
        default:throw std::domain_error("Player post reached an unrecovered instruction");
        }
    }
    void divisionInstruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto branch=[&](bool yes,uint16_t target,uint16_t next) { r.ip=yes ? target : next; };
        switch (r.ip) {
        case 0x945:push(r.bp);r.ip=0x946;break;
        case 0x946:r.bp=r.cx;r.ip=0x948;break;
        case 0x948:r.bp=logic(r.bp|r.bx);r.ip=0x94a;break;
        case 0x94a:branch(flag(0x40),0x9ac,0x94c);break;
        case 0x94c:r.bx=logic(r.bx);r.ip=0x94e;break;
        case 0x94e:push(static_cast<uint16_t>(r.flags));r.ip=0x94f;break;
        case 0x94f:branch(!flag(0x80),0x95b,0x951);break;
        case 0x951:r.cx=static_cast<uint16_t>(~r.cx);r.ip=0x953;break;
        case 0x953:r.bx=static_cast<uint16_t>(~r.bx);r.ip=0x955;break;
        case 0x955:r.cx=arithmetic(r.cx,1);r.ip=0x958;break;
        case 0x958:r.bx=arithmetic(r.bx,0,false,false,true);r.ip=0x95b;break;
        case 0x95b:r.dx=logic(r.dx);r.ip=0x95d;break;
        case 0x95d:push(static_cast<uint16_t>(r.flags));r.ip=0x95e;break;
        case 0x95e:branch(!flag(0x80),0x96a,0x960);break;
        case 0x960:r.ax=static_cast<uint16_t>(~r.ax);r.ip=0x962;break;
        case 0x962:r.dx=static_cast<uint16_t>(~r.dx);r.ip=0x964;break;
        case 0x964:r.ax=arithmetic(r.ax,1);r.ip=0x967;break;
        case 0x967:r.dx=arithmetic(r.dx,0,false,false,true);r.ip=0x96a;break;
        case 0x96a:r.si=r.cx;r.ip=0x96c;break;
        case 0x96c:r.di=r.bx;r.ip=0x96e;break;
        case 0x96e:r.cx=logic(0);r.ip=0x970;break;
        case 0x970:r.bx=logic(0);r.ip=0x972;break;
        case 0x972:r.bp=33;r.ip=0x975;break;
        case 0x975:r.cx=rotateCarry(r.cx);r.ip=0x977;break;
        case 0x977:r.bx=rotateCarry(r.bx);r.ip=0x979;break;
        case 0x979:r.cx=arithmetic(r.cx,r.si,true);r.ip=0x97b;break;
        case 0x97b:r.bx=arithmetic(r.bx,r.di,true,false,true);r.ip=0x97d;break;
        case 0x97d:branch(!flag(1),0x983,0x97f);break;
        case 0x97f:r.cx=arithmetic(r.cx,r.si);r.ip=0x981;break;
        case 0x981:r.bx=arithmetic(r.bx,r.di,false,false,true);r.ip=0x983;break;
        case 0x983:r.flags^=1u;r.ip=0x984;break;
        case 0x984:r.ax=rotateCarry(r.ax);r.ip=0x986;break;
        case 0x986:r.dx=rotateCarry(r.dx);r.ip=0x988;break;
        case 0x988:r.bp=increment(r.bp,true);r.ip=0x989;break;
        case 0x989:branch(!flag(0x40),0x975,0x98b);break;
        case 0x98b:r.flags=(r.flags&0xffff0000u)|pop();r.ip=0x98c;break;
        case 0x98c:branch(!flag(0x80),0x99d,0x98e);break;
        case 0x98e:r.cx=static_cast<uint16_t>(~r.cx);r.ip=0x990;break;
        case 0x990:r.bx=static_cast<uint16_t>(~r.bx);r.ip=0x992;break;
        case 0x992:r.cx=arithmetic(r.cx,1);r.ip=0x995;break;
        case 0x995:r.bx=arithmetic(r.bx,0,false,false,true);r.ip=0x998;break;
        case 0x998:r.flags=(r.flags&0xffff0000u)|pop();r.ip=0x999;break;
        case 0x999:branch(!flag(0x80),0x9a0,0x99b);break;
        case 0x99b:r.ip=0x9aa;break;
        case 0x99d:r.flags=(r.flags&0xffff0000u)|pop();r.ip=0x99e;break;
        case 0x99e:branch(!flag(0x80),0x9aa,0x9a0);break;
        case 0x9a0:r.ax=static_cast<uint16_t>(~r.ax);r.ip=0x9a2;break;
        case 0x9a2:r.dx=static_cast<uint16_t>(~r.dx);r.ip=0x9a4;break;
        case 0x9a4:r.ax=arithmetic(r.ax,1);r.ip=0x9a7;break;
        case 0x9a7:r.dx=arithmetic(r.dx,0,false,false,true);r.ip=0x9aa;break;
        case 0x9aa:r.bp=pop();r.ip=0x9ab;break;
        case 0x9ab:r.ip=pop();r.cs=pop();break;
        case 0x9ac:r.bp=pop();r.ip=0x9ad;break;
        case 0x9ad:r.ax=200;r.ip=0x9b0;break;
        case 0x9b0:r.ip=0xe2;break;
        default:throw std::domain_error("Score divide left recovered RTL code");
        }
    }
};

} // namespace lezac::core
