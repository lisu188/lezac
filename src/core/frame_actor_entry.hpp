#pragma once

#include "core/actor_animation.hpp"
#include "core/boss_links.hpp"
#include "core/frame_prefix.hpp"

namespace lezac::core {

enum class FrameActorEntryOutcome { Running, ActorBody, TransientQueues, Restart, EndRunUi, RuntimeError, BreakOutput };
enum class FrameActorEntryKind { None, NonPlayer, PlayerOne, PlayerTwo };
struct FrameActorCallerSnapshot {
    DosGetTimeRegisters registers;
    bool operator==(const FrameActorCallerSnapshot&) const = default;
};
using FrameActorEntryCallee=std::variant<FramePrefixSnapshot,FrameActorCallerSnapshot,BossLinksSnapshot,ActorAnimationSnapshot>;
struct FrameActorEntrySnapshot {
    FrameActorEntryCallee callee;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    FrameActorEntryOutcome outcome=FrameActorEntryOutcome::Running;
    FrameActorEntryKind actorKind=FrameActorEntryKind::None;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0,prefixTimerInstructions=0,prefixTimerDeliveries=0;
    uint64_t tailTimerInstructions=0,tailTimerDeliveries=0;
    bool operator==(const FrameActorEntrySnapshot&) const = default;
};

// Continuous prefix -> links -> caller selection -> first actor's 6053..615A.
// ActorBody is a live-stack handoff before behavior, not a completed actor/frame.
class FrameActorEntryOperation {
public:
    using CopyBudget=FramePrefixOperation::CopyBudget;
    FrameActorEntryOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r.ip==0x7ebb ? FrameActorEntryCallee{FrameActorCallerSnapshot{r}} :
            FrameActorEntryCallee{FramePrefixOperation(r,game,idToggle).snapshot()},game,idToggle} { validate(); }
    FrameActorEntryOperation(DosGetTimeRegisters r,uint16_t dos,uint16_t keyboard,uint16_t psp,
                            uint16_t game,uint32_t idToggle)
        : state_{FramePrefixOperation(r,dos,keyboard,psp,game,idToggle).snapshot(),game,idToggle} { validate(); }
    explicit FrameActorEntryOperation(FrameActorEntrySnapshot state) : state_(state) { validate(); }
    const FrameActorEntrySnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome!=FrameActorEntryOutcome::Running && !state_.timer; }
    DosGetTimeRegisters registers() const {
        if (state_.timer) return fromTimer(state_.timer->registers);
        return std::visit([](const auto& child) -> DosGetTimeRegisters {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FramePrefixSnapshot>) return FramePrefixOperation(child).registers();
            else return child.registers;
        },state_.callee);
    }
    bool interruptInProgress() const {
        if (state_.timer) return true;
        const auto* prefix=std::get_if<FramePrefixSnapshot>(&state_.callee);
        return prefix && FramePrefixOperation(*prefix).interruptInProgress();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || interruptInProgress() || !(registers().flags&0x200u))
            throw std::logic_error("Frame actor entry IRQ is not eligible");
        if (auto* prefix=std::get_if<FramePrefixSnapshot>(&state_.callee)) {
            FramePrefixOperation operation(*prefix);operation.deliverTimerInterrupt(bus);*prefix=operation.snapshot();
            state_.prefixTimerDeliveries=prefix->timerDeliveries;
        } else {
            auto r=registers();
            const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
            push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);
            r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
            state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
            ++state_.tailTimerDeliveries;
        }
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation operation(*state_.timer);
                if (operation.advance(1,bus)!=1) throw std::domain_error("Frame actor IRQ did not dispatch");
                ++state_.tailTimerInstructions;
                if (operation.returned()) {
                    const auto r=fromTimer(operation.snapshot().registers);
                    std::visit([&](auto& child) {
                        using Child=std::remove_cvref_t<decltype(child)>;
                        if constexpr (!std::is_same_v<Child,FramePrefixSnapshot>) child.registers=r;
                    },state_.callee);
                    state_.timer.reset();
                } else state_.timer=operation.snapshot();
            } else {
                int handoff=-1;
                DosGetTimeRegisters next;
                std::visit([&](auto& child) {
                    using Child=std::remove_cvref_t<decltype(child)>;
                    if constexpr (std::is_same_v<Child,FramePrefixSnapshot>) {
                        FramePrefixOperation operation(child);
                        if (operation.advance(1,bus,copies)!=1) throw std::domain_error("Frame actor prefix did not dispatch");
                        child=operation.snapshot();
                        state_.prefixTimerInstructions=child.timerInstructions;
                        state_.prefixTimerDeliveries=child.timerDeliveries;
                        if (operation.finished()) {
                            next=operation.registers();
                            if (child.outcome==FramePrefixOutcome::ActorUpdate) handoff=0;
                            else state_.outcome=child.outcome==FramePrefixOutcome::EndRunUi ? FrameActorEntryOutcome::EndRunUi :
                                child.outcome==FramePrefixOutcome::BreakOutput ? FrameActorEntryOutcome::BreakOutput : FrameActorEntryOutcome::RuntimeError;
                        }
                    } else if constexpr (std::is_same_v<Child,FrameActorCallerSnapshot>) {
                        callerInstruction(child.registers,bus);next=child.registers;
                        if (next.ip==0x432a) handoff=1;
                        if (next.ip==0x6053) handoff=2;
                        if (next.ip==0x804e) state_.outcome=FrameActorEntryOutcome::TransientQueues;
                        if (next.ip==0x77dc) state_.outcome=FrameActorEntryOutcome::Restart;
                    } else if constexpr (std::is_same_v<Child,BossLinksSnapshot>) {
                        BossLinksOperation operation(child);
                        if (operation.advance(1,bus)!=1) throw std::domain_error("Frame actor links did not dispatch");
                        child=operation.snapshot();
                        if (operation.finished()) {
                            if (operation.returned()) { handoff=0;next=child.registers; }
                            else state_.outcome=FrameActorEntryOutcome::RuntimeError;
                        }
                    } else {
                        ActorAnimationOperation operation(child);
                        if (operation.advance(1,bus,copies)!=1) throw std::domain_error("Frame actor prologue did not dispatch");
                        child=operation.snapshot();
                        if (operation.finished()) state_.outcome=operation.atBehaviorDispatch() ?
                            FrameActorEntryOutcome::ActorBody : FrameActorEntryOutcome::RuntimeError;
                    }
                },state_.callee);
                if (handoff==0) state_.callee=FrameActorCallerSnapshot{next};
                if (handoff==1) state_.callee=BossLinksOperation(next,state_.gameSegment).snapshot();
                if (handoff==2) state_.callee=ActorAnimationOperation(next,state_.gameSegment).snapshot();
            }
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }

private:
    FrameActorEntrySnapshot state_;
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    void validate() const {
        if (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000)
            throw std::invalid_argument("Frame actor entry ID-toggle profile differs");
        const bool matching=std::visit([&](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FramePrefixSnapshot>)
                return child.gameSegment==state_.gameSegment && child.idToggleMask==state_.idToggleMask;
            else if constexpr (std::is_same_v<Child,FrameActorCallerSnapshot>)
                return child.registers.cs==state_.gameSegment && child.registers.ds==static_cast<uint16_t>(state_.gameSegment+0xaa2);
            else return child.gameSegment==state_.gameSegment;
        },state_.callee);
        if (!matching || (state_.timer && (std::holds_alternative<FramePrefixSnapshot>(state_.callee) ||
                state_.outcome!=FrameActorEntryOutcome::Running)))
            throw std::invalid_argument("Frame actor entry callee/IRQ ownership differs");
    }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    static uint16_t arithmetic(DosGetTimeRegisters& r,uint16_t left,uint16_t right,bool subtract=false,bool byte=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u;
        const uint32_t wide=subtract ? uint32_t{left}-right : uint32_t{left}+right;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t flags=valueFlags(value,byte)|((left^right^value)&16u);
        if (subtract ? left<right : wide>mask) flags|=1;
        if (subtract ? ((left^right)&(left^value)&sign) : (~(left^right)&(left^value)&sign)) flags|=0x800;
        r.flags=(r.flags&~uint32_t{0x8d5})|flags;return value;
    }
    void callerInstruction(DosGetTimeRegisters& r,const TimerIrqBus& bus) {
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto flag=[&](uint32_t bit) { return (r.flags&bit)!=0; };
        const auto branch=[&](bool yes,uint16_t target,uint16_t next) { r.ip=yes ? target : next; };
        const auto byte=[&](uint16_t offset) { return bus.readByte(r.ds,offset); };
        const auto increment=[&](uint16_t offset,bool isByte) {
            const auto carry=r.flags&1u;
            const auto value=arithmetic(r,isByte ? byte(offset) : bus.readWord(r.ds,offset),1,false,isByte);
            if (isByte) bus.writeByte(r.ds,offset,static_cast<uint8_t>(value));else bus.writeWord(r.ds,offset,value);
            r.flags=(r.flags&~uint32_t{1})|carry;
        };
        const auto multiplyActor=[&] {
            const auto signedSlot=std::bit_cast<int16_t>(bus.readWord(r.ds,0x2082));
            const int32_t value=int32_t{signedSlot}*38;
            r.di=static_cast<uint16_t>(value);
            r.flags=(r.flags&~uint32_t{0x801})|((value < -32768 || value > 32767) ? 0x801u : 0u);
        };
        switch (r.ip) {
        case 0x7ebb:arithmetic(r,byte(0x79f9),0,true,true);r.ip=0x7ec0;break;
        case 0x7ec0:branch(flag(1)||flag(0x40),0x7ec5,0x7ec2);break;
        case 0x7ec2:push(0x7ec5);r.ip=0x432a;break;
        case 0x7ec5:bus.writeWord(r.ds,0x2082,1);r.ip=0x7ecb;break;
        case 0x7ecb:r.ax=static_cast<uint16_t>((r.ax&0xff00u)|byte(0x208d));r.ip=0x7ece;break;
        case 0x7ece:r.ax&=255u;r.flags=(r.flags&~uint32_t{0x8d5})|0x44u;r.ip=0x7ed0;break;
        case 0x7ed0:arithmetic(r,r.ax,bus.readWord(r.ds,0x2082),true);r.ip=0x7ed4;break;
        case 0x7ed4:branch(flag(1),0x7eea,0x7ed6);break;
        case 0x7ed6:multiplyActor();r.ip=0x7edb;break;
        case 0x7edb:r.di=arithmetic(r,r.di,0x1bae);r.ip=0x7edf;break;
        case 0x7edf:push(r.ds);r.ip=0x7ee0;break;
        case 0x7ee0:push(r.di);r.ip=0x7ee1;break;
        case 0x7ee1:push(0x7ee4);r.ip=0x6053;state_.actorKind=FrameActorEntryKind::NonPlayer;break;
        case 0x7eea:arithmetic(r,byte(0x79e6),1,true,true);r.ip=0x7eef;break;
        case 0x7eef:branch(flag(0x40),0x7f2f,0x7ef1);break;
        case 0x7ef1:arithmetic(r,byte(0x79e7),1,true,true);r.ip=0x7ef6;break;
        case 0x7ef6:branch(flag(0x40),0x7f2f,0x7ef8);break;
        case 0x7ef8:increment(0x79b9,true);r.ip=0x7efc;break;
        case 0x7efc:arithmetic(r,byte(0x79b9),0xe6,true,true);r.ip=0x7f01;break;
        case 0x7f01:branch(!flag(0x40),0x7f2d,0x7f03);break;
        case 0x7f03:bus.writeWord(r.ds,0x2082,1);r.ip=0x7f09;break;
        case 0x7f09:r.ip=0x7f0f;break;
        case 0x7f0b:increment(0x2082,false);r.ip=0x7f0f;break;
        case 0x7f0f:r.di=bus.readWord(r.ds,0x2082);r.ip=0x7f13;break;
        case 0x7f13:arithmetic(r,byte(static_cast<uint16_t>(r.di+0x79e5u)),2,true,true);r.ip=0x7f18;break;
        case 0x7f18:branch(!flag(0x40),0x7f23,0x7f1a);break;
        case 0x7f1a:r.di=bus.readWord(r.ds,0x2082);r.ip=0x7f1e;break;
        case 0x7f1e:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x79e5u),1);r.ip=0x7f23;break;
        case 0x7f23:arithmetic(r,bus.readWord(r.ds,0x2082),2,true);r.ip=0x7f28;break;
        case 0x7f28:branch(!flag(0x40),0x7f0b,0x7f2a);break;
        case 0x7f2a:r.ip=0x77dc;break;
        case 0x7f2d:r.ip=0x7f34;break;
        case 0x7f2f:bus.writeByte(r.ds,0x79b9,0);r.ip=0x7f34;break;
        case 0x7f34:bus.writeWord(r.ds,0x2082,1);r.ip=0x7f3a;break;
        case 0x7f3a:r.ip=0x7f40;break;
        case 0x7f3c:increment(0x2082,false);r.ip=0x7f40;break;
        case 0x7f40:r.di=bus.readWord(r.ds,0x2082);r.ip=0x7f44;break;
        case 0x7f44:arithmetic(r,byte(static_cast<uint16_t>(r.di+0x79e5u)),1,true,true);r.ip=0x7f49;break;
        case 0x7f49:branch(flag(0x40),0x7f4e,0x7f4b);break;
        case 0x7f4b:r.ip=0x8044;break;
        case 0x7f4e:multiplyActor();r.ip=0x7f53;break;
        case 0x7f53:r.di=arithmetic(r,r.di,0x1b62);r.ip=0x7f57;break;
        case 0x7f57:push(r.ds);r.ip=0x7f58;break;
        case 0x7f58:push(r.di);r.ip=0x7f59;break;
        case 0x7f59:push(0x7f5c);r.ip=0x6053;
            state_.actorKind=bus.readWord(r.ds,0x2082)==1 ? FrameActorEntryKind::PlayerOne : FrameActorEntryKind::PlayerTwo;break;
        case 0x8044:arithmetic(r,bus.readWord(r.ds,0x2082),2,true);r.ip=0x8049;break;
        case 0x8049:branch(flag(0x40),0x804e,0x804b);break;
        case 0x804b:r.ip=0x7f3c;break;
        default:throw std::domain_error("Frame actor caller reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
