#pragma once

#include "core/frame_spawner.hpp"
#include "core/actor_terrain.hpp"
#include <optional>

namespace lezac::core {

enum class FrameTailOutcome { Running, NextFrame, Completion, Escape, ViewChange, RuntimeError, DivideError };
struct FrameTailReturn {
    uint16_t cs=0,ip=0,sp=0,bp=0;
    bool operator==(const FrameTailReturn&) const = default;
};
struct FrameTailSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0,callerSs=0,callerSp=0,callerBp=0;
    uint32_t idToggleMask=0;
    FrameTailOutcome outcome=FrameTailOutcome::Running;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    std::optional<FrameTailReturn> rngReturn=std::nullopt,stackReturn=std::nullopt;
    uint64_t tileCalls=0,tileReturns=0;
    bool tileCallback=false,tileWriter=false;
    bool operator==(const FrameTailSnapshot&) const = default;
};

// Original post-queue caller and countdown tile callback; UI handoffs stay unexecuted.
class FrameTailOperation {
public:
    FrameTailOperation(DosGetTimeRegisters r,uint16_t game,uint32_t id)
        : state_{r,game,r.ss,r.sp,r.bp,id} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x806a)
            throw std::invalid_argument("Frame tail entry differs");
        validate();
    }
    explicit FrameTailOperation(FrameTailSnapshot state) : state_(std::move(state)) { validate(); }
    const FrameTailSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome!=FrameTailOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.timer.has_value(); }
    DosGetTimeRegisters registers() const { return state_.timer ? fromTimer(state_.timer->registers) : state_.registers; }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || state_.timer || !(state_.registers.flags&0x200u))
            throw std::logic_error("Frame tail IRQ is not eligible");
        auto r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);
        r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
        state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            const auto before=state_.registers;
            const bool foreground=!state_.timer;
            if (state_.timer) {
                TimerIrqOperation irq(*state_.timer);
                if (irq.advance(1,bus)!=1) throw std::domain_error("Frame tail IRQ stalled");
                ++state_.timerInstructions;
                if (irq.returned()) { state_.registers=fromTimer(irq.snapshot().registers);state_.timer.reset(); }
                else state_.timer=irq.snapshot();
            } else instruction(bus);
            ++used;++state_.dispatchedInstructions;
            if (foreground) classify(before);
            if (finished()) validate();
        }
        return used;
    }
private:
    FrameTailSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    uint16_t graphics() const { return static_cast<uint16_t>(state_.gameSegment+0x8ac); }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static FrameTailOutcome endpoint(uint16_t ip) {
        switch (ip) {
        case 0x7903:return FrameTailOutcome::NextFrame;
        case 0x8298:return FrameTailOutcome::Completion;
        case 0x82b9:return FrameTailOutcome::Escape;
        case 0x8224:case 0x825e:return FrameTailOutcome::ViewChange;
        default:return FrameTailOutcome::Running;
        }
    }
    void classify(const DosGetTimeRegisters& before) {
        const auto& r=state_.registers;
        if (before.cs==state_.gameSegment &&
            (before.ip==0x8077 || before.ip==0x3f39 || before.ip==0x3f56)) {
            if (state_.rngReturn || r.cs!=library() || r.ip!=0x13a8)
                throw std::invalid_argument("Frame tail RNG call differs");
            state_.rngReturn=FrameTailReturn{before.cs,
                static_cast<uint16_t>(before.ip+5u),static_cast<uint16_t>(before.sp+2u),before.bp};
        }
        if ((before.cs==graphics() && before.ip==5) ||
            (before.cs==state_.gameSegment && (before.ip==0x3f2d || before.ip==0x3714))) {
            if (state_.stackReturn || r.cs!=library() || r.ip!=0x4df)
                throw std::invalid_argument("Frame tail stack-check call differs");
            state_.stackReturn=FrameTailReturn{before.cs,static_cast<uint16_t>(before.ip+5u),before.sp,before.bp};
        }
        if (before.cs==library() && before.ip==0x13bb) {
            if (!state_.rngReturn || FrameTailReturn{r.cs,r.ip,r.sp,r.bp}!=*state_.rngReturn)
                throw std::invalid_argument("Frame tail RNG return differs");
            state_.rngReturn.reset();
        }
        if (before.cs==library() && before.ip==0x142c &&
            (!state_.rngReturn || r.cs!=library() || r.ip!=0x13ab ||
                r.sp!=static_cast<uint16_t>(state_.rngReturn->sp-6u) || r.bp!=state_.rngReturn->bp))
            throw std::invalid_argument("Frame tail RNG nested return differs");
        if (before.cs==library() && before.ip==0x4f0) {
            if (!state_.stackReturn || FrameTailReturn{r.cs,r.ip,r.sp,r.bp}!=*state_.stackReturn)
                throw std::invalid_argument("Frame tail stack helper return differs");
            state_.stackReturn.reset();
        }
        if (before.cs==graphics() && before.ip==0x1f &&
            (r.cs!=state_.gameSegment || r.ip!=0x81b4 || r.sp!=state_.callerSp || r.bp!=state_.callerBp))
            throw std::invalid_argument("Frame tail DAC return differs");
        if (before.cs==state_.gameSegment && before.ip==0x7c4 &&
            (r.cs!=state_.gameSegment || r.ip!=0x81df || r.sp!=state_.callerSp || r.bp!=state_.callerBp))
            throw std::invalid_argument("Frame tail palette return differs");
        if (before.cs==state_.gameSegment && before.ip==0x81ca) {
            if (state_.tileCallback || r.cs!=state_.gameSegment || r.ip!=0x3f27)
                throw std::invalid_argument("Frame tail tile callback call differs");
            state_.tileCallback=true;++state_.tileCalls;
        }
        if (before.cs==state_.gameSegment && before.ip==0x3fa1) {
            if (!state_.tileCallback || state_.tileWriter || r.cs!=state_.gameSegment || r.ip!=0x370e)
                throw std::invalid_argument("Frame tail tile writer call differs");
            state_.tileWriter=true;
        }
        if (before.cs==state_.gameSegment && before.ip==0x3a53) {
            if (!state_.tileCallback || !state_.tileWriter || r.cs!=state_.gameSegment || r.ip!=0x3fa4 ||
                r.sp!=static_cast<uint16_t>(state_.callerSp-6u) || r.bp!=static_cast<uint16_t>(state_.callerSp-4u))
                throw std::invalid_argument("Frame tail tile writer return differs");
            state_.tileWriter=false;
        }
        if (before.cs==state_.gameSegment && before.ip==0x3fa5) {
            if (!state_.tileCallback || state_.tileWriter || r.cs!=state_.gameSegment || r.ip!=0x81cd ||
                r.sp!=state_.callerSp || r.bp!=state_.callerBp)
                throw std::invalid_argument("Frame tail tile callback return differs");
            state_.tileCallback=false;++state_.tileReturns;
        }
        if (r.cs==state_.gameSegment) {
            const auto result=endpoint(r.ip);
            if (result!=FrameTailOutcome::Running) {
                const bool source=before.cs==state_.gameSegment &&
                    ((r.ip==0x7903 && before.ip==0x82b6) ||
                     (r.ip==0x8298 && before.ip==0x8296) ||
                     (r.ip==0x82b9 && before.ip==0x82b4) ||
                     (r.ip==0x8224 && before.ip==0x8222) ||
                     (r.ip==0x825e && before.ip==0x825c));
                if (!source) throw std::invalid_argument("Frame tail endpoint source differs");
                state_.outcome=result;
            }
        } else if (r.cs==library() && r.ip==0xe2) state_.outcome=FrameTailOutcome::RuntimeError;
    }
    void validate() const {
        const auto& r=state_.registers;
        const bool main=r.cs==state_.gameSegment;
        const bool runtime=r.cs==library();
        const bool video=r.cs==graphics();
        const bool running=state_.outcome==FrameTailOutcome::Running;
        const bool divide=state_.outcome==FrameTailOutcome::DivideError;
        const bool randomCode=runtime && ((r.ip>=0x13a8 && r.ip<0x13bc) || (r.ip>=0x13f7 && r.ip<=0x142c));
        const bool stackCode=runtime && ((r.ip>=0x4df && r.ip<=0x4f4) ||
            (r.ip==0xe2 && state_.outcome==FrameTailOutcome::RuntimeError));
        const bool ownedMain=state_.tileCallback ?
            (state_.tileWriter ? r.ip>=0x370e && r.ip<=0x3a53 : r.ip>=0x3f27 && r.ip<=0x3fa5) :
            ((r.ip>=0x806a && r.ip<=0x82b6) || (r.ip>=0x79d && r.ip<=0x7c4));
        uint16_t expectedSp=state_.callerSp,expectedBp=state_.callerBp;
        const auto below=[&](unsigned bytes) { return static_cast<uint16_t>(state_.callerSp-bytes); };
        if (main && state_.tileWriter) {
            expectedSp=r.ip<=0x3719 ? below(20) : below(50);
            expectedBp=below(20);
            if (r.ip==0x370e) { expectedSp=below(18);expectedBp=below(4); }
            if (r.ip==0x370f) expectedBp=below(4);
            if (r.ip==0x3a53) { expectedSp=below(18);expectedBp=below(4); }
        } else if (main && state_.tileCallback) {
            expectedSp=below(6);expectedBp=below(4);
            if (r.ip==0x3f27) { expectedSp=below(2);expectedBp=state_.callerBp; }
            if (r.ip==0x3f28) { expectedSp=below(4);expectedBp=state_.callerBp; }
            if (r.ip>=0x3f2a && r.ip<=0x3f32) expectedSp=below(4);
            if (r.ip==0x3f39 || r.ip==0x3f56 || r.ip==0x3f98) expectedSp=below(8);
            if (r.ip==0x3f9a) expectedSp=below(10);
            if (r.ip==0x3f9c || r.ip==0x3f9f) expectedSp=below(12);
            if (r.ip==0x3fa0) expectedSp=below(14);
            if (r.ip==0x3fa1) expectedSp=below(16);
            if (r.ip==0x3fa5) { expectedSp=below(2);expectedBp=state_.callerBp; }
        } else if (main) {
            if (r.ip==0x8077 || (r.ip>=0x79d && r.ip<=0x7c4) ||
                (r.ip>=0x8182 && r.ip<=0x8190)) expectedSp=below(2);
            if (r.ip>=0x8191 && r.ip<=0x819f) expectedSp=below(4);
            if (r.ip>=0x81a0 && r.ip<=0x81ae) expectedSp=below(6);
            if (r.ip==0x81af) expectedSp=below(8);
        } else if (video) {
            expectedSp=r.ip==0 ? below(12) : below(14);
            expectedBp=r.ip<=1 ? state_.callerBp : below(14);
            if (r.ip==31) { expectedSp=below(12);expectedBp=state_.callerBp; }
        }
        if (r.ss!=state_.callerSs || registers().ss!=state_.callerSs ||
            (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            state_.timerInstructions>state_.dispatchedInstructions ||
            (state_.timerDeliveries>state_.timerInstructions &&
                state_.timerDeliveries-state_.timerInstructions>(state_.timer ? 1u : 0u)) ||
            state_.tileCalls>1 || state_.tileCalls>state_.dispatchedInstructions || state_.tileReturns>state_.tileCalls ||
            state_.tileCalls-state_.tileReturns!=(state_.tileCallback ? 1u : 0u) ||
            (state_.tileWriter && !state_.tileCallback) ||
            (!main && !runtime && !video) || r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
            ((main || video) && (r.sp!=expectedSp || r.bp!=expectedBp)) ||
            (running && ((main && !ownedMain) ||
                (main && endpoint(r.ip)!=FrameTailOutcome::Running) ||
                (runtime && !randomCode && !stackCode) || (video && (r.ip>0x1f || state_.tileCallback)))) ||
            (randomCode!=state_.rngReturn.has_value()) || (stackCode!=state_.stackReturn.has_value()) ||
            (state_.timer && (!running || state_.timer->returned || !state_.timer->biosWrapper ||
                !state_.timerDeliveries || state_.timer->dispatchedInstructions>state_.timerInstructions ||
                state_.timer->gameSegment!=state_.gameSegment ||
                state_.timer->dataSegment!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
                state_.timer->crtSegment!=static_cast<uint16_t>(state_.gameSegment+0x84a) ||
                state_.timer->biosSegment!=0xf000 || state_.timer->biosEntry!=0xfea5 ||
                (state_.timer->registers.cs!=state_.gameSegment &&
                    state_.timer->registers.cs!=static_cast<uint16_t>(state_.gameSegment+0x84a) &&
                    state_.timer->registers.cs!=0xf000) ||
                state_.timer->idToggleMask!=state_.idToggleMask)) ||
            (finished() && state_.tileCallback && state_.outcome!=FrameTailOutcome::RuntimeError) ||
            (!running && !divide && state_.outcome!=FrameTailOutcome::RuntimeError &&
                (!main || endpoint(r.ip)!=state_.outcome || r.sp!=state_.callerSp || r.bp!=state_.callerBp)) ||
            (state_.outcome==FrameTailOutcome::RuntimeError && (!runtime || r.ip!=0xe2)) ||
            (divide && (!main || r.ip!=0x81d5 ||
                (r.cx && ((uint32_t{r.dx}<<16)|r.ax)/r.cx<=65535))) ||
            (finished() && (!state_.dispatchedInstructions || state_.timer)) ||
            (!state_.dispatchedInstructions && (!running || !main || r.ip!=0x806a ||
                r.sp!=state_.callerSp || r.bp!=state_.callerBp)))
            throw std::invalid_argument("Frame tail continuation ownership differs");
        if (state_.rngReturn) {
            const auto& target=*state_.rngReturn;
            if (!state_.dispatchedInstructions || state_.tileWriter || target.cs!=state_.gameSegment ||
                (state_.tileCallback ? (target.ip!=0x3f3e && target.ip!=0x3f5b) : target.ip!=0x807c) ||
                target.sp!=(state_.tileCallback ? below(6) : state_.callerSp) ||
                target.bp!=(state_.tileCallback ? below(4) : state_.callerBp) ||
                r.bp!=target.bp || r.sp!=static_cast<uint16_t>(target.sp-(r.ip>=0x13f7 ? 8u : 6u)))
                throw std::invalid_argument("Frame tail RNG continuation differs");
        }
        if (state_.stackReturn) {
            const auto& target=*state_.stackReturn;
            const bool allowed=state_.tileCallback ?
                target.cs==state_.gameSegment && target.ip==(state_.tileWriter ? 0x3719 : 0x3f32) :
                target.cs==graphics() && target.ip==10;
            if (!state_.dispatchedInstructions || !allowed || r.bp!=target.bp ||
                target.sp!=(state_.tileCallback ? (state_.tileWriter ? below(20) : below(4)) : below(14)) ||
                target.bp!=target.sp ||
                r.sp!=static_cast<uint16_t>(target.sp-4u))
                throw std::invalid_argument("Frame tail stack-check continuation differs");
        }
        if (state_.timer) (void)TimerIrqOperation(*state_.timer);
    }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    static uint32_t values(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value,bool byte=false) {
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|values(value,byte);return value;
    }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false,bool byte=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u;
        const uint32_t wide=subtract ? uint32_t{a}-b : uint32_t{a}+b;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t f=values(value,byte)|((a^b^value)&16u);
        if (subtract ? a<b : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^value)&sign) : (~(a^b)&(a^value)&sign)) f|=0x800;
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|f;return value;
    }
    uint16_t increment(uint16_t value,bool subtract=false,bool byte=false) {
        const auto carry=state_.registers.flags&1u;value=arithmetic(value,1,subtract,byte);
        state_.registers.flags=(state_.registers.flags&~uint32_t{1})|carry;return value;
    }
    uint16_t shift(uint16_t value) {
        const auto next=static_cast<uint16_t>(value<<1);
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|values(next)|16u|
            (value>>15)|((value^next)&0x8000u ? 0x800u : 0u);return next;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        if (r.cs==library()) {
            FrameSpawnerOperation child(FrameSpawnerSnapshot{r,state_.gameSegment});
            if (child.advance(1,bus)!=1) throw std::domain_error("Frame tail helper stalled");
            r=child.snapshot().registers;return;
        }
        if (r.cs==state_.gameSegment && r.ip>=0x370e && r.ip<=0x3a53) {
            advanceActorTerrainInstruction(r,state_.gameSegment,bus);return;
        }
        const auto word=[&](uint16_t o) { return bus.readWord(r.ds,o); };
        const auto byte=[&](uint16_t o) { return bus.readByte(r.ds,o); };
        const auto wd=[&](uint16_t o,uint16_t v) { bus.writeWord(r.ds,o,v); };
        const auto bd=[&](uint16_t o,uint16_t v) { bus.writeByte(r.ds,o,static_cast<uint8_t>(v)); };
        const auto al=[&](uint16_t v) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|(v&255u)); };
        const auto dl=[&](uint16_t v) { r.dx=static_cast<uint16_t>((r.dx&0xff00u)|(v&255u)); };
        const auto bl=[&](uint16_t v) { r.bx=static_cast<uint16_t>((r.bx&0xff00u)|(v&255u)); };
        const auto push=[&](uint16_t v) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,v); };
        const auto pop=[&] { const auto v=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return v; };
        const auto branch=[&](bool yes,uint16_t target,uint16_t next) { r.ip=yes ? target : next; };
        if (r.cs==graphics()) {
            switch (r.ip) {
            case 0:push(r.bp);r.ip=1;break;
            case 1:r.bp=r.sp;r.ip=3;break;
            case 3:r.ax=logic(0);r.ip=5;break;
            case 5:push(r.cs);push(10);r.cs=library();r.ip=0x4df;break;
            case 10:r.dx=0x3c8;r.ip=13;break;
            case 13:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+12u)));r.ip=16;break;
            case 16:case 21:case 25:case 29:
                bus.outByte(r.dx,static_cast<uint8_t>(r.ax));r.ip=static_cast<uint16_t>(r.ip+1u);break;
            case 17:r.dx=increment(r.dx);r.ip=18;break;
            case 18:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+10u)));r.ip=21;break;
            case 22:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+8u)));r.ip=25;break;
            case 26:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+6u)));r.ip=29;break;
            case 30:r.bp=pop();r.ip=31;break;
            case 31:r.ip=pop();r.cs=pop();r.sp=static_cast<uint16_t>(r.sp+8u);break;
            default:throw std::domain_error("Frame tail DAC reached unowned instruction");
            }
            return;
        }
        switch (r.ip) {
        case 0x806a:arithmetic(word(0x209c),0,true);r.ip=0x806f;break;
        case 0x806f:branch(flag(0x40),0x8094,0x8071);break;
        case 0x8071:r.ax=word(0x209a);r.ip=0x8074;break;
        case 0x8074:r.ax=shift(r.ax);r.ip=0x8076;break;
        case 0x8076:push(r.ax);r.ip=0x8077;break;
        case 0x8077:push(r.cs);push(0x807c);r.cs=library();r.ip=0x13a8;break;
        case 0x807c:wd(0x2098,r.ax);r.ip=0x807f;break;
        case 0x807f:wd(0x209a,increment(word(0x209a),true));r.ip=0x8083;break;
        case 0x8083:arithmetic(word(0x209a),0,true);r.ip=0x8088;break;
        case 0x8088:branch(!flag(0x40),0x8094,0x808a);break;
        case 0x808a:case 0x808f:r.ax=logic(0);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x808c:wd(0x209c,r.ax);r.ip=0x808f;break;
        case 0x8091:wd(0x2098,r.ax);r.ip=0x8094;break;
        case 0x8094:arithmetic(byte(0x79cb),0,true,true);r.ip=0x8099;break;
        case 0x8099:branch(!flag(1)&&!flag(0x40),0x809e,0x809b);break;
        case 0x809b:case 0x80ae:r.ip=0x81bf;break;
        case 0x809e:case 0x816a:al(byte(0x79cb));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x80a1:case 0x80cd:case 0x80e2:case 0x8100:case 0x8115:case 0x812e:case 0x8146:case 0x816d:
        case 0x81e2:logic(0,true);r.ax&=255u;r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x80a3:bus.writeWord(r.ss,static_cast<uint16_t>(r.bp-2u),r.ax);r.ip=0x80a6;break;
        case 0x80a6:r.ax=1;r.ip=0x80a9;break;
        case 0x80a9:arithmetic(r.ax,bus.readWord(r.ss,static_cast<uint16_t>(r.bp-2u)),true);r.ip=0x80ac;break;
        case 0x80ac:branch(flag(1)||flag(0x40),0x80b1,0x80ae);break;
        case 0x80b1:wd(0x2082,r.ax);r.ip=0x80b4;break;
        case 0x80b4:r.ip=0x80ba;break;
        case 0x80c4:r.ip=0x80ca;break;
        case 0x80b6:wd(0x2082,increment(word(0x2082)));r.ip=0x80ba;break;
        case 0x80ba:bd(0x208c,0);r.ip=0x80bf;break;
        case 0x80bf:bd(0x79a3,1);r.ip=0x80c4;break;
        case 0x80c6:bd(0x79a3,increment(byte(0x79a3),false,true));r.ip=0x80ca;break;
        case 0x80ca:case 0x80df:case 0x80fd:case 0x8112:case 0x812b:case 0x8143:
            al(byte(0x79a3));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x80cf:case 0x80e4:case 0x8102:case 0x8117:case 0x8130:case 0x8148:case 0x8179:
        case 0x8182:case 0x8191:case 0x81a0:r.di=word(0x2082);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x80d3:case 0x80e8:case 0x8106:case 0x811b:case 0x8134:case 0x814c:
        case 0x8186:case 0x8195:case 0x81a4:r.si=r.di;r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x80d5:case 0x80ea:case 0x8108:case 0x811d:case 0x8136:case 0x814e:
        case 0x8188:case 0x8197:case 0x81a6:r.di=shift(r.di);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x80d7:case 0x80ec:case 0x810a:case 0x811f:case 0x8138:case 0x8150:
        case 0x818a:case 0x8199:case 0x81a8:r.di=arithmetic(r.di,r.si);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x80d9:case 0x80ee:case 0x810c:case 0x8121:case 0x813a:case 0x8152:
            r.di=arithmetic(r.di,r.ax);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x80db:case 0x810e:dl(byte(static_cast<uint16_t>(r.di+0x79d8u)));r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x80f0:case 0x8123:al(byte(static_cast<uint16_t>(r.di+0x79ceu)));r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x80f4:case 0x8127:arithmetic(r.ax&255u,r.dx&255u,true,true);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x80f6:branch(flag(0x40),0x8159,0x80f8);break;
        case 0x80f8:bd(0x208c,1);r.ip=0x80fd;break;
        case 0x8129:branch(flag(1)||flag(0x40),0x8143,0x812b);break;
        case 0x813c:bd(static_cast<uint16_t>(r.di+0x79ceu),arithmetic(byte(static_cast<uint16_t>(r.di+0x79ceu)),2,true,true));r.ip=0x8141;break;
        case 0x8141:r.ip=0x8159;break;
        case 0x8154:bd(static_cast<uint16_t>(r.di+0x79ceu),arithmetic(byte(static_cast<uint16_t>(r.di+0x79ceu)),2,false,true));r.ip=0x8159;break;
        case 0x8159:arithmetic(byte(0x79a3),3,true,true);r.ip=0x815e;break;
        case 0x815e:branch(flag(0x40),0x8163,0x8160);break;
        case 0x8160:r.ip=0x80c6;break;
        case 0x8163:arithmetic(byte(0x208c),0,true,true);r.ip=0x8168;break;
        case 0x8168:branch(!flag(0x40),0x8179,0x816a);break;
        case 0x816f:arithmetic(r.ax,word(0x2082),true);r.ip=0x8173;break;
        case 0x8173:branch(!flag(0x40),0x8179,0x8175);break;
        case 0x8175:bd(0x79cb,increment(byte(0x79cb),true,true));r.ip=0x8179;break;
        case 0x817d:al(byte(static_cast<uint16_t>(r.di+0x79cdu)));r.ip=0x8181;break;
        case 0x818c:al(byte(static_cast<uint16_t>(r.di+0x79cfu)));r.ip=0x8190;break;
        case 0x819b:al(byte(static_cast<uint16_t>(r.di+0x79d0u)));r.ip=0x819f;break;
        case 0x81aa:al(byte(static_cast<uint16_t>(r.di+0x79d1u)));r.ip=0x81ae;break;
        case 0x8181:case 0x8190:case 0x819f:case 0x81ae:push(r.ax);r.ip=static_cast<uint16_t>(r.ip+1u);break;
        case 0x81af:push(r.cs);push(0x81b4);r.cs=graphics();r.ip=0;break;
        case 0x81b4:r.ax=word(0x2082);r.ip=0x81b7;break;
        case 0x81b7:arithmetic(r.ax,bus.readWord(r.ss,static_cast<uint16_t>(r.bp-2u)),true);r.ip=0x81ba;break;
        case 0x81ba:branch(flag(0x40),0x81bf,0x81bc);break;
        case 0x81bc:r.ip=0x80b6;break;
        case 0x81bf:arithmetic(byte(0x79b2),0,true,true);r.ip=0x81c4;break;
        case 0x81c4:branch(flag(1)||flag(0x40),0x81cd,0x81c6);break;
        case 0x81c6:bd(0x79b2,increment(byte(0x79b2),true,true));r.ip=0x81ca;break;
        case 0x81ca:push(0x81cd);r.ip=0x3f27;break;
        case 0x81cd:r.ax=word(0x78c2);r.ip=0x81d0;break;
        case 0x81d0:r.dx=logic(0);r.ip=0x81d2;break;
        case 0x81d2:r.cx=5;r.ip=0x81d5;break;
        case 0x81d5: {
            const uint32_t dividend=(uint32_t{r.dx}<<16)|r.ax;
            if (!r.cx || dividend/r.cx>65535) { state_.outcome=FrameTailOutcome::DivideError;break; }
            r.ax=static_cast<uint16_t>(dividend/r.cx);r.dx=static_cast<uint16_t>(dividend%r.cx);r.ip=0x81d7;break;
        }
        case 0x81d7:std::swap(r.ax,r.dx);r.ip=0x81d8;break;
        case 0x81d8:logic(r.ax);r.ip=0x81da;break;
        case 0x81da:branch(!flag(0x40),0x81f6,0x81dc);break;
        case 0x81dc:push(0x81df);r.ip=0x79d;break;
        case 0x81df:al(byte(0x79ad));r.ip=0x81e2;break;
        case 0x81e4:r.ax=arithmetic(r.ax,7);r.ip=0x81e7;break;
        case 0x81e7:bd(0x79ad,r.ax);r.ip=0x81ea;break;
        case 0x81ea:arithmetic(byte(0x79ad),63,true,true);r.ip=0x81ef;break;
        case 0x81ef:branch(flag(1)||flag(0x40),0x81f6,0x81f1);break;
        case 0x81f1:bd(0x79ad,20);r.ip=0x81f6;break;
        case 0x81f6:arithmetic(byte(0x2058),0x73,true,true);r.ip=0x81fb;break;
        case 0x81fb:branch(!flag(0x40),0x820f,0x81fd);break;
        case 0x81fd:arithmetic(byte(0xc49c),0,true,true);r.ip=0x8202;break;
        case 0x8202:al(0);r.ip=0x8204;break;
        case 0x8204:branch(!flag(0x40),0x8207,0x8206);break;
        case 0x8206:r.ax=increment(r.ax);r.ip=0x8207;break;
        case 0x8207:bd(0xc49c,r.ax);r.ip=0x820a;break;
        case 0x820a:bd(0x2058,0x39);r.ip=0x820f;break;
        case 0x820f:arithmetic(byte(0x2058),0x65,true,true);r.ip=0x8214;break;
        case 0x8214:branch(!flag(0x40),0x8249,0x8216);break;
        case 0x8216:arithmetic(word(0xc1ea),21,true);r.ip=0x821b;break;
        case 0x821b:branch(flag(1)||flag(0x40),0x8249,0x821d);break;
        case 0x821d:arithmetic(byte(0x79b8),1,true,true);r.ip=0x8222;break;
        case 0x8222:branch(!flag(0x40),0x8249,0x8224);break;
        case 0x8249:arithmetic(byte(0x2058),0x72,true,true);r.ip=0x824e;break;
        case 0x824e:branch(!flag(0x40),0x8283,0x8250);break;
        case 0x8250:arithmetic(word(0xc1ea),40,true);r.ip=0x8255;break;
        case 0x8255:branch(!flag(1),0x8283,0x8257);break;
        case 0x8257:arithmetic(byte(0x79b8),1,true,true);r.ip=0x825c;break;
        case 0x825c:branch(!flag(0x40),0x8283,0x825e);break;
        case 0x8283:arithmetic(byte(0x79c5),0,true,true);r.ip=0x8288;break;
        case 0x8288:branch(flag(0x40),0x82af,0x828a);break;
        case 0x828a:arithmetic(byte(0x79c6),0,true,true);r.ip=0x828f;break;
        case 0x828f:branch(flag(0x40),0x82af,0x8291);break;
        case 0x8291:arithmetic(word(0x2080),0,true);r.ip=0x8296;break;
        case 0x8296:branch(!flag(0x40),0x82af,0x8298);break;
        case 0x82af:arithmetic(byte(0x2058),0x1b,true,true);r.ip=0x82b4;break;
        case 0x82b4:branch(flag(0x40),0x82b9,0x82b6);break;
        case 0x82b6:r.ip=0x7903;break;
        case 0x3f27:push(r.bp);r.ip=0x3f28;break;
        case 0x3f28:r.bp=r.sp;r.ip=0x3f2a;break;
        case 0x3f2a:r.ax=2;r.ip=0x3f2d;break;
        case 0x3f2d:push(r.cs);push(0x3f32);r.cs=library();r.ip=0x4df;break;
        case 0x3f32:r.sp=arithmetic(r.sp,2,true);r.ip=0x3f35;break;
        case 0x3f35:push(word(0xc204));r.ip=0x3f39;break;
        case 0x3f39:push(r.cs);push(0x3f3e);r.cs=library();r.ip=0x13a8;break;
        case 0x3f3e:r.ax=arithmetic(r.ax,word(0xc204));r.ip=0x3f42;break;
        case 0x3f42:bus.writeWord(r.ss,static_cast<uint16_t>(r.bp-2u),r.ax);r.ip=0x3f45;break;
        case 0x3f45:case 0x3f73:case 0x3f83:
            r.ax=bus.readWord(r.ss,static_cast<uint16_t>(r.bp-2u));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x3f48:case 0x3f76:r.di=word(0xc1e0);r.es=word(0xc1e2);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x3f4c:case 0x3f7a:case 0x3f8c:r.di=arithmetic(r.di,r.ax);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x3f4e:arithmetic(bus.readByte(r.es,r.di),0,true,true);r.ip=0x3f52;break;
        case 0x3f52:branch(!flag(0x40),0x3fa4,0x3f54);break;
        case 0x3f54:push(9);r.ip=0x3f56;break;
        case 0x3f56:push(r.cs);push(0x3f5b);r.cs=library();r.ip=0x13a8;break;
        case 0x3f5b:r.ax=arithmetic(r.ax,0x66);r.ip=0x3f5e;break;
        case 0x3f5e:r.ax=increment(r.ax);r.ip=0x3f5f;break;
        case 0x3f5f:bd(0x79a3,r.ax);r.ip=0x3f62;break;
        case 0x3f62:al(byte(0x79a3));r.ip=0x3f65;break;
        case 0x3f65:arithmetic(r.ax&255u,byte(0x79b4),true,true);r.ip=0x3f69;break;
        case 0x3f69:branch(!flag(0x40),0x3f6f,0x3f6b);break;
        case 0x3f6b:bd(0x79a3,increment(byte(0x79a3),false,true));r.ip=0x3f6f;break;
        case 0x3f6f:dl(byte(0x79a3));r.ip=0x3f73;break;
        case 0x3f7c:bus.writeByte(r.es,r.di,static_cast<uint8_t>(r.dx));r.ip=0x3f7f;break;
        case 0x3f7f:r.dx=word(0x78c4);r.ip=0x3f83;break;
        case 0x3f86:r.ax=shift(r.ax);r.ip=0x3f88;break;
        case 0x3f88:r.di=word(0x6612);r.es=word(0x6614);r.ip=0x3f8c;break;
        case 0x3f8e:bus.writeWord(r.es,r.di,r.dx);r.ip=0x3f91;break;
        case 0x3f91:wd(0x78c4,increment(word(0x78c4)));r.ip=0x3f95;break;
        case 0x3f95:push(bus.readWord(r.ss,static_cast<uint16_t>(r.bp-2u)));r.ip=0x3f98;break;
        case 0x3f98:case 0x3f9a:push(0);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x3f9c:r.di=0x79a3;r.ip=0x3f9f;break;
        case 0x3f9f:push(r.ds);r.ip=0x3fa0;break;
        case 0x3fa0:push(r.di);r.ip=0x3fa1;break;
        case 0x3fa1:push(0x3fa4);r.ip=0x370e;break;
        case 0x3fa4:r.sp=r.bp;r.bp=pop();r.ip=0x3fa5;break;
        case 0x3fa5:r.ip=pop();break;
        case 0x79d:r.cx=6;r.ip=0x7a0;break;
        case 0x7a0:bl(0xe6);r.ip=0x7a2;break;
        case 0x7a2:al(byte(0x79ad));r.ip=0x7a5;break;
        case 0x7a5:logic(0,true);r.ax&=255u;r.ip=0x7a7;break;
        case 0x7a7:r.dx=0x3c8;r.ip=0x7aa;break;
        case 0x7aa:case 0x7ae: { const auto value=static_cast<uint16_t>(r.ax&255u);al(r.bx);bl(value);r.ip=static_cast<uint16_t>(r.ip+2u);break; }
        case 0x7ac:case 0x7b0:case 0x7b3:case 0x7b4:
            bus.outByte(r.dx,static_cast<uint8_t>(r.ax));r.ip=static_cast<uint16_t>(r.ip+1u);break;
        case 0x7ad:r.dx=increment(r.dx);r.ip=0x7ae;break;
        case 0x7b1:case 0x7b5:r.ax=static_cast<uint16_t>((r.ax>>8)|(r.ax<<8));r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x7b7:r.dx=increment(r.dx,true);r.ip=0x7b8;break;
        case 0x7b8:al(arithmetic(r.ax&255u,7,false,true));r.ip=0x7ba;break;
        case 0x7ba:arithmetic(r.ax&255u,63,true,true);r.ip=0x7bc;break;
        case 0x7bc:branch(flag(0x40)||(flag(0x80)!=flag(0x800)),0x7c0,0x7be);break;
        case 0x7be:al(20);r.ip=0x7c0;break;
        case 0x7c0:bl(increment(r.bx&255u,false,true));r.ip=0x7c2;break;
        case 0x7c2:r.cx=static_cast<uint16_t>(r.cx-1u);r.ip=r.cx ? 0x7aa : 0x7c4;break;
        case 0x7c4:r.ip=pop();break;
        default:throw std::domain_error("Frame tail reached unowned instruction");
        }
    }
};
} // namespace lezac::core
