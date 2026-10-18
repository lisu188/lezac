#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <stdexcept>
#include <utility>

namespace lezac::core {

enum class FrameCameraOutcome { Running, Returned, RuntimeError };
struct FrameCameraSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0;
    FrameCameraOutcome outcome = FrameCameraOutcome::Running;
    bool operator==(const FrameCameraSnapshot&) const = default;
};

// Original near Pascal camera 3587..370E, including its unchanged CRT callees.
class FrameCameraOperation {
public:
    FrameCameraOperation(DosGetTimeRegisters registers, uint16_t gameSegment)
        : state_{registers,gameSegment} {
        if (registers.cs != gameSegment || registers.ds != static_cast<uint16_t>(gameSegment+0xaa2) || registers.ip != 0x3587)
            throw std::invalid_argument("Camera entry differs");
    }
    explicit FrameCameraOperation(FrameCameraSnapshot state) : state_(state) {}
    const FrameCameraSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != FrameCameraOutcome::Running; }
    bool returned() const noexcept { return state_.outcome == FrameCameraOutcome::Returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !finished()) {
            instruction(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
            if (state_.registers.cs == library() && state_.registers.ip == 0xe2)
                state_.outcome = FrameCameraOutcome::RuntimeError;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Arithmetic = 0x8d5;
    FrameCameraSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    bool flag(uint32_t value) const { return (state_.registers.flags & value) != 0; }
    static uint32_t valueFlags(uint16_t value) {
        return (value == 0 ? 0x40u : 0u) | (value & 0x8000 ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value) {
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | valueFlags(value);
        return value;
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract=false, bool carry=false) {
        const uint32_t extra = carry && flag(1) ? 1u : 0u;
        const uint32_t wide = subtract ? uint32_t{left}-right-extra : uint32_t{left}+right+extra;
        const auto value = static_cast<uint16_t>(wide);
        uint32_t flags = valueFlags(value) | ((left ^ right ^ value) & 16u);
        if (subtract ? uint32_t{left}<uint32_t{right}+extra : wide>65535u) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & 0x8000) :
                       (~(left ^ right) & (left ^ value) & 0x8000)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | flags;
        return value;
    }
    void multiply(uint16_t factor) {
        auto& r=state_.registers;
        const uint32_t product=uint32_t{r.ax}*factor;
        r.ax=static_cast<uint16_t>(product); r.dx=static_cast<uint16_t>(product>>16);
        r.flags=(r.flags & ~uint32_t{0x841}) | (r.dx ? 0x801u : 0u) | (r.ax==0 ? 0x40u : 0u);
    }
    void divide() {
        auto& r=state_.registers;
        const int64_t dividend=std::bit_cast<int32_t>((uint32_t{r.dx}<<16)|r.ax);
        const int32_t divisor=std::bit_cast<int16_t>(r.cx);
        if (!divisor || dividend/divisor < -32768 || dividend/divisor > 32767)
            throw std::domain_error("Camera IDIV left its recovered domain");
        r.ax=static_cast<uint16_t>(dividend/divisor);
        r.dx=static_cast<uint16_t>(dividend%divisor);
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u); bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp); r.sp=static_cast<uint16_t>(r.sp+2u); return value; };
        const auto local=[&](uint16_t offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        const auto cwd=[&] { r.dx=(r.ax & 0x8000) ? 0xffff : 0; };
        const auto farCall=[&](uint16_t ip,uint16_t next) { push(r.cs); push(next); r.cs=library(); r.ip=ip; };
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
            default:throw std::domain_error("Camera CRT reached an unrecovered instruction");
            }
            return;
        }
        if (r.cs!=state_.gameSegment) throw std::domain_error("Camera left recovered code");
        switch (r.ip) {
        case 0x3587:push(r.bp);r.ip=0x3588;break;
        case 0x3588:r.bp=r.sp;r.ip=0x358a;break;
        case 0x358a:r.ax=logic(0);r.ip=0x358c;break;
        case 0x358c:farCall(0x4df,0x3591);break;
        case 0x3591:r.ax=bus.readWord(r.ds,0x78bc);r.ip=0x3594;break;
        case 0x3594:r.dx=logic(0);r.ip=0x3596;break;
        case 0x3596:r.cx=r.ax;r.ip=0x3598;break;
        case 0x3598:r.bx=r.dx;r.ip=0x359a;break;
        case 0x359a:r.ax=local(6);r.ip=0x359d;break;
        case 0x359d:cwd();r.ip=0x359e;break;
        case 0x359e:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x35a0;break;
        case 0x35a0:r.dx=arithmetic(r.dx,r.bx,true,true);r.ip=0x35a2;break;
        case 0x35a2:r.ax=logic(r.ax & 0xfff8);r.ip=0x35a5;break;
        case 0x35a5:r.dx=logic(0);r.ip=0x35a9;break;
        case 0x35a9:bus.writeWord(r.ds,0xc216,r.ax);r.ip=0x35ac;break;
        case 0x35ac:r.ax=local(4);r.ip=0x35af;break;
        case 0x35af:r.ax=arithmetic(r.ax,80,true);r.ip=0x35b2;break;
        case 0x35b2:cwd();r.ip=0x35b3;break;
        case 0x35b3:r.ax=logic(r.ax & 0xfff8);r.ip=0x35b6;break;
        case 0x35b6:r.dx=logic(0);r.ip=0x35ba;break;
        case 0x35ba:bus.writeWord(r.ds,0xc218,r.ax);r.ip=0x35bd;break;
        case 0x35bd:r.ax=bus.readWord(r.ds,0xc204);r.ip=0x35c0;break;
        case 0x35c0:r.dx=logic(0);r.ip=0x35c2;break;
        case 0x35c2:push(r.dx);r.ip=0x35c3;break;
        case 0x35c3:push(r.ax);r.ip=0x35c4;break;
        case 0x35c4:r.ax=local(4);r.ip=0x35c7;break;
        case 0x35c7:cwd();r.ip=0x35c8;break;
        case 0x35c8:r.cx=8;r.ip=0x35cb;break;
        case 0x35cb:divide();r.ip=0x35cd;break;
        case 0x35cd:r.ax=arithmetic(r.ax,10,true);r.ip=0x35d0;break;
        case 0x35d0:cwd();r.ip=0x35d1;break;
        case 0x35d1:r.cx=pop();r.ip=0x35d2;break;
        case 0x35d2:r.bx=pop();r.ip=0x35d3;break;
        case 0x35d3:farCall(0x92a,0x35d8);break;
        case 0x35d8:push(r.dx);r.ip=0x35d9;break;
        case 0x35d9:push(r.ax);r.ip=0x35da;break;
        case 0x35da:r.ax=bus.readWord(r.ds,0x78be);r.ip=0x35dd;break;
        case 0x35dd:r.dx=logic(0);r.ip=0x35df;break;
        case 0x35df:push(r.dx);r.ip=0x35e0;break;
        case 0x35e0:push(r.ax);r.ip=0x35e1;break;
        case 0x35e1:r.ax=local(6);r.ip=0x35e4;break;
        case 0x35e4:cwd();r.ip=0x35e5;break;
        case 0x35e5:r.cx=8;r.ip=0x35e8;break;
        case 0x35e8:divide();r.ip=0x35ea;break;
        case 0x35ea:cwd();r.ip=0x35eb;break;
        case 0x35eb:r.cx=pop();r.ip=0x35ec;break;
        case 0x35ec:r.bx=pop();r.ip=0x35ed;break;
        case 0x35ed:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x35ef;break;
        case 0x35ef:r.dx=arithmetic(r.dx,r.bx,true,true);r.ip=0x35f1;break;
        case 0x35f1:r.cx=pop();r.ip=0x35f2;break;
        case 0x35f2:r.bx=pop();r.ip=0x35f3;break;
        case 0x35f3:r.ax=arithmetic(r.ax,r.cx);r.ip=0x35f5;break;
        case 0x35f5:r.dx=arithmetic(r.dx,r.bx,false,true);r.ip=0x35f7;break;
        case 0x35f7:bus.writeWord(r.ds,0xc1f0,r.ax);r.ip=0x35fa;break;
        case 0x35fa:r.ax=local(6);r.ip=0x35fd;break;
        case 0x35fd:cwd();r.ip=0x35fe;break;
        case 0x35fe:r.cx=8;r.ip=0x3601;break;
        case 0x3601:divide();r.ip=0x3603;break;
        case 0x3603:std::swap(r.dx,r.ax);r.ip=0x3604;break;
        case 0x3604:bus.writeWord(r.ds,0xc20a,r.ax);r.ip=0x3607;break;
        case 0x3607:r.ax=local(4);r.ip=0x360a;break;
        case 0x360a:cwd();r.ip=0x360b;break;
        case 0x360b:r.cx=8;r.ip=0x360e;break;
        case 0x360e:divide();r.ip=0x3610;break;
        case 0x3610:std::swap(r.dx,r.ax);r.ip=0x3611;break;
        case 0x3611:bus.writeWord(r.ds,0xc20c,r.ax);r.ip=0x3614;break;
        case 0x3614:arithmetic(bus.readWord(r.ds,0xc216),0,true);r.ip=0x3619;break;
        case 0x3619:branch(flag(0x80)==flag(0x800),0x3641,0x361b);break;
        case 0x361b:r.ax=bus.readWord(r.ds,0xc216);r.ip=0x361e;break;
        case 0x361e:cwd();r.ip=0x361f;break;
        case 0x361f:r.cx=8;r.ip=0x3622;break;
        case 0x3622:divide();r.ip=0x3624;break;
        case 0x3624:cwd();r.ip=0x3625;break;
        case 0x3625:r.cx=r.ax;r.ip=0x3627;break;
        case 0x3627:r.bx=r.dx;r.ip=0x3629;break;
        case 0x3629:r.ax=bus.readWord(r.ds,0xc1f0);r.ip=0x362c;break;
        case 0x362c:r.dx=logic(0);r.ip=0x362e;break;
        case 0x362e:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x3630;break;
        case 0x3630:r.dx=arithmetic(r.dx,r.bx,true,true);r.ip=0x3632;break;
        case 0x3632:bus.writeWord(r.ds,0xc1f0,r.ax);r.ip=0x3635;break;
        case 0x3635:r.ax=logic(0);r.ip=0x3637;break;
        case 0x3637:bus.writeWord(r.ds,0xc20a,r.ax);r.ip=0x363a;break;
        case 0x363a:r.ax=logic(0);r.ip=0x363c;break;
        case 0x363c:bus.writeWord(r.ds,0xc216,r.ax);r.ip=0x363f;break;
        case 0x363f:r.ip=0x3674;break;
        case 0x3641:r.ax=bus.readWord(r.ds,0xc216);r.ip=0x3644;break;
        case 0x3644:arithmetic(r.ax,bus.readWord(r.ds,0x2094),true);r.ip=0x3648;break;
        case 0x3648:branch(flag(0x40)||flag(0x80)!=flag(0x800),0x3674,0x364a);break;
        case 0x364a:r.ax=bus.readWord(r.ds,0x2094);r.ip=0x364d;break;
        case 0x364d:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc216),true);r.ip=0x3651;break;
        case 0x3651:cwd();r.ip=0x3652;break;
        case 0x3652:r.cx=8;r.ip=0x3655;break;
        case 0x3655:divide();r.ip=0x3657;break;
        case 0x3657:cwd();r.ip=0x3658;break;
        case 0x3658:r.cx=r.ax;r.ip=0x365a;break;
        case 0x365a:r.bx=r.dx;r.ip=0x365c;break;
        case 0x365c:r.ax=bus.readWord(r.ds,0xc1f0);r.ip=0x365f;break;
        case 0x365f:r.dx=logic(0);r.ip=0x3661;break;
        case 0x3661:r.ax=arithmetic(r.ax,r.cx);r.ip=0x3663;break;
        case 0x3663:r.dx=arithmetic(r.dx,r.bx,false,true);r.ip=0x3665;break;
        case 0x3665:bus.writeWord(r.ds,0xc1f0,r.ax);r.ip=0x3668;break;
        case 0x3668:bus.writeWord(r.ds,0xc20a,7);r.ip=0x366e;break;
        case 0x366e:r.ax=bus.readWord(r.ds,0x2094);r.ip=0x3671;break;
        case 0x3671:bus.writeWord(r.ds,0xc216,r.ax);r.ip=0x3674;break;
        case 0x3674:arithmetic(bus.readWord(r.ds,0xc218),0,true);r.ip=0x3679;break;
        case 0x3679:branch(flag(0x80)==flag(0x800),0x36af,0x367b);break;
        case 0x367b:r.ax=bus.readWord(r.ds,0xc204);r.ip=0x367e;break;
        case 0x367e:r.dx=logic(0);r.ip=0x3680;break;
        case 0x3680:push(r.dx);r.ip=0x3681;break;
        case 0x3681:push(r.ax);r.ip=0x3682;break;
        case 0x3682:r.ax=bus.readWord(r.ds,0xc218);r.ip=0x3685;break;
        case 0x3685:cwd();r.ip=0x3686;break;
        case 0x3686:r.cx=8;r.ip=0x3689;break;
        case 0x3689:divide();r.ip=0x368b;break;
        case 0x368b:cwd();r.ip=0x368c;break;
        case 0x368c:r.cx=pop();r.ip=0x368d;break;
        case 0x368d:r.bx=pop();r.ip=0x368e;break;
        case 0x368e:farCall(0x92a,0x3693);break;
        case 0x3693:r.cx=r.ax;r.ip=0x3695;break;
        case 0x3695:r.bx=r.dx;r.ip=0x3697;break;
        case 0x3697:r.ax=bus.readWord(r.ds,0xc1f0);r.ip=0x369a;break;
        case 0x369a:r.dx=logic(0);r.ip=0x369c;break;
        case 0x369c:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x369e;break;
        case 0x369e:r.dx=arithmetic(r.dx,r.bx,true,true);r.ip=0x36a0;break;
        case 0x36a0:bus.writeWord(r.ds,0xc1f0,r.ax);r.ip=0x36a3;break;
        case 0x36a3:r.ax=logic(0);r.ip=0x36a5;break;
        case 0x36a5:bus.writeWord(r.ds,0xc20c,r.ax);r.ip=0x36a8;break;
        case 0x36a8:r.ax=logic(0);r.ip=0x36aa;break;
        case 0x36aa:bus.writeWord(r.ds,0xc218,r.ax);r.ip=0x36ad;break;
        case 0x36ad:r.ip=0x36f0;break;
        case 0x36af:r.ax=bus.readWord(r.ds,0xc218);r.ip=0x36b2;break;
        case 0x36b2:arithmetic(r.ax,bus.readWord(r.ds,0x2096),true);r.ip=0x36b6;break;
        case 0x36b6:branch(flag(0x40)||flag(0x80)!=flag(0x800),0x36f0,0x36b8);break;
        case 0x36b8:r.ax=bus.readWord(r.ds,0xc204);r.ip=0x36bb;break;
        case 0x36bb:r.dx=logic(0);r.ip=0x36bd;break;
        case 0x36bd:push(r.dx);r.ip=0x36be;break;
        case 0x36be:push(r.ax);r.ip=0x36bf;break;
        case 0x36bf:r.ax=bus.readWord(r.ds,0xc218);r.ip=0x36c2;break;
        case 0x36c2:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0x2096),true);r.ip=0x36c6;break;
        case 0x36c6:cwd();r.ip=0x36c7;break;
        case 0x36c7:r.cx=8;r.ip=0x36ca;break;
        case 0x36ca:divide();r.ip=0x36cc;break;
        case 0x36cc:cwd();r.ip=0x36cd;break;
        case 0x36cd:r.cx=pop();r.ip=0x36ce;break;
        case 0x36ce:r.bx=pop();r.ip=0x36cf;break;
        case 0x36cf:farCall(0x92a,0x36d4);break;
        case 0x36d4:r.cx=r.ax;r.ip=0x36d6;break;
        case 0x36d6:r.bx=r.dx;r.ip=0x36d8;break;
        case 0x36d8:r.ax=bus.readWord(r.ds,0xc1f0);r.ip=0x36db;break;
        case 0x36db:r.dx=logic(0);r.ip=0x36dd;break;
        case 0x36dd:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x36df;break;
        case 0x36df:r.dx=arithmetic(r.dx,r.bx,true,true);r.ip=0x36e1;break;
        case 0x36e1:bus.writeWord(r.ds,0xc1f0,r.ax);r.ip=0x36e4;break;
        case 0x36e4:bus.writeWord(r.ds,0xc20c,7);r.ip=0x36ea;break;
        case 0x36ea:r.ax=bus.readWord(r.ds,0x2096);r.ip=0x36ed;break;
        case 0x36ed:bus.writeWord(r.ds,0xc218,r.ax);r.ip=0x36f0;break;
        case 0x36f0:r.ax=bus.readWord(r.ds,0xc1f0);r.ip=0x36f3;break;
        case 0x36f3:bus.writeWord(r.ds,0xc1f0,r.ax);r.ip=0x36f6;break;
        case 0x36f6:r.ax=bus.readWord(r.ds,0x2098);r.ip=0x36f9;break;
        case 0x36f9:cwd();r.ip=0x36fa;break;
        case 0x36fa:r.cx=r.ax;r.ip=0x36fc;break;
        case 0x36fc:r.bx=r.dx;r.ip=0x36fe;break;
        case 0x36fe:r.ax=bus.readWord(r.ds,0xc20a);r.ip=0x3701;break;
        case 0x3701:r.dx=logic(0);r.ip=0x3703;break;
        case 0x3703:r.ax=arithmetic(r.ax,r.cx);r.ip=0x3705;break;
        case 0x3705:r.dx=arithmetic(r.dx,r.bx,false,true);r.ip=0x3707;break;
        case 0x3707:bus.writeWord(r.ds,0xc20a,r.ax);r.ip=0x370a;break;
        case 0x370a:r.sp=r.bp;r.bp=pop();r.ip=0x370b;break;
        case 0x370b:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);state_.outcome=FrameCameraOutcome::Returned;break;
        default:throw std::domain_error("Camera reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
