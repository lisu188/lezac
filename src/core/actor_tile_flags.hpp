#pragma once

#include "core/actor_contact.hpp"

namespace lezac::core {

enum class ActorTileFlagsOutcome { Running, Expiry, Motion, Behavior };
struct ActorTileFlagsSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    std::optional<ActorContactSnapshot> interrupt=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    ActorTileFlagsOutcome outcome=ActorTileFlagsOutcome::Running;
    bool operator==(const ActorTileFlagsSnapshot&) const = default;
};

// Original tile classification and behavior dispatch. Each exit is before the
// expiry (65A8), motion (6737), or nonzero-behavior (7018) continuation.
class ActorTileFlagsOperation {
public:
    ActorTileFlagsOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r,game,idToggle} {
        if (r.ip!=0x65a2) throw std::invalid_argument("Actor tile flags entry differs");
        validate();
    }
    explicit ActorTileFlagsOperation(ActorTileFlagsSnapshot state) : state_(state) { validate(); }
    const ActorTileFlagsSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return state_.interrupt ? ActorContactOperation(*state_.interrupt).registers() : state_.registers;
    }
    bool finished() const noexcept { return state_.outcome!=ActorTileFlagsOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.interrupt.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || state_.interrupt || !(state_.registers.flags&0x200u))
            throw std::logic_error("Actor tile flags IRQ is not eligible");
        ActorContactOperation irq(ActorContactSnapshot{state_.registers,state_.gameSegment,state_.idToggleMask});
        irq.deliverTimerInterrupt(bus);state_.interrupt=irq.snapshot();++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.interrupt) {
                ActorContactOperation irq(*state_.interrupt);
                if (irq.advance(1,bus)!=1) throw std::domain_error("Actor tile flags IRQ did not dispatch");
                ++state_.timerInstructions;
                if (irq.interruptInProgress()) state_.interrupt=irq.snapshot();
                else { state_.registers=irq.registers();state_.interrupt.reset(); }
            } else {
                instruction(bus);
                if (state_.registers.ip==0x65a8) state_.outcome=ActorTileFlagsOutcome::Expiry;
                if (state_.registers.ip==0x6737) state_.outcome=ActorTileFlagsOutcome::Motion;
                if (state_.registers.ip==0x7018) state_.outcome=ActorTileFlagsOutcome::Behavior;
            }
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    ActorTileFlagsSnapshot state_;
    void validate() const {
        const auto& r=state_.registers;
        if (r.cs!=state_.gameSegment || r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
            (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            (state_.outcome==ActorTileFlagsOutcome::Expiry && r.ip!=0x65a8) ||
            (state_.outcome==ActorTileFlagsOutcome::Motion && r.ip!=0x6737) ||
            (state_.outcome==ActorTileFlagsOutcome::Behavior && r.ip!=0x7018) ||
            (state_.interrupt && (finished() || state_.interrupt->registers!=r ||
                state_.interrupt->gameSegment!=state_.gameSegment || state_.interrupt->idToggleMask!=state_.idToggleMask ||
                !state_.interrupt->interrupt || state_.interrupt->outcome!=ActorContactOutcome::Running)))
            throw std::invalid_argument("Actor tile flags ownership differs");
        if (state_.interrupt) (void)ActorContactOperation(*state_.interrupt);
    }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    void compare(uint8_t a,uint8_t b) {
        const auto value=static_cast<uint8_t>(a-b);
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|
            (a<b ? 1u : 0u)|(std::popcount(value)%2==0 ? 4u : 0u)|((a^b^value)&16u)|
            (value==0 ? 0x40u : 0u)|(value&128u ? 0x80u : 0u)|(((a^b)&(a^value)&128u) ? 0x800u : 0u);
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        const auto lb=[&](int offset) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto sb=[&](int offset,uint8_t value) { bus.writeByte(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto data=[&](uint16_t offset) { return bus.readByte(r.ds,offset); };
        const auto al=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|value); };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        switch (r.ip) {
        case 0x65a2:compare(lb(-49),5);r.ip=0x65a6;break;
        case 0x65a6:branch(!flag(0x40),0x65da,0x65a8);break;
        case 0x65da:compare(lb(-15),13);r.ip=0x65de;break;
        case 0x65de:branch(!flag(0x40),0x6643,0x65e0);break;
        case 0x65e0:compare(data(0x2055),1);r.ip=0x65e5;break;
        case 0x65e5:branch(flag(1),0x65f4,0x65e7);break;
        case 0x65e7:compare(data(0x2055),82);r.ip=0x65ec;break;
        case 0x65ec:branch(!flag(1)&&!flag(0x40),0x65f4,0x65ee);break;
        case 0x65ee:sb(-33,1);r.ip=0x65f2;break;
        case 0x65f2:r.ip=0x65f8;break;
        case 0x65f4:sb(-33,0);r.ip=0x65f8;break;
        case 0x65f8:compare(data(0x2050),1);r.ip=0x65fd;break;
        case 0x65fd:branch(flag(1),0x660c,0x65ff);break;
        case 0x65ff:compare(data(0x2050),76);r.ip=0x6604;break;
        case 0x6604:branch(!flag(1)&&!flag(0x40),0x660c,0x6606);break;
        case 0x6606:sb(-35,1);r.ip=0x660a;break;
        case 0x660a:r.ip=0x6610;break;
        case 0x660c:sb(-35,0);r.ip=0x6610;break;
        case 0x6610:compare(data(0x2052),1);r.ip=0x6615;break;
        case 0x6615:branch(flag(1),0x6624,0x6617);break;
        case 0x6617:compare(data(0x2052),76);r.ip=0x661c;break;
        case 0x661c:branch(!flag(1)&&!flag(0x40),0x6624,0x661e);break;
        case 0x661e:sb(-36,1);r.ip=0x6622;break;
        case 0x6622:r.ip=0x6628;break;
        case 0x6624:sb(-36,0);r.ip=0x6628;break;
        case 0x6628:compare(data(0x204d),1);r.ip=0x662d;break;
        case 0x662d:branch(flag(1),0x663c,0x662f);break;
        case 0x662f:compare(data(0x204d),76);r.ip=0x6634;break;
        case 0x6634:branch(!flag(1)&&!flag(0x40),0x663c,0x6636);break;
        case 0x6636:sb(-34,1);r.ip=0x663a;break;
        case 0x663a:r.ip=0x6640;break;
        case 0x663c:sb(-34,0);r.ip=0x6640;break;
        case 0x6640:r.ip=0x66f3;break;
        case 0x6643:compare(data(0x2055),1);r.ip=0x6648;break;
        case 0x6648:branch(flag(1),0x6657,0x664a);break;
        case 0x664a:compare(data(0x2055),82);r.ip=0x664f;break;
        case 0x664f:branch(!flag(1)&&!flag(0x40),0x6657,0x6651);break;
        case 0x6651:sb(-33,1);r.ip=0x6655;break;
        case 0x6655:r.ip=0x666f;break;
        case 0x6657:compare(data(0x2056),1);r.ip=0x665c;break;
        case 0x665c:branch(flag(1),0x666b,0x665e);break;
        case 0x665e:compare(data(0x2056),82);r.ip=0x6663;break;
        case 0x6663:branch(!flag(1)&&!flag(0x40),0x666b,0x6665);break;
        case 0x6665:sb(-33,1);r.ip=0x6669;break;
        case 0x6669:r.ip=0x666f;break;
        case 0x666b:sb(-33,0);r.ip=0x666f;break;
        case 0x666f:compare(data(0x204c),1);r.ip=0x6674;break;
        case 0x6674:branch(flag(1),0x6683,0x6676);break;
        case 0x6676:compare(data(0x204c),76);r.ip=0x667b;break;
        case 0x667b:branch(!flag(1)&&!flag(0x40),0x6683,0x667d);break;
        case 0x667d:sb(-35,1);r.ip=0x6681;break;
        case 0x6681:r.ip=0x669b;break;
        case 0x6683:compare(data(0x2050),1);r.ip=0x6688;break;
        case 0x6688:branch(flag(1),0x6697,0x668a);break;
        case 0x668a:compare(data(0x2050),76);r.ip=0x668f;break;
        case 0x668f:branch(!flag(1)&&!flag(0x40),0x6697,0x6691);break;
        case 0x6691:sb(-35,1);r.ip=0x6695;break;
        case 0x6695:r.ip=0x669b;break;
        case 0x6697:sb(-35,0);r.ip=0x669b;break;
        case 0x669b:compare(data(0x204f),1);r.ip=0x66a0;break;
        case 0x66a0:branch(flag(1),0x66af,0x66a2);break;
        case 0x66a2:compare(data(0x204f),76);r.ip=0x66a7;break;
        case 0x66a7:branch(!flag(1)&&!flag(0x40),0x66af,0x66a9);break;
        case 0x66a9:sb(-36,1);r.ip=0x66ad;break;
        case 0x66ad:r.ip=0x66c7;break;
        case 0x66af:compare(data(0x2053),1);r.ip=0x66b4;break;
        case 0x66b4:branch(flag(1),0x66c3,0x66b6);break;
        case 0x66b6:compare(data(0x2053),76);r.ip=0x66bb;break;
        case 0x66bb:branch(!flag(1)&&!flag(0x40),0x66c3,0x66bd);break;
        case 0x66bd:sb(-36,1);r.ip=0x66c1;break;
        case 0x66c1:r.ip=0x66c7;break;
        case 0x66c3:sb(-36,0);r.ip=0x66c7;break;
        case 0x66c7:compare(data(0x2049),1);r.ip=0x66cc;break;
        case 0x66cc:branch(flag(1),0x66db,0x66ce);break;
        case 0x66ce:compare(data(0x2049),76);r.ip=0x66d3;break;
        case 0x66d3:branch(!flag(1)&&!flag(0x40),0x66db,0x66d5);break;
        case 0x66d5:sb(-34,1);r.ip=0x66d9;break;
        case 0x66d9:r.ip=0x66f3;break;
        case 0x66db:compare(data(0x204a),1);r.ip=0x66e0;break;
        case 0x66e0:branch(flag(1),0x66ef,0x66e2);break;
        case 0x66e2:compare(data(0x204a),76);r.ip=0x66e7;break;
        case 0x66e7:branch(!flag(1)&&!flag(0x40),0x66ef,0x66e9);break;
        case 0x66e9:sb(-34,1);r.ip=0x66ed;break;
        case 0x66ed:r.ip=0x66f3;break;
        case 0x66ef:sb(-34,0);r.ip=0x66f3;break;
        case 0x66f3:al(lb(-49));r.ip=0x66f6;break;
        case 0x66f6:compare(static_cast<uint8_t>(r.ax),0);r.ip=0x66f8;break;
        case 0x66f8:branch(flag(0x40),0x66fd,0x66fa);break;
        case 0x66fa:r.ip=0x7018;break;
        case 0x66fd:compare(lb(-35),0);r.ip=0x6701;break;
        case 0x6701:branch(flag(0x40),0x6711,0x6703);break;
        case 0x6703:compare(data(0x204c),1);r.ip=0x6708;break;
        case 0x6708:branch(flag(1),0x6715,0x670a);break;
        case 0x670a:compare(data(0x204c),76);r.ip=0x670f;break;
        case 0x670f:branch(!flag(1)&&!flag(0x40),0x6715,0x6711);break;
        case 0x6711:al(0);r.ip=0x6713;break;
        case 0x6713:r.ip=0x6717;break;
        case 0x6715:al(1);r.ip=0x6717;break;
        case 0x6717:sb(-37,static_cast<uint8_t>(r.ax));r.ip=0x671a;break;
        case 0x671a:compare(lb(-36),0);r.ip=0x671e;break;
        case 0x671e:branch(flag(0x40),0x672e,0x6720);break;
        case 0x6720:compare(data(0x204f),1);r.ip=0x6725;break;
        case 0x6725:branch(flag(1),0x6732,0x6727);break;
        case 0x6727:compare(data(0x204f),76);r.ip=0x672c;break;
        case 0x672c:branch(!flag(1)&&!flag(0x40),0x6732,0x672e);break;
        case 0x672e:al(0);r.ip=0x6730;break;
        case 0x6730:r.ip=0x6734;break;
        case 0x6732:al(1);r.ip=0x6734;break;
        case 0x6734:sb(-38,static_cast<uint8_t>(r.ax));r.ip=0x6737;break;
        default:throw std::domain_error("Actor tile flags reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
