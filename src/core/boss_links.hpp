#pragma once

#include "core/frame_display.hpp"

#include <bit>
#include <stdexcept>

namespace lezac::core {

enum class BossLinksOutcome { Running, Returned, RuntimeError };
struct BossLinksSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint64_t dispatchedInstructions=0;
    BossLinksOutcome outcome=BossLinksOutcome::Running;
    bool operator==(const BossLinksSnapshot&) const = default;
};

// Complete 432A..4529 link loop, including spring LongInt multiply and orbit
// software Real48 calls. The table is original caller-owned memory, not host sin.
class BossLinksOperation {
public:
    BossLinksOperation(DosGetTimeRegisters registers,uint16_t game) : state_{registers,game} {
        if (registers.cs!=game || registers.ds!=static_cast<uint16_t>(game+0xaa2) || registers.ip!=0x432a)
            throw std::invalid_argument("Boss links entry differs");
    }
    explicit BossLinksOperation(BossLinksSnapshot state) : state_(state) {}
    const BossLinksSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome!=BossLinksOutcome::Running; }
    bool returned() const noexcept { return state_.outcome==BossLinksOutcome::Returned; }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            instruction(bus);++used;++state_.dispatchedInstructions;
            const auto& r=state_.registers;
            if (r.cs==state_.gameSegment && r.ip==0x7ec5) state_.outcome=BossLinksOutcome::Returned;
            if (r.cs==library() && r.ip==0xe2) state_.outcome=BossLinksOutcome::RuntimeError;
        }
        return used;
    }

private:
    BossLinksSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u) | (value&(byte ? 0x80u : 0x8000u) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value,bool byte=false) {
        value=static_cast<uint16_t>(value&(byte ? 255u : 65535u));
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value,byte);
        return value;
    }
    uint16_t arithmetic(uint16_t left,uint16_t right,bool subtract=false,bool byte=false,bool carry=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u;
        const uint32_t extra=carry && flag(1) ? 1u : 0u;
        const uint32_t wide=subtract ? uint32_t{left}-right-extra : uint32_t{left}+right+extra;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t flags=valueFlags(value,byte)|((left^right^value)&16u);
        if (subtract ? uint32_t{left}<uint32_t{right}+extra : wide>mask) flags|=1;
        if (subtract ? ((left^right)&(left^value)&sign) : (~(left^right)&(left^value)&sign)) flags|=0x800;
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|flags;
        return value;
    }
    uint16_t shift(uint16_t value,unsigned count) {
        const auto original=value;
        unsigned carry=0;
        for (unsigned i=0;i<count;++i) { carry=value>>15;value=static_cast<uint16_t>(value<<1); }
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value)|16u|carry|
            ((value^original)&0x8000u ? 0x800u : 0u);
        return value;
    }
    void multiply(uint16_t factor) {
        auto& r=state_.registers;
        const uint32_t product=uint32_t{r.ax}*factor;
        r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
        r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto store=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto les=[&](int offset) { r.di=local(offset);r.es=local(offset+2); };
        const auto al=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|value); };
        const auto zeroAh=[&] { r.ax&=255u;r.flags=(r.flags&~uint32_t{0x8d5})|0x44u; };
        const auto cwd=[&] { r.dx=(r.ax&0x8000) ? 0xffff : 0; };
        const auto read=[&](unsigned offset) { return bus.readWord(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto byte=[&](unsigned offset) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto write=[&](unsigned offset,uint16_t value) { bus.writeWord(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto farCall=[&](uint16_t ip,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=ip; };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        if (r.cs==library()) {
            switch (r.ip) {
            case 0x4df:r.ax=arithmetic(r.ax,0x200);r.ip=0x4e2;break;
            case 0x4e2:branch(flag(1),0x4f1,0x4e4);break;
            case 0x4e4:r.ax=arithmetic(r.ax,r.sp,true);r.ip=0x4e6;break;
            case 0x4e6:branch(!flag(1),0x4f1,0x4e8);break;
            case 0x4e8:r.ax=arithmetic(0,r.ax,true);r.ip=0x4ea;break;
            case 0x4ea:arithmetic(r.ax,bus.readWord(r.ds,0x1afa),true);r.ip=0x4ee;break;
            case 0x4ee:branch(flag(1),0x4f1,0x4f0);break;
            case 0x4f0:case 0x944:r.ip=pop();r.cs=pop();break;
            case 0x4f1:r.ax=0xca;r.ip=0x4f4;break;
            case 0x4f4:r.ip=0xe2;break;
            case 0x92a:r.si=r.ax;r.ip=0x92c;break;
            case 0x92c:r.di=r.dx;r.ip=0x92e;break;
            case 0x92e:multiply(r.cx);r.ip=0x930;break;
            case 0x930:push(r.ax);r.ip=0x931;break;
            case 0x931:push(r.dx);r.ip=0x932;break;
            case 0x932:r.ax=r.si;r.ip=0x934;break;
            case 0x934:multiply(r.bx);r.ip=0x936;break;
            case 0x936:r.bx=r.ax;r.ip=0x938;break;
            case 0x938:r.ax=r.di;r.ip=0x93a;break;
            case 0x93a:multiply(r.cx);r.ip=0x93c;break;
            case 0x93c:r.cx=r.ax;r.ip=0x93e;break;
            case 0x93e:r.dx=pop();r.ip=0x93f;break;
            case 0x93f:r.ax=pop();r.ip=0x940;break;
            case 0x940:r.dx=arithmetic(r.dx,r.bx);r.ip=0x942;break;
            case 0x942:r.dx=arithmetic(r.dx,r.cx);r.ip=0x944;break;
            default: {
                // Reuse the already recovered RTL instructions, never its game caller.
                FrameDisplayOperation runtime(FrameDisplaySnapshot{r,state_.gameSegment});
                runtime.advance(1,bus);r=runtime.snapshot().registers;break;
            }
            }
            return;
        }
        if (r.cs!=state_.gameSegment) throw std::domain_error("Boss links left recovered code");
        switch (r.ip) {
        case 0x432a:push(r.bp);r.ip=0x432b;break;
        case 0x432b:r.bp=r.sp;r.ip=0x432d;break;
        case 0x432d:r.ax=0xc;r.ip=0x4330;break;
        case 0x4330:farCall(0x4df,0x4335);break;
        case 0x4335:r.sp=arithmetic(r.sp,0xc,true);r.ip=0x4338;break;
        case 0x4338:al(bus.readByte(r.ds,0x79f9));r.ip=0x433b;break;
        case 0x433b:zeroAh();r.ip=0x433d;break;
        case 0x433d:store(-4,r.ax);r.ip=0x4340;break;
        case 0x4340:r.ax=1;r.ip=0x4343;break;
        case 0x4343:arithmetic(r.ax,local(-4),true);r.ip=0x4346;break;
        case 0x4346:branch(flag(0x40)||(flag(0x80)!=flag(0x800)),0x434b,0x4348);break;
        case 0x4348:r.ip=0x4528;break;
        case 0x434b:store(-2,r.ax);r.ip=0x434e;break;
        case 0x434e:r.ip=0x4353;break;
        case 0x4350: { const auto carry=r.flags&1u;store(-2,arithmetic(local(-2),1));r.flags=(r.flags&~uint32_t{1})|carry;r.ip=0x4353;break; }
        case 0x4353:r.di=local(-2);r.ip=0x4356;break;
        case 0x4356:r.di=shift(r.di,4);r.ip=0x4359;break;
        case 0x4359:r.di=arithmetic(r.di,0x79ea);r.ip=0x435d;break;
        case 0x435d:store(-8,r.di);r.ip=0x4360;break;
        case 0x4360:store(-6,r.ds);r.ip=0x4363;break;
        case 0x4363:les(-8);r.ip=0x4366;break;
        case 0x4366:al(byte(0));r.ip=0x4369;break;
        case 0x4369:zeroAh();r.ip=0x436b;break;
        case 0x436b:r.di=r.ax;r.ip=0x436d;break;
        case 0x436d:r.di=shift(r.di,3);r.ip=0x4370;break;
        case 0x4370:r.di=arithmetic(r.di,0xc21e);r.ip=0x4374;break;
        case 0x4374:store(-12,r.di);r.ip=0x4377;break;
        case 0x4377:store(-10,r.ds);r.ip=0x437a;break;
        case 0x437a:les(-8);r.ip=0x437d;break;
        case 0x437d:arithmetic(byte(3),255,true,true);r.ip=0x4382;break;
        case 0x4382:branch(!flag(0x40),0x4387,0x4384);break;
        case 0x4384:r.ip=0x442a;break;
        case 0x4387:les(-8);r.ip=0x438a;break;
        case 0x438a:r.ax=read(7);r.ip=0x438e;break;
        case 0x438e:cwd();r.ip=0x438f;break;
        case 0x438f:r.cx=r.ax;r.ip=0x4391;break;
        case 0x4391:r.bx=r.dx;r.ip=0x4393;break;
        case 0x4393:les(-8);r.ip=0x4396;break;
        case 0x4396:al(byte(1));r.ip=0x439a;break;
        case 0x439a:zeroAh();r.ip=0x439c;break;
        case 0x439c:r.di=r.ax;r.ip=0x439e;break;
        case 0x439e:r.di=shift(r.di,3);r.ip=0x43a1;break;
        case 0x43a1:r.dx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0xc21eu));r.ip=0x43a5;break;
        case 0x43a5:les(-12);r.ip=0x43a8;break;
        case 0x43a8:r.ax=read(0);r.ip=0x43ab;break;
        case 0x43ab:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x43ad;break;
        case 0x43ad:r.dx=logic(0);r.ip=0x43af;break;
        case 0x43af:r.ax=arithmetic(r.ax,r.cx);r.ip=0x43b1;break;
        case 0x43b1:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x43b3;break;
        case 0x43b3:r.cx=r.ax;r.ip=0x43b5;break;
        case 0x43b5:r.bx=r.dx;r.ip=0x43b7;break;
        case 0x43b7:les(-8);r.ip=0x43ba;break;
        case 0x43ba:al(byte(2));r.ip=0x43be;break;
        case 0x43be:zeroAh();r.ip=0x43c0;break;
        case 0x43c0:r.dx=logic(0);r.ip=0x43c2;break;
        case 0x43c2:farCall(0x92a,0x43c7);break;
        case 0x43c7:les(-8);r.ip=0x43ca;break;
        case 0x43ca:write(11,r.ax);r.ip=0x43ce;break;
        case 0x43ce:les(-8);r.ip=0x43d1;break;
        case 0x43d1:r.ax=read(9);r.ip=0x43d5;break;
        case 0x43d5:cwd();r.ip=0x43d6;break;
        case 0x43d6:r.cx=r.ax;r.ip=0x43d8;break;
        case 0x43d8:r.bx=r.dx;r.ip=0x43da;break;
        case 0x43da:les(-8);r.ip=0x43dd;break;
        case 0x43dd:al(byte(1));r.ip=0x43e1;break;
        case 0x43e1:zeroAh();r.ip=0x43e3;break;
        case 0x43e3:r.di=r.ax;r.ip=0x43e5;break;
        case 0x43e5:r.di=shift(r.di,3);r.ip=0x43e8;break;
        case 0x43e8:r.dx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0xc220u));r.ip=0x43ec;break;
        case 0x43ec:les(-12);r.ip=0x43ef;break;
        case 0x43ef:r.ax=read(2);r.ip=0x43f3;break;
        case 0x43f3:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x43f5;break;
        case 0x43f5:r.dx=logic(0);r.ip=0x43f7;break;
        case 0x43f7:r.ax=arithmetic(r.ax,r.cx);r.ip=0x43f9;break;
        case 0x43f9:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x43fb;break;
        case 0x43fb:r.cx=r.ax;r.ip=0x43fd;break;
        case 0x43fd:r.bx=r.dx;r.ip=0x43ff;break;
        case 0x43ff:les(-8);r.ip=0x4402;break;
        case 0x4402:al(byte(2));r.ip=0x4406;break;
        case 0x4406:zeroAh();r.ip=0x4408;break;
        case 0x4408:r.dx=logic(0);r.ip=0x440a;break;
        case 0x440a:farCall(0x92a,0x440f);break;
        case 0x440f:r.cx=r.ax;r.ip=0x4411;break;
        case 0x4411:r.bx=r.dx;r.ip=0x4413;break;
        case 0x4413:les(-8);r.ip=0x4416;break;
        case 0x4416:al(byte(15));r.ip=0x441a;break;
        case 0x441a:r.ax=static_cast<uint16_t>(static_cast<int16_t>(std::bit_cast<int8_t>(static_cast<uint8_t>(r.ax))));r.ip=0x441b;break;
        case 0x441b:cwd();r.ip=0x441c;break;
        case 0x441c:r.ax=arithmetic(r.ax,r.cx);r.ip=0x441e;break;
        case 0x441e:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x4420;break;
        case 0x4420:les(-8);r.ip=0x4423;break;
        case 0x4423:write(13,r.ax);r.ip=0x4427;break;
        case 0x4427:r.ip=0x451d;break;
        case 0x442a:les(-8);r.ip=0x442d;break;
        case 0x442d:al(byte(2));r.ip=0x4431;break;
        case 0x4431:zeroAh();r.ip=0x4433;break;
        case 0x4433:r.dx=r.ax;r.ip=0x4435;break;
        case 0x4435:les(-8);r.ip=0x4438;break;
        case 0x4438:al(byte(6));r.ip=0x443c;break;
        case 0x443c:zeroAh();r.ip=0x443e;break;
        case 0x443e:r.ax=arithmetic(r.ax,r.dx);r.ip=0x4440;break;
        case 0x4440:r.ax=logic(r.ax&127u);r.ip=0x4443;break;
        case 0x4443:les(-8);r.ip=0x4446;break;
        case 0x4446:bus.writeByte(r.es,static_cast<uint16_t>(r.di+6u),static_cast<uint8_t>(r.ax));r.ip=0x444a;break;
        case 0x444a:les(-8);r.ip=0x444d;break;
        case 0x444d:al(byte(6));r.ip=0x4451;break;
        case 0x4451:zeroAh();r.ip=0x4453;break;
        case 0x4453:r.ax=arithmetic(r.ax,32);r.ip=0x4456;break;
        case 0x4456:r.ax=logic(r.ax&127u);r.ip=0x4459;break;
        case 0x4459:r.di=r.ax;r.ip=0x445b;break;
        case 0x445b:r.di=shift(r.di,1);r.ip=0x445d;break;
        case 0x445d:r.si=r.di;r.ip=0x445f;break;
        case 0x445f:r.di=shift(r.di,1);r.ip=0x4461;break;
        case 0x4461:r.di=arithmetic(r.di,r.si);r.ip=0x4463;break;
        case 0x4463:r.ax=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x7bdau));r.ip=0x4467;break;
        case 0x4467:r.bx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x7bdcu));r.ip=0x446b;break;
        case 0x446b:r.dx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x7bdeu));r.ip=0x446f;break;
        case 0x446f:push(r.dx);r.ip=0x4470;break;
        case 0x4470:push(r.bx);r.ip=0x4471;break;
        case 0x4471:push(r.ax);r.ip=0x4472;break;
        case 0x4472:les(-8);r.ip=0x4475;break;
        case 0x4475:al(byte(4));r.ip=0x4479;break;
        case 0x4479:zeroAh();r.ip=0x447b;break;
        case 0x447b:r.dx=logic(0);r.ip=0x447d;break;
        case 0x447d:farCall(0xf0f,0x4482);break;
        case 0x4482:r.cx=pop();r.ip=0x4483;break;
        case 0x4483:r.si=pop();r.ip=0x4484;break;
        case 0x4484:r.di=pop();r.ip=0x4485;break;
        case 0x4485:farCall(0xefb,0x448a);break;
        case 0x448a:farCall(0xf13,0x448f);break;
        case 0x448f:push(r.dx);r.ip=0x4490;break;
        case 0x4490:push(r.ax);r.ip=0x4491;break;
        case 0x4491:les(-8);r.ip=0x4494;break;
        case 0x4494:r.ax=read(7);r.ip=0x4498;break;
        case 0x4498:cwd();r.ip=0x4499;break;
        case 0x4499:r.cx=r.ax;r.ip=0x449b;break;
        case 0x449b:r.bx=r.dx;r.ip=0x449d;break;
        case 0x449d:les(-12);r.ip=0x44a0;break;
        case 0x44a0:r.ax=read(0);r.ip=0x44a3;break;
        case 0x44a3:r.dx=logic(0);r.ip=0x44a5;break;
        case 0x44a5:r.ax=arithmetic(r.ax,r.cx);r.ip=0x44a7;break;
        case 0x44a7:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x44a9;break;
        case 0x44a9:r.cx=pop();r.ip=0x44aa;break;
        case 0x44aa:r.bx=pop();r.ip=0x44ab;break;
        case 0x44ab:r.ax=arithmetic(r.ax,r.cx);r.ip=0x44ad;break;
        case 0x44ad:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x44af;break;
        case 0x44af:les(-8);r.ip=0x44b2;break;
        case 0x44b2:write(11,r.ax);r.ip=0x44b6;break;
        case 0x44b6:les(-8);r.ip=0x44b9;break;
        case 0x44b9:al(byte(6));r.ip=0x44bd;break;
        case 0x44bd:zeroAh();r.ip=0x44bf;break;
        case 0x44bf:r.di=r.ax;r.ip=0x44c1;break;
        case 0x44c1:r.di=shift(r.di,1);r.ip=0x44c3;break;
        case 0x44c3:r.si=r.di;r.ip=0x44c5;break;
        case 0x44c5:r.di=shift(r.di,1);r.ip=0x44c7;break;
        case 0x44c7:r.di=arithmetic(r.di,r.si);r.ip=0x44c9;break;
        case 0x44c9:r.ax=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x7bdau));r.ip=0x44cd;break;
        case 0x44cd:r.bx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x7bdcu));r.ip=0x44d1;break;
        case 0x44d1:r.dx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x7bdeu));r.ip=0x44d5;break;
        case 0x44d5:push(r.dx);r.ip=0x44d6;break;
        case 0x44d6:push(r.bx);r.ip=0x44d7;break;
        case 0x44d7:push(r.ax);r.ip=0x44d8;break;
        case 0x44d8:les(-8);r.ip=0x44db;break;
        case 0x44db:al(byte(5));r.ip=0x44df;break;
        case 0x44df:zeroAh();r.ip=0x44e1;break;
        case 0x44e1:r.dx=logic(0);r.ip=0x44e3;break;
        case 0x44e3:farCall(0xf0f,0x44e8);break;
        case 0x44e8:r.cx=pop();r.ip=0x44e9;break;
        case 0x44e9:r.si=pop();r.ip=0x44ea;break;
        case 0x44ea:r.di=pop();r.ip=0x44eb;break;
        case 0x44eb:farCall(0xefb,0x44f0);break;
        case 0x44f0:farCall(0xf13,0x44f5);break;
        case 0x44f5:push(r.dx);r.ip=0x44f6;break;
        case 0x44f6:push(r.ax);r.ip=0x44f7;break;
        case 0x44f7:les(-8);r.ip=0x44fa;break;
        case 0x44fa:r.ax=read(9);r.ip=0x44fe;break;
        case 0x44fe:cwd();r.ip=0x44ff;break;
        case 0x44ff:r.cx=r.ax;r.ip=0x4501;break;
        case 0x4501:r.bx=r.dx;r.ip=0x4503;break;
        case 0x4503:les(-12);r.ip=0x4506;break;
        case 0x4506:r.ax=read(2);r.ip=0x450a;break;
        case 0x450a:r.dx=logic(0);r.ip=0x450c;break;
        case 0x450c:r.ax=arithmetic(r.ax,r.cx);r.ip=0x450e;break;
        case 0x450e:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x4510;break;
        case 0x4510:r.cx=pop();r.ip=0x4511;break;
        case 0x4511:r.bx=pop();r.ip=0x4512;break;
        case 0x4512:r.ax=arithmetic(r.ax,r.cx);r.ip=0x4514;break;
        case 0x4514:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x4516;break;
        case 0x4516:les(-8);r.ip=0x4519;break;
        case 0x4519:write(13,r.ax);r.ip=0x451d;break;
        case 0x451d:r.ax=local(-2);r.ip=0x4520;break;
        case 0x4520:arithmetic(r.ax,local(-4),true);r.ip=0x4523;break;
        case 0x4523:branch(flag(0x40),0x4528,0x4525);break;
        case 0x4525:r.ip=0x4350;break;
        case 0x4528:r.sp=r.bp;r.bp=pop();r.ip=0x4529;break;
        case 0x4529:r.ip=pop();break;
        default:throw std::domain_error("Boss links reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
