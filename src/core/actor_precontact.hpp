#pragma once

#include "core/boss_links.hpp"
#include "core/frame_actor_entry.hpp"
#include "core/frame_spawner.hpp"

namespace lezac::core {

enum class ActorPrecontactOutcome { Running, BehaviorDispatch, RuntimeError };
struct ActorPrecontactSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    ActorPrecontactOutcome outcome=ActorPrecontactOutcome::Running;
    bool operator==(const ActorPrecontactSnapshot&) const = default;
};

// Original 615A..654E, including player context, link application and pickups.
// The actor's caller/prologue stack remains live at the next behavior gate.
class ActorPrecontactOperation {
public:
    ActorPrecontactOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r,game,idToggle} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x615a)
            throw std::invalid_argument("Actor precontact entry differs");
        validate();
    }
    explicit ActorPrecontactOperation(ActorPrecontactSnapshot state) : state_(state) { validate(); }
    const ActorPrecontactSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return state_.timer ? fromTimer(state_.timer->registers) : state_.registers; }
    bool finished() const noexcept { return state_.outcome!=ActorPrecontactOutcome::Running && !state_.timer; }
    bool interruptInProgress() const noexcept { return state_.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || state_.timer || !(state_.registers.flags&0x200u))
            throw std::logic_error("Actor precontact IRQ is not eligible");
        auto r=state_.registers;
        const auto push=[&](uint16_t v) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,v); };
        push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);
        r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
        state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation timer(*state_.timer);
                if (timer.advance(1,bus)!=1) throw std::domain_error("Actor precontact IRQ did not dispatch");
                ++state_.timerInstructions;
                if (timer.returned()) { state_.registers=fromTimer(timer.snapshot().registers);state_.timer.reset(); }
                else state_.timer=timer.snapshot();
            } else {
                instruction(bus);
                const auto& r=state_.registers;
                if (r.cs==state_.gameSegment && r.ip==0x654e) state_.outcome=ActorPrecontactOutcome::BehaviorDispatch;
                if (r.cs==library() && r.ip==0xe2) state_.outcome=ActorPrecontactOutcome::RuntimeError;
            }
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }

private:
    ActorPrecontactSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    void validate() const {
        if (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000)
            throw std::invalid_argument("Actor precontact ID-toggle profile differs");
        if (state_.registers.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
            (state_.registers.cs!=state_.gameSegment && state_.registers.cs!=library()) ||
            (state_.timer && state_.outcome!=ActorPrecontactOutcome::Running))
            throw std::invalid_argument("Actor precontact register/IRQ ownership differs");
    }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t v,bool byte=false) {
        return (v==0 ? 0x40u : 0u)|(v&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(v))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t v) {
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(v);return v;
    }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false,bool byte=false,bool carry=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u,extra=carry && flag(1) ? 1u : 0u;
        const uint32_t wide=subtract ? uint32_t{a}-b-extra : uint32_t{a}+b+extra;
        const auto v=static_cast<uint16_t>(wide&mask);
        uint32_t f=valueFlags(v,byte)|((a^b^v)&16u);
        if (subtract ? uint32_t{a}<uint32_t{b}+extra : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^v)&sign) : (~(a^b)&(a^v)&sign)) f|=0x800;
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|f;return v;
    }
    uint16_t shift(uint16_t v,unsigned count,bool right=false) {
        for (unsigned i=0;i<count;++i) {
            const auto original=v;const auto c=right ? (v&1u) : (v>>15);
            v=static_cast<uint16_t>(right ? v>>1 : v<<1);
            state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(v)|c|16u|
                (right ? (original&0x8000u ? 0x800u : 0u) : ((original^v)&0x8000u ? 0x800u : 0u));
        }
        return v;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t v) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,v); };
        const auto pop=[&] { const auto v=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return v; };
        const auto local=[&](int o) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+o)); };
        const auto lb=[&](int o) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+o)); };
        const auto store=[&](int o,uint16_t v) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+o),v); };
        const auto sb=[&](int o,uint8_t v) { bus.writeByte(r.ss,static_cast<uint16_t>(r.bp+o),v); };
        const auto les=[&](int o) { r.di=local(o);r.es=local(o+2); };
        const auto read=[&](unsigned o) { return bus.readWord(r.es,static_cast<uint16_t>(r.di+o)); };
        const auto byte=[&](unsigned o) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+o)); };
        const auto write=[&](unsigned o,uint16_t v) { bus.writeWord(r.es,static_cast<uint16_t>(r.di+o),v); };
        const auto wb=[&](unsigned o,uint8_t v) { bus.writeByte(r.es,static_cast<uint16_t>(r.di+o),v); };
        const auto data=[&](uint16_t o) { return bus.readByte(r.ds,o); };
        const auto al=[&](uint8_t v) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|v); };
        const auto zeroAh=[&] { r.ax&=255u;r.flags=(r.flags&~uint32_t{0x8d5})|0x44u; };
        const auto cwd=[&] { r.dx=(r.ax&0x8000u) ? 0xffff : 0; };
        const auto branch=[&](bool yes,uint16_t target,uint16_t next) { r.ip=yes ? target : next; };
        const auto nearCall=[&](uint16_t target,uint16_t next) { push(next);r.ip=target; };
        const auto farCall=[&](uint16_t target,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=target; };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        const auto multiply=[&](uint16_t v) {
            const uint32_t product=uint32_t{r.ax}*v;r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
            r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
        };
        if (r.cs==library()) {
            if (r.ip>=0x13a8 && r.ip<=0x142c) {
                FrameSpawnerOperation runtime(FrameSpawnerSnapshot{r,state_.gameSegment});
                runtime.advance(1,bus);r=runtime.snapshot().registers;
            } else {
                BossLinksOperation runtime(BossLinksSnapshot{r,state_.gameSegment});
                runtime.advance(1,bus);r=runtime.snapshot().registers;
            }
            return;
        }
        if (r.cs!=state_.gameSegment) throw std::domain_error("Actor precontact left recovered code");
        switch (r.ip) {
        case 0x615a:les(4);r.ip=0x615d;break;
        case 0x615d:al(byte(21));r.ip=0x6161;break;
        case 0x6161:sb(-49,static_cast<uint8_t>(r.ax));r.ip=0x6164;break;
        case 0x6164:les(4);r.ip=0x6167;break;
        case 0x6167:al(byte(22));r.ip=0x616b;break;
        case 0x616b:sb(-20,static_cast<uint8_t>(r.ax));r.ip=0x616e;break;
        case 0x616e:al(lb(-49));r.ip=0x6171;break;
        case 0x6171:arithmetic(r.ax&255u,0,true,true);r.ip=0x6173;break;
        case 0x6173:branch(!flag(0x40),0x61da,0x6175);break;
        case 0x6175:al(data(0x1b78));r.ip=0x6178;break;
        case 0x6178:bus.writeByte(r.ds,0x1b82,static_cast<uint8_t>(r.ax));r.ip=0x617b;break;
        case 0x617b:al(data(0x1b79));r.ip=0x617e;break;
        case 0x617e:bus.writeByte(r.ds,0x1b83,static_cast<uint8_t>(r.ax));r.ip=0x6181;break;
        case 0x6181:al(data(0x1b7a));r.ip=0x6184;break;
        case 0x6184:bus.writeByte(r.ds,0x1b84,static_cast<uint8_t>(r.ax));r.ip=0x6187;break;
        case 0x6187:al(data(0x1b7b));r.ip=0x618a;break;
        case 0x618a:bus.writeByte(r.ds,0x1b85,static_cast<uint8_t>(r.ax));r.ip=0x618d;break;
        case 0x618d:al(data(0x1b7c));r.ip=0x6190;break;
        case 0x6190:bus.writeByte(r.ds,0x1b86,static_cast<uint8_t>(r.ax));r.ip=0x6193;break;
        case 0x6193:sb(-21,18);r.ip=0x6197;break;
        case 0x6197:sb(-22,19);r.ip=0x619b;break;
        case 0x619b:sb(-23,1);r.ip=0x619f;break;
        case 0x619f:al(data(0x64));r.ip=0x61a2;break;
        case 0x61a2:sb(-24,static_cast<uint8_t>(r.ax));r.ip=0x61a5;break;
        case 0x61a5:al(data(0x65));r.ip=0x61a8;break;
        case 0x61a8:sb(-25,static_cast<uint8_t>(r.ax));r.ip=0x61ab;break;
        case 0x61ab:al(data(0x62));r.ip=0x61ae;break;
        case 0x61ae:sb(-26,static_cast<uint8_t>(r.ax));r.ip=0x61b1;break;
        case 0x61b1:al(data(0x63));r.ip=0x61b4;break;
        case 0x61b4:sb(-27,static_cast<uint8_t>(r.ax));r.ip=0x61b7;break;
        case 0x61b7:r.ax=0x785a;r.ip=0x61ba;break;
        case 0x61ba:r.dx=r.ds;r.ip=0x61bc;break;
        case 0x61bc:store(-54,r.ax);r.ip=0x61bf;break;
        case 0x61bf:store(-52,r.dx);r.ip=0x61c2;break;
        case 0x61c2:al(data(0x79ae));r.ip=0x61c5;break;
        case 0x61c5:sb(-28,static_cast<uint8_t>(r.ax));r.ip=0x61c8;break;
        case 0x61c8:sb(-29,1);r.ip=0x61cc;break;
        case 0x61cc:r.ax=0x79b0;r.ip=0x61cf;break;
        case 0x61cf:r.dx=r.ds;r.ip=0x61d1;break;
        case 0x61d1:bus.writeWord(r.ds,0x79bc,r.ax);r.ip=0x61d4;break;
        case 0x61d4:bus.writeWord(r.ds,0x79be,r.dx);r.ip=0x61d8;break;
        case 0x61d8:r.ip=0x6245;break;
        case 0x61da:arithmetic(r.ax&255u,1,true,true);r.ip=0x61dc;break;
        case 0x61dc:branch(!flag(0x40),0x6245,0x61de);break;
        case 0x61de:al(data(0x1b7d));r.ip=0x61e1;break;
        case 0x61e1:bus.writeByte(r.ds,0x1b82,static_cast<uint8_t>(r.ax));r.ip=0x61e4;break;
        case 0x61e4:al(data(0x1b7e));r.ip=0x61e7;break;
        case 0x61e7:bus.writeByte(r.ds,0x1b83,static_cast<uint8_t>(r.ax));r.ip=0x61ea;break;
        case 0x61ea:al(data(0x1b7f));r.ip=0x61ed;break;
        case 0x61ed:bus.writeByte(r.ds,0x1b84,static_cast<uint8_t>(r.ax));r.ip=0x61f0;break;
        case 0x61f0:al(data(0x1b80));r.ip=0x61f3;break;
        case 0x61f3:bus.writeByte(r.ds,0x1b85,static_cast<uint8_t>(r.ax));r.ip=0x61f6;break;
        case 0x61f6:al(data(0x1b81));r.ip=0x61f9;break;
        case 0x61f9:bus.writeByte(r.ds,0x1b86,static_cast<uint8_t>(r.ax));r.ip=0x61fc;break;
        case 0x61fc:sb(-49,0);r.ip=0x6200;break;
        case 0x6200:sb(-21,37);r.ip=0x6204;break;
        case 0x6204:sb(-22,38);r.ip=0x6208;break;
        case 0x6208:sb(-23,20);r.ip=0x620c;break;
        case 0x620c:al(data(0x68));r.ip=0x620f;break;
        case 0x620f:sb(-24,static_cast<uint8_t>(r.ax));r.ip=0x6212;break;
        case 0x6212:al(data(0x69));r.ip=0x6215;break;
        case 0x6215:sb(-25,static_cast<uint8_t>(r.ax));r.ip=0x6218;break;
        case 0x6218:al(data(0x66));r.ip=0x621b;break;
        case 0x621b:sb(-26,static_cast<uint8_t>(r.ax));r.ip=0x621e;break;
        case 0x621e:al(data(0x67));r.ip=0x6221;break;
        case 0x6221:sb(-27,static_cast<uint8_t>(r.ax));r.ip=0x6224;break;
        case 0x6224:r.ax=0x7888;r.ip=0x6227;break;
        case 0x6227:r.dx=r.ds;r.ip=0x6229;break;
        case 0x6229:store(-54,r.ax);r.ip=0x622c;break;
        case 0x622c:store(-52,r.dx);r.ip=0x622f;break;
        case 0x622f:al(data(0x79af));r.ip=0x6232;break;
        case 0x6232:sb(-28,static_cast<uint8_t>(r.ax));r.ip=0x6235;break;
        case 0x6235:sb(-29,2);r.ip=0x6239;break;
        case 0x6239:r.ax=0x79b1;r.ip=0x623c;break;
        case 0x623c:r.dx=r.ds;r.ip=0x623e;break;
        case 0x623e:bus.writeWord(r.ds,0x79bc,r.ax);r.ip=0x6241;break;
        case 0x6241:bus.writeWord(r.ds,0x79be,r.dx);r.ip=0x6245;break;
        case 0x6245:al(lb(-19));r.ip=0x6248;break;
        case 0x6248:zeroAh();r.ip=0x624a;break;
        case 0x624a:r.di=r.ax;r.ip=0x624c;break;
        case 0x624c:r.di=shift(r.di,3);r.ip=0x624f;break;
        case 0x624f:r.di=arithmetic(r.di,0xc21e);r.ip=0x6253;break;
        case 0x6253:store(-58,r.di);r.ip=0x6256;break;
        case 0x6256:store(-56,r.ds);r.ip=0x6259;break;
        case 0x6259:les(-58);r.ip=0x625c;break;
        case 0x625c:r.ax=read(0);r.ip=0x625f;break;
        case 0x625f:store(-44,r.ax);r.ip=0x6262;break;
        case 0x6262:les(-58);r.ip=0x6265;break;
        case 0x6265:r.ax=read(2);r.ip=0x6269;break;
        case 0x6269:store(-46,r.ax);r.ip=0x626c;break;
        case 0x626c:les(4);r.ip=0x626f;break;
        case 0x626f:store(-58,r.di);r.ip=0x6272;break;
        case 0x6272:store(-56,r.es);r.ip=0x6275;break;
        case 0x6275:les(-58);r.ip=0x6278;break;
        case 0x6278:al(byte(10));r.ip=0x627c;break;
        case 0x627c:sb(-16,static_cast<uint8_t>(r.ax));r.ip=0x627f;break;
        case 0x627f:les(-58);r.ip=0x6282;break;
        case 0x6282:al(byte(12));r.ip=0x6286;break;
        case 0x6286:sb(-17,static_cast<uint8_t>(r.ax));r.ip=0x6289;break;
        case 0x6289:les(-58);r.ip=0x628c;break;
        case 0x628c:r.ax=read(6);r.ip=0x6290;break;
        case 0x6290:store(-12,r.ax);r.ip=0x6293;break;
        case 0x6293:les(-58);r.ip=0x6296;break;
        case 0x6296:r.ax=read(8);r.ip=0x629a;break;
        case 0x629a:store(-14,r.ax);r.ip=0x629d;break;
        case 0x629d:les(-58);r.ip=0x62a0;break;
        case 0x62a0:al(byte(20));r.ip=0x62a4;break;
        case 0x62a4:r.ax=(r.ax&128u) ? static_cast<uint16_t>((r.ax&255u)|0xff00u) : r.ax&255u;r.ip=0x62a5;break;
        case 0x62a5:cwd();r.ip=0x62a6;break;
        case 0x62a6:r.cx=r.ax;r.ip=0x62a8;break;
        case 0x62a8:r.bx=r.dx;r.ip=0x62aa;break;
        case 0x62aa:r.ax=local(-46);r.ip=0x62ad;break;
        case 0x62ad:r.dx=logic(0);r.ip=0x62af;break;
        case 0x62af:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x62b1;break;
        case 0x62b1:r.dx=arithmetic(r.dx,r.bx,true,false,true);r.ip=0x62b3;break;
        case 0x62b3:store(-46,r.ax);r.ip=0x62b6;break;
        case 0x62b6:les(-58);r.ip=0x62b9;break;
        case 0x62b9:al(byte(0));r.ip=0x62bc;break;
        case 0x62bc:sb(-15,static_cast<uint8_t>(r.ax));r.ip=0x62bf;break;
        case 0x62bf:r.ax=local(-44);r.ip=0x62c2;break;
        case 0x62c2:store(-48,r.ax);r.ip=0x62c5;break;
        case 0x62c5:arithmetic(lb(-15),1,true,true);r.ip=0x62c9;break;
        case 0x62c9:branch(flag(1),0x62d1,0x62cb);break;
        case 0x62cb:arithmetic(lb(-15),8,true,true);r.ip=0x62cf;break;
        case 0x62cf:branch(flag(1)||flag(0x40),0x62da,0x62d1);break;
        case 0x62d1:arithmetic(lb(-15),18,true,true);r.ip=0x62d5;break;
        case 0x62d5:branch(!flag(1)&&!flag(0x40),0x62da,0x62d7);break;
        case 0x62d7:r.ip=0x654e;break;
        case 0x62da:arithmetic(data(0x79e6),1,true,true);r.ip=0x62df;break;
        case 0x62df:branch(!flag(0x40),0x6310,0x62e1);break;
        case 0x62e1:al(data(0x1b89));r.ip=0x62e4;break;
        case 0x62e4:zeroAh();r.ip=0x62e6;break;
        case 0x62e6:r.di=r.ax;r.ip=0x62e8;break;
        case 0x62e8:r.di=shift(r.di,3);r.ip=0x62eb;break;
        case 0x62eb:r.di=arithmetic(r.di,0xc21e);r.ip=0x62ef;break;
        case 0x62ef:store(-58,r.di);r.ip=0x62f2;break;
        case 0x62f2:store(-56,r.ds);r.ip=0x62f5;break;
        case 0x62f5:les(-58);r.ip=0x62f8;break;
        case 0x62f8:r.ax=read(0);r.ip=0x62fb;break;
        case 0x62fb:r.ax=arithmetic(r.ax,local(-44),true);r.ip=0x62fe;break;
        case 0x62fe:store(-4,r.ax);r.ip=0x6301;break;
        case 0x6301:les(-58);r.ip=0x6304;break;
        case 0x6304:r.ax=read(2);r.ip=0x6308;break;
        case 0x6308:r.ax=arithmetic(r.ax,local(-46),true);r.ip=0x630b;break;
        case 0x630b:store(-6,r.ax);r.ip=0x630e;break;
        case 0x630e:r.ip=0x6315;break;
        case 0x6310:store(-4,6000);r.ip=0x6315;break;
        case 0x6315:arithmetic(data(0x79e7),1,true,true);r.ip=0x631a;break;
        case 0x631a:branch(!flag(0x40),0x634b,0x631c);break;
        case 0x631c:al(data(0x1baf));r.ip=0x631f;break;
        case 0x631f:zeroAh();r.ip=0x6321;break;
        case 0x6321:r.di=r.ax;r.ip=0x6323;break;
        case 0x6323:r.di=shift(r.di,3);r.ip=0x6326;break;
        case 0x6326:r.di=arithmetic(r.di,0xc21e);r.ip=0x632a;break;
        case 0x632a:store(-58,r.di);r.ip=0x632d;break;
        case 0x632d:store(-56,r.ds);r.ip=0x6330;break;
        case 0x6330:les(-58);r.ip=0x6333;break;
        case 0x6333:r.ax=read(0);r.ip=0x6336;break;
        case 0x6336:r.ax=arithmetic(r.ax,local(-44),true);r.ip=0x6339;break;
        case 0x6339:store(-8,r.ax);r.ip=0x633c;break;
        case 0x633c:les(-58);r.ip=0x633f;break;
        case 0x633f:r.ax=read(2);r.ip=0x6343;break;
        case 0x6343:r.ax=arithmetic(r.ax,local(-46),true);r.ip=0x6346;break;
        case 0x6346:store(-10,r.ax);r.ip=0x6349;break;
        case 0x6349:r.ip=0x6350;break;
        case 0x634b:store(-8,6000);r.ip=0x6350;break;
        case 0x6350:arithmetic(lb(-15),31,true,true);r.ip=0x6354;break;
        case 0x6354:branch(!flag(0x40),0x63be,0x6356);break;
        case 0x6356:les(4);r.ip=0x6359;break;
        case 0x6359:store(-58,r.di);r.ip=0x635c;break;
        case 0x635c:store(-56,r.es);r.ip=0x635f;break;
        case 0x635f:les(-58);r.ip=0x6362;break;
        case 0x6362:wb(2,250);r.ip=0x6367;break;
        case 0x6367:les(-58);r.ip=0x636a;break;
        case 0x636a:r.ax=read(14);r.ip=0x636e;break;
        case 0x636e:r.ax=logic(r.ax&255u);r.ip=0x6371;break;
        case 0x6371:logic(r.ax);r.ip=0x6373;break;
        case 0x6373:branch(flag(1)||flag(0x40),0x63be,0x6375);break;
        case 0x6375:les(-58);r.ip=0x6378;break;
        case 0x6378:r.ax=read(14);r.ip=0x637c;break;
        case 0x637c:r.ax=logic(r.ax&255u);r.ip=0x637f;break;
        case 0x637f:push(r.ax);r.ip=0x6380;break;
        case 0x6380:push(r.bp);r.ip=0x6381;break;
        case 0x6381:nearCall(0x5872,0x6384);break;
        case 0x6384:les(-58);r.ip=0x6387;break;
        case 0x6387:r.ax=read(14);r.ip=0x638b;break;
        case 0x638b:r.ax=shift(r.ax,8,true);r.ip=0x638e;break;
        case 0x638e:logic(r.ax);r.ip=0x6390;break;
        case 0x6390:branch(flag(1)||flag(0x40),0x63be,0x6392);break;
        case 0x6392:les(-58);r.ip=0x6395;break;
        case 0x6395:r.ax=read(14);r.ip=0x6399;break;
        case 0x6399:r.ax=shift(r.ax,8,true);r.ip=0x639c;break;
        case 0x639c:push(r.ax);r.ip=0x639d;break;
        case 0x639d:push(r.bp);r.ip=0x639e;break;
        case 0x639e:nearCall(0x5872,0x63a1);break;
        case 0x63a1:les(-58);r.ip=0x63a4;break;
        case 0x63a4:r.ax=read(16);r.ip=0x63a8;break;
        case 0x63a8:r.ax=logic(r.ax&255u);r.ip=0x63ab;break;
        case 0x63ab:logic(r.ax);r.ip=0x63ad;break;
        case 0x63ad:branch(flag(1)||flag(0x40),0x63be,0x63af);break;
        case 0x63af:les(-58);r.ip=0x63b2;break;
        case 0x63b2:r.ax=read(16);r.ip=0x63b6;break;
        case 0x63b6:r.ax=logic(r.ax&255u);r.ip=0x63b9;break;
        case 0x63b9:push(r.ax);r.ip=0x63ba;break;
        case 0x63ba:push(r.bp);r.ip=0x63bb;break;
        case 0x63bb:nearCall(0x5872,0x63be);break;
        case 0x63be:r.ax=local(-4);r.ip=0x63c1;break;
        case 0x63c1:cwd();r.ip=0x63c2;break;
        case 0x63c2:r.ax=logic(r.ax^r.dx);r.ip=0x63c4;break;
        case 0x63c4:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x63c6;break;
        case 0x63c6:arithmetic(r.ax,10,true);r.ip=0x63c9;break;
        case 0x63c9:branch(less(),0x63ce,0x63cb);break;
        case 0x63cb:r.ip=0x645f;break;
        case 0x63ce:r.ax=local(-6);r.ip=0x63d1;break;
        case 0x63d1:cwd();r.ip=0x63d2;break;
        case 0x63d2:r.ax=logic(r.ax^r.dx);r.ip=0x63d4;break;
        case 0x63d4:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x63d6;break;
        case 0x63d6:arithmetic(r.ax,10,true);r.ip=0x63d9;break;
        case 0x63d9:branch(less(),0x63de,0x63db);break;
        case 0x63db:r.ip=0x645f;break;
        case 0x63de:arithmetic(lb(-15),1,true,true);r.ip=0x63e2;break;
        case 0x63e2:branch(flag(1),0x63ea,0x63e4);break;
        case 0x63e4:arithmetic(lb(-15),8,true,true);r.ip=0x63e8;break;
        case 0x63e8:branch(flag(1)||flag(0x40),0x63f0,0x63ea);break;
        case 0x63ea:arithmetic(lb(-15),29,true,true);r.ip=0x63ee;break;
        case 0x63ee:branch(flag(1)||flag(0x40),0x63f6,0x63f0);break;
        case 0x63f0: { const auto c=r.flags&1u;bus.writeByte(r.ds,0x79e8,static_cast<uint8_t>(arithmetic(data(0x79e8),1,false,true)));r.flags=(r.flags&~uint32_t{1})|c;r.ip=0x63f4;break; }
        case 0x63f4:r.ip=0x645f;break;
        case 0x63f6:arithmetic(data(0x79ae),0,true,true);r.ip=0x63fb;break;
        case 0x63fb:branch(!flag(0x40),0x645f,0x63fd);break;
        case 0x63fd:al(lb(-15));r.ip=0x6400;break;
        case 0x6400:zeroAh();r.ip=0x6402;break;
        case 0x6402:r.ax=arithmetic(r.ax,18,true);r.ip=0x6405;break;
        case 0x6405:bus.writeByte(r.ds,0x79ae,static_cast<uint8_t>(r.ax));r.ip=0x6408;break;
        case 0x6408:les(4);r.ip=0x640b;break;
        case 0x640b:store(-58,r.di);r.ip=0x640e;break;
        case 0x640e:store(-56,r.es);r.ip=0x6411;break;
        case 0x6411:les(-58);r.ip=0x6414;break;
        case 0x6414:wb(21,5);r.ip=0x6419;break;
        case 0x6419:les(-58);r.ip=0x641c;break;
        case 0x641c:wb(0,11);r.ip=0x6420;break;
        case 0x6420:al(data(0x79ae));r.ip=0x6423;break;
        case 0x6423:zeroAh();r.ip=0x6425;break;
        case 0x6425:r.di=r.ax;r.ip=0x6427;break;
        case 0x6427:r.di=shift(r.di,1);r.ip=0x6429;break;
        case 0x6429:al(data(static_cast<uint16_t>(r.di+0x42u)));r.ip=0x642d;break;
        case 0x642d:push(r.ax);r.ip=0x642e;break;
        case 0x642e:push(r.bp);r.ip=0x642f;break;
        case 0x642f:nearCall(0x5a75,0x6432);break;
        case 0x6432:les(-58);r.ip=0x6435;break;
        case 0x6435:wb(2,26);r.ip=0x643a;break;
        case 0x643a:les(-58);r.ip=0x643d;break;
        case 0x643d:wb(27,0);r.ip=0x6442;break;
        case 0x6442:r.ax=logic(0);r.ip=0x6444;break;
        case 0x6444:store(-12,r.ax);r.ip=0x6447;break;
        case 0x6447:push(3);r.ip=0x6449;break;
        case 0x6449:farCall(0x13a8,0x644e);break;
        case 0x644e: { const auto c=r.flags&1u;r.ax=arithmetic(r.ax,1);r.flags=(r.flags&~uint32_t{1})|c;r.ip=0x644f;break; }
        case 0x644f:r.dx=logic(0);r.ip=0x6451;break;
        case 0x6451:r.cx=0xff9c;r.ip=0x6454;break;
        case 0x6454:r.bx=0xffff;r.ip=0x6457;break;
        case 0x6457:farCall(0x92a,0x645c);break;
        case 0x645c:store(-14,r.ax);r.ip=0x645f;break;
        case 0x645f:r.ax=local(-8);r.ip=0x6462;break;
        case 0x6462:cwd();r.ip=0x6463;break;
        case 0x6463:r.ax=logic(r.ax^r.dx);r.ip=0x6465;break;
        case 0x6465:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x6467;break;
        case 0x6467:arithmetic(r.ax,10,true);r.ip=0x646a;break;
        case 0x646a:branch(less(),0x646f,0x646c);break;
        case 0x646c:r.ip=0x6500;break;
        case 0x646f:r.ax=local(-10);r.ip=0x6472;break;
        case 0x6472:cwd();r.ip=0x6473;break;
        case 0x6473:r.ax=logic(r.ax^r.dx);r.ip=0x6475;break;
        case 0x6475:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x6477;break;
        case 0x6477:arithmetic(r.ax,10,true);r.ip=0x647a;break;
        case 0x647a:branch(less(),0x647f,0x647c);break;
        case 0x647c:r.ip=0x6500;break;
        case 0x647f:arithmetic(lb(-15),1,true,true);r.ip=0x6483;break;
        case 0x6483:branch(flag(1),0x648b,0x6485);break;
        case 0x6485:arithmetic(lb(-15),8,true,true);r.ip=0x6489;break;
        case 0x6489:branch(flag(1)||flag(0x40),0x6491,0x648b);break;
        case 0x648b:arithmetic(lb(-15),29,true,true);r.ip=0x648f;break;
        case 0x648f:branch(flag(1)||flag(0x40),0x6497,0x6491);break;
        case 0x6491: { const auto c=r.flags&1u;bus.writeByte(r.ds,0x79e9,static_cast<uint8_t>(arithmetic(data(0x79e9),1,false,true)));r.flags=(r.flags&~uint32_t{1})|c;r.ip=0x6495;break; }
        case 0x6495:r.ip=0x6500;break;
        case 0x6497:arithmetic(data(0x79af),0,true,true);r.ip=0x649c;break;
        case 0x649c:branch(!flag(0x40),0x6500,0x649e);break;
        case 0x649e:al(lb(-15));r.ip=0x64a1;break;
        case 0x64a1:zeroAh();r.ip=0x64a3;break;
        case 0x64a3:r.ax=arithmetic(r.ax,18,true);r.ip=0x64a6;break;
        case 0x64a6:bus.writeByte(r.ds,0x79af,static_cast<uint8_t>(r.ax));r.ip=0x64a9;break;
        case 0x64a9:les(4);r.ip=0x64ac;break;
        case 0x64ac:store(-58,r.di);r.ip=0x64af;break;
        case 0x64af:store(-56,r.es);r.ip=0x64b2;break;
        case 0x64b2:les(-58);r.ip=0x64b5;break;
        case 0x64b5:wb(21,5);r.ip=0x64ba;break;
        case 0x64ba:les(-58);r.ip=0x64bd;break;
        case 0x64bd:wb(0,11);r.ip=0x64c1;break;
        case 0x64c1:al(data(0x79af));r.ip=0x64c4;break;
        case 0x64c4:zeroAh();r.ip=0x64c6;break;
        case 0x64c6:r.di=r.ax;r.ip=0x64c8;break;
        case 0x64c8:r.di=shift(r.di,1);r.ip=0x64ca;break;
        case 0x64ca:al(data(static_cast<uint16_t>(r.di+0x42u)));r.ip=0x64ce;break;
        case 0x64ce:push(r.ax);r.ip=0x64cf;break;
        case 0x64cf:push(r.bp);r.ip=0x64d0;break;
        case 0x64d0:nearCall(0x5a75,0x64d3);break;
        case 0x64d3:les(-58);r.ip=0x64d6;break;
        case 0x64d6:wb(2,26);r.ip=0x64db;break;
        case 0x64db:les(-58);r.ip=0x64de;break;
        case 0x64de:wb(27,0);r.ip=0x64e3;break;
        case 0x64e3:r.ax=logic(0);r.ip=0x64e5;break;
        case 0x64e5:store(-12,r.ax);r.ip=0x64e8;break;
        case 0x64e8:push(3);r.ip=0x64ea;break;
        case 0x64ea:farCall(0x13a8,0x64ef);break;
        case 0x64ef: { const auto c=r.flags&1u;r.ax=arithmetic(r.ax,1);r.flags=(r.flags&~uint32_t{1})|c;r.ip=0x64f0;break; }
        case 0x64f0:r.dx=logic(0);r.ip=0x64f2;break;
        case 0x64f2:r.cx=0xff9c;r.ip=0x64f5;break;
        case 0x64f5:r.bx=0xffff;r.ip=0x64f8;break;
        case 0x64f8:farCall(0x92a,0x64fd);break;
        case 0x64fd:store(-14,r.ax);r.ip=0x6500;break;
        case 0x6500:r.ax=local(-10);r.ip=0x6503;break;
        case 0x6503:cwd();r.ip=0x6504;break;
        case 0x6504:r.ax=logic(r.ax^r.dx);r.ip=0x6506;break;
        case 0x6506:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x6508;break;
        case 0x6508:cwd();r.ip=0x6509;break;
        case 0x6509:r.cx=r.ax;r.ip=0x650b;break;
        case 0x650b:r.bx=r.dx;r.ip=0x650d;break;
        case 0x650d:r.ax=local(-8);r.ip=0x6510;break;
        case 0x6510:cwd();r.ip=0x6511;break;
        case 0x6511:r.ax=logic(r.ax^r.dx);r.ip=0x6513;break;
        case 0x6513:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x6515;break;
        case 0x6515:cwd();r.ip=0x6516;break;
        case 0x6516:r.ax=arithmetic(r.ax,r.cx);r.ip=0x6518;break;
        case 0x6518:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x651a;break;
        case 0x651a:push(r.dx);r.ip=0x651b;break;
        case 0x651b:push(r.ax);r.ip=0x651c;break;
        case 0x651c:r.ax=local(-6);r.ip=0x651f;break;
        case 0x651f:cwd();r.ip=0x6520;break;
        case 0x6520:r.ax=logic(r.ax^r.dx);r.ip=0x6522;break;
        case 0x6522:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x6524;break;
        case 0x6524:cwd();r.ip=0x6525;break;
        case 0x6525:r.cx=r.ax;r.ip=0x6527;break;
        case 0x6527:r.bx=r.dx;r.ip=0x6529;break;
        case 0x6529:r.ax=local(-4);r.ip=0x652c;break;
        case 0x652c:cwd();r.ip=0x652d;break;
        case 0x652d:r.ax=logic(r.ax^r.dx);r.ip=0x652f;break;
        case 0x652f:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x6531;break;
        case 0x6531:cwd();r.ip=0x6532;break;
        case 0x6532:r.ax=arithmetic(r.ax,r.cx);r.ip=0x6534;break;
        case 0x6534:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x6536;break;
        case 0x6536:r.cx=pop();r.ip=0x6537;break;
        case 0x6537:r.bx=pop();r.ip=0x6538;break;
        case 0x6538:arithmetic(r.dx,r.bx,true);r.ip=0x653a;break;
        case 0x653a:branch(!flag(0x40)&&!less(),0x6542,0x653c);break;
        case 0x653c:branch(less(),0x654e,0x653e);break;
        case 0x653e:arithmetic(r.ax,r.cx,true);r.ip=0x6540;break;
        case 0x6540:branch(flag(1)||flag(0x40),0x654e,0x6542);break;
        case 0x6542:r.ax=local(-8);r.ip=0x6545;break;
        case 0x6545:store(-4,r.ax);r.ip=0x6548;break;
        case 0x6548:r.ax=local(-10);r.ip=0x654b;break;
        case 0x654b:store(-6,r.ax);r.ip=0x654e;break;

        case 0x5872:push(r.bp);r.ip=0x5873;break;
        case 0x5873:r.bp=r.sp;r.ip=0x5875;break;
        case 0x5875:r.ax=6;r.ip=0x5878;break;
        case 0x5878:farCall(0x4df,0x587d);break;
        case 0x587d:r.sp=arithmetic(r.sp,6,true);r.ip=0x5880;break;
        case 0x5880:store(-2,1);r.ip=0x5885;break;
        case 0x5885:arithmetic(lb(6),128,true,true);r.ip=0x5889;break;
        case 0x5889:branch(flag(1)||flag(0x40),0x5894,0x588b);break;
        case 0x588b:sb(6,static_cast<uint8_t>(arithmetic(lb(6),128,true,true)));r.ip=0x588f;break;
        case 0x588f:store(-2,65535);r.ip=0x5894;break;
        case 0x5894:al(lb(6));r.ip=0x5897;break;
        case 0x5897:zeroAh();r.ip=0x5899;break;
        case 0x5899:r.di=r.ax;r.ip=0x589b;break;
        case 0x589b:r.di=shift(r.di,4);r.ip=0x589e;break;
        case 0x589e:r.di=arithmetic(r.di,0x79ea);r.ip=0x58a2;break;
        case 0x58a2:store(-6,r.di);r.ip=0x58a5;break;
        case 0x58a5:store(-4,r.ds);r.ip=0x58a8;break;
        case 0x58a8:les(-6);r.ip=0x58ab;break;
        case 0x58ab:arithmetic(byte(3),255,true,true);r.ip=0x58b0;break;
        case 0x58b0:branch(!flag(0x40),0x58b5,0x58b2);break;
        case 0x58b2:r.ip=0x5967;break;
        case 0x58b5:les(-6);r.ip=0x58b8;break;
        case 0x58b8:r.ax=read(11);r.ip=0x58bc;break;
        case 0x58bc:multiply(local(-2));r.ip=0x58bf;break;
        case 0x58bf:r.di=local(4);r.ip=0x58c2;break;
        case 0x58c2:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-12u),arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u)),r.ax));r.ip=0x58c6;break;
        case 0x58c6:les(-6);r.ip=0x58c9;break;
        case 0x58c9:r.ax=read(13);r.ip=0x58cd;break;
        case 0x58cd:multiply(local(-2));r.ip=0x58d0;break;
        case 0x58d0:r.di=local(4);r.ip=0x58d3;break;
        case 0x58d3:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-14u),arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-14u)),r.ax));r.ip=0x58d7;break;
        case 0x58d7:les(-6);r.ip=0x58da;break;
        case 0x58da:al(byte(3));r.ip=0x58de;break;
        case 0x58de:zeroAh();r.ip=0x58e0;break;
        case 0x58e0:r.cx=r.ax;r.ip=0x58e2;break;
        case 0x58e2:r.di=local(4);r.ip=0x58e5;break;
        case 0x58e5:r.ax=bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u));r.ip=0x58e9;break;
        case 0x58e9:cwd();r.ip=0x58ea;break;
        case 0x58ea:r.ax=logic(r.ax^r.dx);r.ip=0x58ec;break;
        case 0x58ec:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x58ee;break;
        case 0x58ee:arithmetic(r.ax,r.cx,true);r.ip=0x58f0;break;
        case 0x58f0:branch(flag(0x40)||less(),0x591e,0x58f2);break;
        case 0x58f2:r.di=local(4);r.ip=0x58f5;break;
        case 0x58f5:arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u)),0,true);r.ip=0x58fa;break;
        case 0x58fa:branch(flag(0x40)||less(),0x590e,0x58fc);break;
        case 0x58fc:les(-6);r.ip=0x58ff;break;
        case 0x58ff:al(byte(3));r.ip=0x5903;break;
        case 0x5903:zeroAh();r.ip=0x5905;break;
        case 0x5905:r.di=local(4);r.ip=0x5908;break;
        case 0x5908:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-12u),arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u)),r.ax,true));r.ip=0x590c;break;
        case 0x590c:r.ip=0x591e;break;
        case 0x590e:les(-6);r.ip=0x5911;break;
        case 0x5911:al(byte(3));r.ip=0x5915;break;
        case 0x5915:zeroAh();r.ip=0x5917;break;
        case 0x5917:r.di=local(4);r.ip=0x591a;break;
        case 0x591a:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-12u),arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u)),r.ax));r.ip=0x591e;break;
        case 0x591e:les(-6);r.ip=0x5921;break;
        case 0x5921:al(byte(3));r.ip=0x5925;break;
        case 0x5925:zeroAh();r.ip=0x5927;break;
        case 0x5927:r.cx=r.ax;r.ip=0x5929;break;
        case 0x5929:r.di=local(4);r.ip=0x592c;break;
        case 0x592c:r.ax=bus.readWord(r.ss,static_cast<uint16_t>(r.di-14u));r.ip=0x5930;break;
        case 0x5930:cwd();r.ip=0x5931;break;
        case 0x5931:r.ax=logic(r.ax^r.dx);r.ip=0x5933;break;
        case 0x5933:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x5935;break;
        case 0x5935:arithmetic(r.ax,r.cx,true);r.ip=0x5937;break;
        case 0x5937:branch(flag(0x40)||less(),0x5965,0x5939);break;
        case 0x5939:r.di=local(4);r.ip=0x593c;break;
        case 0x593c:arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-14u)),0,true);r.ip=0x5941;break;
        case 0x5941:branch(flag(0x40)||less(),0x5955,0x5943);break;
        case 0x5943:les(-6);r.ip=0x5946;break;
        case 0x5946:al(byte(3));r.ip=0x594a;break;
        case 0x594a:zeroAh();r.ip=0x594c;break;
        case 0x594c:r.di=local(4);r.ip=0x594f;break;
        case 0x594f:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-14u),arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-14u)),r.ax,true));r.ip=0x5953;break;
        case 0x5953:r.ip=0x5965;break;
        case 0x5955:les(-6);r.ip=0x5958;break;
        case 0x5958:al(byte(3));r.ip=0x595c;break;
        case 0x595c:zeroAh();r.ip=0x595e;break;
        case 0x595e:r.di=local(4);r.ip=0x5961;break;
        case 0x5961:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-14u),arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-14u)),r.ax));r.ip=0x5965;break;
        case 0x5965:r.ip=0x5995;break;
        case 0x5967:les(-6);r.ip=0x596a;break;
        case 0x596a:r.ax=read(11);r.ip=0x596e;break;
        case 0x596e:r.di=local(4);r.ip=0x5971;break;
        case 0x5971:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-44u),r.ax);r.ip=0x5975;break;
        case 0x5975:les(-6);r.ip=0x5978;break;
        case 0x5978:r.ax=read(13);r.ip=0x597c;break;
        case 0x597c:r.di=local(4);r.ip=0x597f;break;
        case 0x597f:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-46u),r.ax);r.ip=0x5983;break;
        case 0x5983:r.di=local(4);r.ip=0x5986;break;
        case 0x5986:r.ax=logic(0);r.ip=0x5988;break;
        case 0x5988:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-12u),r.ax);r.ip=0x598c;break;
        case 0x598c:r.di=local(4);r.ip=0x598f;break;
        case 0x598f:r.ax=logic(0);r.ip=0x5991;break;
        case 0x5991:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-14u),r.ax);r.ip=0x5995;break;
        case 0x5995:case 0x5af9:r.sp=r.bp;r.bp=pop();r.ip=static_cast<uint16_t>(r.ip+1u);break;
        case 0x5996:case 0x5afa:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);break;

        case 0x5a75:push(r.bp);r.ip=0x5a76;break;
        case 0x5a76:r.bp=r.sp;r.ip=0x5a78;break;
        case 0x5a78:r.ax=4;r.ip=0x5a7b;break;
        case 0x5a7b:farCall(0x4df,0x5a80);break;
        case 0x5a80:r.sp=arithmetic(r.sp,4,true);r.ip=0x5a83;break;
        case 0x5a83:r.di=local(4);r.ip=0x5a86;break;
        case 0x5a86: { const auto at=static_cast<uint16_t>(r.di+4u);r.di=bus.readWord(r.ss,at);r.es=bus.readWord(r.ss,static_cast<uint16_t>(at+2u));r.ip=0x5a8a;break; }
        case 0x5a8a:al(byte(1));r.ip=0x5a8e;break;
        case 0x5a8e:zeroAh();r.ip=0x5a90;break;
        case 0x5a90:r.di=r.ax;r.ip=0x5a92;break;
        case 0x5a92:r.di=shift(r.di,3);r.ip=0x5a95;break;
        case 0x5a95:r.di=arithmetic(r.di,0xc21e);r.ip=0x5a99;break;
        case 0x5a99:store(-4,r.di);r.ip=0x5a9c;break;
        case 0x5a9c:store(-2,r.ds);r.ip=0x5a9f;break;
        case 0x5a9f:al(lb(6));r.ip=0x5aa2;break;
        case 0x5aa2:zeroAh();r.ip=0x5aa4;break;
        case 0x5aa4:r.di=r.ax;r.ip=0x5aa6;break;
        case 0x5aa6:r.di=shift(r.di,2);r.ip=0x5aa9;break;
        case 0x5aa9:r.ax=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0xc324u));r.ip=0x5aad;break;
        case 0x5aad:les(-4);r.ip=0x5ab0;break;
        case 0x5ab0:write(6,r.ax);r.ip=0x5ab4;break;
        case 0x5ab4:al(lb(6));r.ip=0x5ab7;break;
        case 0x5ab7:zeroAh();r.ip=0x5ab9;break;
        case 0x5ab9:r.di=r.ax;r.ip=0x5abb;break;
        case 0x5abb:r.di=shift(r.di,2);r.ip=0x5abe;break;
        case 0x5abe:al(data(static_cast<uint16_t>(r.di+0xc322u)));r.ip=0x5ac2;break;
        case 0x5ac2:les(-4);r.ip=0x5ac5;break;
        case 0x5ac5:wb(4,static_cast<uint8_t>(r.ax));r.ip=0x5ac9;break;
        case 0x5ac9:al(lb(6));r.ip=0x5acc;break;
        case 0x5acc:zeroAh();r.ip=0x5ace;break;
        case 0x5ace:r.di=r.ax;r.ip=0x5ad0;break;
        case 0x5ad0:r.di=shift(r.di,2);r.ip=0x5ad3;break;
        case 0x5ad3:al(data(static_cast<uint16_t>(r.di+0xc323u)));r.ip=0x5ad7;break;
        case 0x5ad7:les(-4);r.ip=0x5ada;break;
        case 0x5ada:wb(5,static_cast<uint8_t>(r.ax));r.ip=0x5ade;break;
        case 0x5ade:les(-4);r.ip=0x5ae1;break;
        case 0x5ae1:al(byte(5));r.ip=0x5ae5;break;
        case 0x5ae5:zeroAh();r.ip=0x5ae7;break;
        case 0x5ae7:r.dx=r.ax;r.ip=0x5ae9;break;
        case 0x5ae9:r.ax=16;r.ip=0x5aec;break;
        case 0x5aec:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x5aee;break;
        case 0x5aee:r.di=local(4);r.ip=0x5af1;break;
        case 0x5af1: { const auto at=static_cast<uint16_t>(r.di+4u);r.di=bus.readWord(r.ss,at);r.es=bus.readWord(r.ss,static_cast<uint16_t>(at+2u));r.ip=0x5af5;break; }
        case 0x5af5:wb(20,static_cast<uint8_t>(r.ax));r.ip=0x5af9;break;
        default:throw std::domain_error("Actor precontact reached an unrecovered instruction");
        }
    }
};

enum class FrameActorPrecontactOutcome { Running, BehaviorDispatch, TransientQueues, Restart, EndRunUi, RuntimeError, BreakOutput };
using FrameActorPrecontactCallee=std::variant<FrameActorEntrySnapshot,ActorPrecontactSnapshot>;
struct FrameActorPrecontactSnapshot {
    FrameActorPrecontactCallee callee;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    uint64_t dispatchedInstructions=0;
    uint64_t entryTimerInstructions=0,entryTimerDeliveries=0;
    FrameActorPrecontactOutcome outcome=FrameActorPrecontactOutcome::Running;
    bool operator==(const FrameActorPrecontactSnapshot&) const = default;
};

class FrameActorPrecontactOperation {
public:
    using CopyBudget=FrameActorEntryOperation::CopyBudget;
    FrameActorPrecontactOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r.ip==0x615a ? FrameActorPrecontactCallee{ActorPrecontactOperation(r,game,idToggle).snapshot()} :
            r.ip==0x6053 ? FrameActorPrecontactCallee{FrameActorEntrySnapshot{ActorAnimationOperation(r,game).snapshot(),game,idToggle}} :
            FrameActorPrecontactCallee{FrameActorEntryOperation(r,game,idToggle).snapshot()},game,idToggle} { validate(); }
    FrameActorPrecontactOperation(DosGetTimeRegisters r,uint16_t dos,uint16_t keyboard,uint16_t psp,
                                 uint16_t game,uint32_t idToggle)
        : state_{FrameActorEntryOperation(r,dos,keyboard,psp,game,idToggle).snapshot(),game,idToggle} { validate(); }
    explicit FrameActorPrecontactOperation(FrameActorPrecontactSnapshot state) : state_(state) { validate(); }
    const FrameActorPrecontactSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) -> DosGetTimeRegisters {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) return FrameActorEntryOperation(child).registers();
            else return ActorPrecontactOperation(child).registers();
        },state_.callee);
    }
    bool finished() const noexcept { return state_.outcome!=FrameActorPrecontactOutcome::Running; }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) return FrameActorEntryOperation(child).interruptInProgress();
            else return ActorPrecontactOperation(child).interruptInProgress();
        },state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished actor precontact admitted IRQ");
        std::visit([&](auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) {
                FrameActorEntryOperation operation(child);operation.deliverTimerInterrupt(bus);child=operation.snapshot();
            } else {
                ActorPrecontactOperation operation(child);operation.deliverTimerInterrupt(bus);child=operation.snapshot();
            }
        },state_.callee);
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            std::optional<DosGetTimeRegisters> next;
            std::visit([&](auto& child) {
                using Child=std::remove_cvref_t<decltype(child)>;
                if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) {
                    FrameActorEntryOperation operation(child);
                    if (operation.advance(1,bus,copies)!=1) throw std::domain_error("Frame actor entry did not dispatch");
                    child=operation.snapshot();
                    state_.entryTimerInstructions=child.prefixTimerInstructions+child.tailTimerInstructions;
                    state_.entryTimerDeliveries=child.prefixTimerDeliveries+child.tailTimerDeliveries;
                    if (operation.finished()) {
                        switch (child.outcome) {
                        case FrameActorEntryOutcome::ActorBody:next=operation.registers();break;
                        case FrameActorEntryOutcome::TransientQueues:state_.outcome=FrameActorPrecontactOutcome::TransientQueues;break;
                        case FrameActorEntryOutcome::Restart:state_.outcome=FrameActorPrecontactOutcome::Restart;break;
                        case FrameActorEntryOutcome::EndRunUi:state_.outcome=FrameActorPrecontactOutcome::EndRunUi;break;
                        case FrameActorEntryOutcome::RuntimeError:state_.outcome=FrameActorPrecontactOutcome::RuntimeError;break;
                        case FrameActorEntryOutcome::BreakOutput:state_.outcome=FrameActorPrecontactOutcome::BreakOutput;break;
                        default:throw std::logic_error("Finished actor entry has no outcome");
                        }
                    }
                } else {
                    ActorPrecontactOperation operation(child);
                    if (operation.advance(1,bus)!=1) throw std::domain_error("Actor precontact did not dispatch");
                    child=operation.snapshot();
                    if (operation.finished()) state_.outcome=child.outcome==ActorPrecontactOutcome::BehaviorDispatch ?
                        FrameActorPrecontactOutcome::BehaviorDispatch : FrameActorPrecontactOutcome::RuntimeError;
                }
            },state_.callee);
            if (next) state_.callee=ActorPrecontactOperation(*next,state_.gameSegment,state_.idToggleMask).snapshot();
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    FrameActorPrecontactSnapshot state_;
    void validate() const {
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            !std::visit([&](const auto& child) { return child.gameSegment==state_.gameSegment && child.idToggleMask==state_.idToggleMask; },state_.callee))
            throw std::invalid_argument("Frame actor precontact ID-toggle/callee ownership differs");
    }
};

} // namespace lezac::core
