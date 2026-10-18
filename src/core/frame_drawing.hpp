#pragma once

#include "core/game_keyboard.hpp"

#include <functional>

namespace lezac::core {

enum class FrameDrawingOutcome { Running, Returned, RuntimeError };
struct FrameDrawingSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    FrameDrawingOutcome outcome=FrameDrawingOutcome::Running;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0, timerInstructions=0, timerDeliveries=0, stringTransfers=0;
    bool operator==(const FrameDrawingSnapshot&) const = default;
};

// Original near Pascal rectangle clear 07C5 and indexed sprite painter 12DB.
// The caller retains memory, REP transfer grants and interrupt scheduling.
class FrameDrawingOperation {
public:
    using CopyBudget=std::function<uint16_t(uint16_t)>;
    FrameDrawingOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        :state_{r,game,idToggle} {
        if(r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) ||
            (r.ip!=0x7c5 && r.ip!=0x12db) || (idToggle!=0 && idToggle!=0x200000))
            throw std::invalid_argument("Frame drawing entry differs from recovered profile");
    }
    explicit FrameDrawingOperation(FrameDrawingSnapshot state):state_(state) {}
    const FrameDrawingSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return !state_.timer && state_.outcome!=FrameDrawingOutcome::Running;}
    bool returned() const noexcept {return finished() && state_.outcome==FrameDrawingOutcome::Returned;}
    bool interruptInProgress() const noexcept {return state_.timer.has_value();}
    DosGetTimeRegisters registers() const {return state_.timer?fromTimer(state_.timer->registers):state_.registers;}
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if(state_.timer || !(state_.registers.flags&0x200u)) throw std::logic_error("Drawing timer is not eligible");
        auto& r=state_.registers;push(bus,static_cast<uint16_t>(r.flags));push(bus,r.cs);push(bus,r.ip);
        r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
        state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t consumed=0;
        while(consumed<budget && !finished()) {
            if(state_.timer) {
                TimerIrqOperation timer(*state_.timer);
                if(timer.advance(1,bus)!=1) throw std::domain_error("Drawing timer did not dispatch");
                ++state_.timerInstructions;
                if(timer.returned()){state_.registers=fromTimer(timer.snapshot().registers);state_.timer.reset();}
                else state_.timer=timer.snapshot();
            } else {
                instruction(bus,copies);
                const auto& r=state_.registers;
                if(r.cs==static_cast<uint16_t>(state_.gameSegment+0x920) && r.ip==0xe2)
                    state_.outcome=FrameDrawingOutcome::RuntimeError;
            }
            ++consumed;++state_.dispatchedInstructions;
        }
        return consumed;
    }
private:
    static constexpr uint32_t Arithmetic=0x8d5;
    static uint8_t lo(uint16_t value){return static_cast<uint8_t>(value);}
    void al(uint8_t value){auto& ax=state_.registers.ax;ax=static_cast<uint16_t>((ax&0xff00u)|value);}
    void push(const TimerIrqBus& bus,uint16_t value){auto& r=state_.registers;r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value);}
    uint16_t pop(const TimerIrqBus& bus){auto& r=state_.registers;const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value;}
    uint16_t flags(uint16_t value,unsigned bits) const {
        return static_cast<uint16_t>((value==0?0x40u:0u)|((value&(1u<<(bits-1)))?0x80u:0u)|(std::popcount(lo(value))%2==0?4u:0u));
    }
    uint16_t logic(uint16_t value,unsigned bits=16){state_.registers.flags=(state_.registers.flags&~Arithmetic)|flags(value,bits);return value;}
    uint16_t arithmetic(uint16_t left,uint16_t right,bool subtract,unsigned bits=16) {
        const uint32_t mask=bits==8?255u:65535u,sign=1u<<(bits-1);
        const uint32_t wide=subtract?uint32_t{left}-right:uint32_t{left}+right;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t f=flags(value,bits)|(((left^right^value)&0x10u)?0x10u:0u);
        if(subtract?left<right:wide>mask)f|=1;
        if(subtract?((left^right)&(left^value)&sign):(~(left^right)&(left^value)&sign))f|=0x800;
        state_.registers.flags=(state_.registers.flags&~Arithmetic)|f;return value;
    }
    uint16_t increment(uint16_t value) {
        const auto carry=state_.registers.flags&1u;const auto result=arithmetic(value,1,false);
        state_.registers.flags=(state_.registers.flags&~uint32_t{1})|carry;return result;
    }
    bool flag(uint32_t value) const{return (state_.registers.flags&value)!=0;}
    void branch(bool value,uint16_t yes,uint16_t no){state_.registers.ip=value?yes:no;}
    void pointer(const TimerIrqBus& bus,uint16_t segment,uint16_t at,uint16_t& offset,uint16_t& target) {
        const auto a=bus.readWord(segment,at),b=bus.readWord(segment,static_cast<uint16_t>(at+2u));offset=a;target=b;
    }
    void multiply() {
        auto& r=state_.registers;const uint32_t product=uint32_t{r.ax}*r.bx;
        r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
        r.flags=(r.flags&~uint32_t{0x801})|(r.dx?0x801u:0u);
    }
    void stores(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.registers;const auto count=copies(r.cx);
        if(count>r.cx || (r.cx && !count))throw std::domain_error("Drawing REP grant differs");
        for(unsigned i=0;i<count;++i){bus.writeByte(r.es,r.di,lo(r.ax));r.di=static_cast<uint16_t>(r.di+(flag(0x400)?-1:1));}
        r.cx=static_cast<uint16_t>(r.cx-count);state_.stringTransfers+=count;
        if(!r.cx)r.ip=static_cast<uint16_t>(r.ip+2u);
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.registers;
        const auto at=[&](int delta){return static_cast<uint16_t>(r.bp+delta);};
        const auto local=[&](int delta){return bus.readWord(r.ss,at(delta));};
        const auto store=[&](int delta,uint16_t value){bus.writeWord(r.ss,at(delta),value);};
        if(r.cs==static_cast<uint16_t>(state_.gameSegment+0x920)) {
            switch(r.ip) {
            case 0x4df:r.ax=arithmetic(r.ax,0x200,false);r.ip=0x4e2;break;
            case 0x4e2:branch(flag(1),0x4f1,0x4e4);break;
            case 0x4e4:r.ax=arithmetic(r.ax,r.sp,true);r.ip=0x4e6;break;
            case 0x4e6:branch(!flag(1),0x4f1,0x4e8);break;
            case 0x4e8:r.ax=arithmetic(0,r.ax,true);r.ip=0x4ea;break;
            case 0x4ea:arithmetic(r.ax,bus.readWord(r.ds,0x1afa),true);r.ip=0x4ee;break;
            case 0x4ee:branch(flag(1),0x4f1,0x4f0);break;
            case 0x4f0:r.ip=pop(bus);r.cs=pop(bus);break;
            case 0x4f1:r.ax=202;r.ip=0x4f4;break;
            case 0x4f4:r.ip=0xe2;break;
            default:throw std::domain_error("Drawing runtime left recovered code");
            }
            return;
        }
        if(r.cs!=state_.gameSegment)throw std::domain_error("Drawing left recovered code");
        switch(r.ip) {
        case 0x7c5:case 0x12db:push(bus,r.bp);++r.ip;break;
        case 0x7c6:r.bp=r.sp;r.ip=0x7c8;break;
        case 0x7c8:r.ax=logic(0);r.ip=0x7ca;break;
        case 0x7ca:case 0x12e1:push(bus,r.cs);push(bus,static_cast<uint16_t>(r.ip+5u));r.cs=static_cast<uint16_t>(state_.gameSegment+0x920);r.ip=0x4df;break;
        case 0x7cf:r.ax=0xa000;r.ip=0x7d2;break;
        case 0x7d2:r.es=r.ax;r.ip=0x7d4;break;
        case 0x7d4:r.ax=local(10);r.ip=0x7d7;break;
        case 0x7d7:r.bx=0x140;r.ip=0x7da;break;
        case 0x7da:multiply();r.ip=0x7dc;break;
        case 0x7dc:r.ax=arithmetic(r.ax,local(12),false);r.ip=0x7df;break;
        case 0x7df:r.di=r.ax;r.ip=0x7e1;break;
        case 0x7e1:al(bus.readByte(r.ss,at(4)));r.ip=0x7e4;break;
        case 0x7e4:r.cx=local(6);r.ip=0x7e7;break;
        case 0x7e7:case 0x1344:push(bus,r.cx);++r.ip;break;
        case 0x7e8:push(bus,r.di);r.ip=0x7e9;break;
        case 0x7e9:r.cx=local(8);r.ip=0x7ec;break;
        case 0x7ec:stores(bus,copies);break;
        case 0x7ee:r.di=pop(bus);r.ip=0x7ef;break;
        case 0x7ef:r.di=arithmetic(r.di,0x140,false);r.ip=0x7f3;break;
        case 0x7f3:r.cx=pop(bus);r.ip=0x7f4;break;
        case 0x7f4:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x7e7,0x7f6);break;
        case 0x7f6:case 0x136a:r.sp=r.bp;r.bp=pop(bus);++r.ip;break;
        case 0x7f7:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+10u);state_.outcome=FrameDrawingOutcome::Returned;break;
        case 0x12dc:r.bp=r.sp;r.ip=0x12de;break;
        case 0x12de:r.ax=8;r.ip=0x12e1;break;
        case 0x12e6:r.sp=arithmetic(r.sp,8,true);r.ip=0x12e9;break;
        case 0x12e9:al(bus.readByte(r.ss,at(4)));r.ip=0x12ec;break;
        case 0x12ec:r.ax=lo(r.ax);logic(0,8);r.ip=0x12ee;break;
        case 0x12ee:r.di=r.ax;r.ip=0x12f0;break;
        case 0x12f0:{const auto before=r.di;r.di=static_cast<uint16_t>(uint32_t{r.di}<<2);r.flags=(r.flags&~Arithmetic)|flags(r.di,16)|0x10u|(((before>>14)&1u)?1u:0u)|(((before^r.di)&0x8000u)?0x800u:0u);r.ip=0x12f3;break;}
        case 0x12f3:r.di=arithmetic(r.di,0xc322,false);r.ip=0x12f7;break;
        case 0x12f7:store(-8,r.di);r.ip=0x12fa;break;
        case 0x12fa:store(-6,r.ds);r.ip=0x12fd;break;
        case 0x12fd:case 0x1307:case 0x1310:pointer(bus,r.ss,at(-8),r.di,r.es);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x1300:r.ax=bus.readWord(r.es,static_cast<uint16_t>(r.di+2u));r.ip=0x1304;break;
        case 0x1304:store(-2,r.ax);r.ip=0x1307;break;
        case 0x130a:al(bus.readByte(r.es,r.di));r.ip=0x130d;break;
        case 0x130d:bus.writeByte(r.ss,at(-4),lo(r.ax));r.ip=0x1310;break;
        case 0x1313:al(bus.readByte(r.es,static_cast<uint16_t>(r.di+1u)));r.ip=0x1317;break;
        case 0x1317:bus.writeByte(r.ss,at(-3),lo(r.ax));r.ip=0x131a;break;
        case 0x131a:r.ax=0xa000;r.ip=0x131d;break;
        case 0x131d:push(bus,r.ax);r.ip=0x131e;break;
        case 0x131e:r.es=pop(bus);r.ip=0x131f;break;
        case 0x131f:r.bx=0x140;r.ip=0x1322;break;
        case 0x1322:r.ax=local(6);r.ip=0x1325;break;
        case 0x1325:r.di=local(8);r.ip=0x1328;break;
        case 0x1328:multiply();r.ip=0x132a;break;
        case 0x132a:r.di=arithmetic(r.di,r.ax,false);r.ip=0x132c;break;
        case 0x132c:r.cx=static_cast<uint16_t>((r.cx&0xff00u)|bus.readByte(r.ss,at(-3)));r.ip=0x132f;break;
        case 0x132f:r.si=local(-2);r.ip=0x1332;break;
        case 0x1332:r.cx=lo(r.cx);logic(0,8);r.ip=0x1334;break;
        case 0x1334:r.ax=static_cast<uint16_t>((r.ax&255u)|(uint16_t{bus.readByte(r.ds,0x79a3)}<<8));r.ip=0x1338;break;
        case 0x1338:r.bx=static_cast<uint16_t>((r.bx&0xff00u)|bus.readByte(r.ds,0x661e));r.ip=0x133c;break;
        case 0x133c:r.bx=static_cast<uint16_t>((r.bx&255u)|(uint16_t{bus.readByte(r.ss,at(-4))}<<8));r.ip=0x133f;break;
        case 0x133f:push(bus,r.ds);r.ip=0x1340;break;
        case 0x1340:r.ds=bus.readWord(r.ds,0xc1fa);r.ip=0x1344;break;
        case 0x1345:push(bus,r.di);r.ip=0x1346;break;
        case 0x1346:r.cx=static_cast<uint16_t>((r.cx&0xff00u)|(r.bx>>8));r.ip=0x1348;break;
        case 0x1348:r.cx=lo(r.cx);logic(0,8);r.ip=0x134a;break;
        case 0x134a:al(bus.readByte(r.ds,r.si));r.si=static_cast<uint16_t>(r.si+(flag(0x400)?-1:1));r.ip=0x134b;break;
        case 0x134b:arithmetic(lo(r.ax),0,true,8);r.ip=0x134d;break;
        case 0x134d:branch(!flag(0x40),0x1358,0x134f);break;
        case 0x134f:al(static_cast<uint8_t>(r.ax>>8));r.ip=0x1351;break;
        case 0x1351:arithmetic(lo(r.ax),0,true,8);r.ip=0x1353;break;
        case 0x1353:branch(!flag(0x40),0x135e,0x1355);break;
        case 0x1355:r.di=increment(r.di);r.ip=0x1356;break;
        case 0x1356:r.ip=0x135f;break;
        case 0x1358:arithmetic(lo(r.ax),1,true,8);r.ip=0x135a;break;
        case 0x135a:branch(!flag(0x40),0x135e,0x135c);break;
        case 0x135c:al(lo(r.bx));r.ip=0x135e;break;
        case 0x135e:bus.writeByte(r.es,r.di,lo(r.ax));r.di=static_cast<uint16_t>(r.di+(flag(0x400)?-1:1));r.ip=0x135f;break;
        case 0x135f:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x134a,0x1361);break;
        case 0x1361:r.di=pop(bus);r.ip=0x1362;break;
        case 0x1362:r.cx=pop(bus);r.ip=0x1363;break;
        case 0x1363:r.di=arithmetic(r.di,0x140,false);r.ip=0x1367;break;
        case 0x1367:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x1344,0x1369);break;
        case 0x1369:r.ds=pop(bus);r.ip=0x136a;break;
        case 0x136b:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+6u);state_.outcome=FrameDrawingOutcome::Returned;break;
        default:throw std::domain_error("Frame drawing reached an unrecovered instruction");
        }
    }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r){return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};}
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r){return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};}
    FrameDrawingSnapshot state_;
};

}
