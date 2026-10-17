#pragma once

#include "core/game_keyboard.hpp"

#include <functional>

namespace lezac::core {

enum class FrameHudOutcome { Running, Returned, RuntimeError, BreakOutput };
struct FrameHudSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0, callbackBase=0;
    uint32_t idToggleMask=0;
    bool hudOnly=false;
    FrameHudOutcome outcome=FrameHudOutcome::Running;
    std::optional<GameKeyboardSnapshot> keyboard=std::nullopt;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0, timerInstructions=0, timerDeliveries=0, stringTransfers=0;
    bool operator==(const FrameHudSnapshot&) const = default;
};

// Original 79E8..7A13, including HUD, palette requests, digit blits and CRT Move.
// REP transfer budgets and IRQ eligibility belong to the external normal-core clock.
class FrameHudOperation {
public:
    using CopyBudget=std::function<uint16_t(uint16_t)>;
    FrameHudOperation(DosGetTimeRegisters r,uint16_t callbackBase,uint16_t game,uint32_t idToggle)
        :state_{r,game,callbackBase,idToggle,r.ip==0x3184} {
        if(r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || (r.ip!=0x79e8 && r.ip!=0x3184) ||
            callbackBase>0xffec || (idToggle!=0 && idToggle!=0x200000))
            throw std::invalid_argument("Frame HUD entry differs from the recovered profile");
    }
    explicit FrameHudOperation(FrameHudSnapshot state):state_(state) {}
    const FrameHudSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return !state_.timer && state_.outcome!=FrameHudOutcome::Running;}
    bool returned() const noexcept {return finished() && state_.outcome==FrameHudOutcome::Returned;}
    bool interruptInProgress() const noexcept {return state_.timer || (state_.keyboard && GameKeyboardOperation(*state_.keyboard).interruptInProgress());}
    DosGetTimeRegisters registers() const {
        if(state_.timer) return fromTimer(state_.timer->registers);
        return state_.keyboard?GameKeyboardOperation(*state_.keyboard).registers():state_.registers;
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if(state_.keyboard) {
            GameKeyboardOperation operation(*state_.keyboard);operation.deliverTimerInterrupt(bus);state_.keyboard=operation.snapshot();
        } else {
            if(state_.timer || !(state_.registers.flags&0x200u)) throw std::logic_error("Frame HUD timer is not eligible");
            auto& r=state_.registers;push(bus,static_cast<uint16_t>(r.flags));push(bus,r.cs);push(bus,r.ip);
            r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
            state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t consumed=0;
        while(consumed<budget && !finished()) {
            if(state_.timer) {
                TimerIrqOperation timer(*state_.timer);if(timer.advance(1,bus)!=1) throw std::domain_error("HUD timer did not dispatch");
                ++state_.timerInstructions;
                if(timer.returned()) {state_.registers=fromTimer(timer.snapshot().registers);state_.timer.reset();}
                else state_.timer=timer.snapshot();
            } else if(state_.keyboard) {
                GameKeyboardOperation operation(*state_.keyboard);const bool timer=operation.interruptInProgress();
                if(operation.advance(1,bus)!=1) throw std::domain_error("HUD keyboard did not dispatch");
                if(timer) ++state_.timerInstructions;
                state_.keyboard=operation.snapshot();
                if(operation.finished()) {
                    state_.registers=operation.registers();state_.outcome=operation.returned()?FrameHudOutcome::Returned:FrameHudOutcome::BreakOutput;
                    state_.keyboard.reset();
                }
            } else {
                instruction(bus,copies);
                const auto& r=state_.registers;
                if(r.cs==static_cast<uint16_t>(state_.gameSegment+0x920) && r.ip==0xe2) state_.outcome=FrameHudOutcome::RuntimeError;
                if(!state_.hudOnly && r.cs==state_.gameSegment && r.ip==0x7a00)
                    state_.keyboard=GameKeyboardOperation(r,state_.callbackBase,state_.gameSegment,state_.idToggleMask).snapshot();
            }
            ++consumed;++state_.dispatchedInstructions;
        }
        return consumed;
    }
private:
    static constexpr uint32_t Arithmetic=0x8d5;
    static uint8_t lo(uint16_t value) {return static_cast<uint8_t>(value);}
    void al(uint8_t value) {auto& ax=state_.registers.ax;ax=static_cast<uint16_t>((ax&0xff00u)|value);}
    uint16_t stackOffset(int delta) const {return static_cast<uint16_t>(state_.registers.bp+delta);}
    void push(const TimerIrqBus& bus,uint16_t value) {auto& r=state_.registers;r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value);}
    uint16_t pop(const TimerIrqBus& bus) {auto& r=state_.registers;const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value;}
    void call(const TimerIrqBus& bus,uint16_t at,uint16_t next) {push(bus,next);state_.registers.ip=at;}
    void farCall(const TimerIrqBus& bus,uint16_t at,uint16_t next) {push(bus,state_.registers.cs);push(bus,next);state_.registers.cs=static_cast<uint16_t>(state_.gameSegment+0x920);state_.registers.ip=at;}
    uint16_t flags(uint16_t value,unsigned bits) const {
        return static_cast<uint16_t>((value==0?0x40u:0u)|((value&(1u<<(bits-1)))?0x80u:0u)|(std::popcount(lo(value))%2==0?4u:0u));
    }
    uint16_t logic(uint16_t value,unsigned bits=16) {state_.registers.flags=(state_.registers.flags&~Arithmetic)|flags(value,bits);return value;}
    uint16_t arithmetic(uint16_t left,uint16_t right,bool subtract,unsigned bits=16,bool carry=false) {
        const uint32_t c=carry?(state_.registers.flags&1u):0u,mask=bits==8?255u:65535u,sign=1u<<(bits-1);
        const uint32_t wide=subtract?uint32_t{left}-right-c:uint32_t{left}+right+c;
        const auto value=static_cast<uint16_t>(wide&mask);uint32_t f=flags(value,bits)|(((left^right^value)&0x10u)?0x10u:0u);
        if(subtract?uint32_t{left}<uint32_t{right}+c:wide>mask) f|=1;
        if(subtract?((left^right)&(left^value)&sign):(~(left^right)&(left^value)&sign)) f|=0x800;
        state_.registers.flags=(state_.registers.flags&~Arithmetic)|f;return value;
    }
    uint16_t increment(uint16_t value,bool decrement,unsigned bits=16) {
        const auto carry=state_.registers.flags&1u;const auto result=arithmetic(value,1,decrement,bits);
        state_.registers.flags=(state_.registers.flags&~uint32_t{1})|carry;return result;
    }
    uint16_t shift(uint16_t value,unsigned count) {
        const auto result=static_cast<uint16_t>(uint32_t{value}<<count);
        state_.registers.flags=(state_.registers.flags&~Arithmetic)|flags(result,16)|0x10u|
            (((value>>(16-count))&1u)?1u:0u)|(((value^result)&0x8000u)?0x800u:0u);
        return result;
    }
    bool flag(uint32_t value) const {return (state_.registers.flags&value)!=0;}
    void branch(bool value,uint16_t yes,uint16_t no) {state_.registers.ip=value?yes:no;}
    void pointer(const TimerIrqBus& bus,uint16_t segment,uint16_t at,uint16_t& offset,uint16_t& target) {
        const auto a=bus.readWord(segment,at),b=bus.readWord(segment,static_cast<uint16_t>(at+2u));offset=a;target=b;
    }
    void repeated(const TimerIrqBus& bus,const CopyBudget& copies,bool word) {
        auto& r=state_.registers;const auto count=copies(r.cx);
        if(count>r.cx || (r.cx && !count)) throw std::domain_error("HUD REP transfer budget differs");
        for(unsigned i=0;i<count;++i) {
            if(word) bus.writeWord(r.es,r.di,bus.readWord(r.ds,r.si));else bus.writeByte(r.es,r.di,bus.readByte(r.ds,r.si));
            const int step=(flag(0x400)?-1:1)*(word?2:1);r.si=static_cast<uint16_t>(r.si+step);r.di=static_cast<uint16_t>(r.di+step);
        }
        r.cx=static_cast<uint16_t>(r.cx-count);state_.stringTransfers+=count;
        if(!r.cx) r.ip=static_cast<uint16_t>(r.ip+2u);
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.registers;
        const auto local=[&](int delta){return bus.readWord(r.ss,stackOffset(delta));};
        const auto store=[&](int delta,uint16_t value){bus.writeWord(r.ss,stackOffset(delta),value);};
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
            case 0x90e:r.bx=r.sp;r.ip=0x910;break;
            case 0x910:r.dx=r.ds;r.ip=0x912;break;
            case 0x912:pointer(bus,r.ss,static_cast<uint16_t>(r.bx+10u),r.si,r.ds);r.ip=0x916;break;
            case 0x916:pointer(bus,r.ss,static_cast<uint16_t>(r.bx+6u),r.di,r.es);r.ip=0x91a;break;
            case 0x91a:r.cx=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+4u));r.ip=0x91e;break;
            case 0x91e:r.flags&=~uint32_t{0x400};r.ip=0x91f;break;
            case 0x91f:repeated(bus,copies,false);break;
            case 0x921:r.ds=r.dx;r.ip=0x923;break;
            case 0x923:r.ip=pop(bus);r.cs=pop(bus);r.sp=static_cast<uint16_t>(r.sp+10u);break;
            default:throw std::domain_error("HUD runtime left recovered code");
            }
            return;
        }
        if(r.cs!=state_.gameSegment) throw std::domain_error("HUD left recovered code");
        switch(r.ip) {
        case 0x79e8:al(bus.readByte(r.ds,0x79b5));r.ip=0x79eb;break;
        case 0x79eb:arithmetic(lo(r.ax),bus.readByte(r.ds,0x79b6),true,8);r.ip=0x79ef;break;
        case 0x79ef:branch(!flag(0x40),0x79fa,0x79f1);break;
        case 0x79f1:r.ax=bus.readWord(r.ds,0x2088);r.ip=0x79f4;break;
        case 0x79f4:arithmetic(r.ax,bus.readWord(r.ds,0x208a),true);r.ip=0x79f8;break;
        case 0x79f8:branch(flag(0x40),0x7a00,0x79fa);break;
        case 0x79fa:push(bus,0xcb0f);r.ip=0x79fd;break;
        case 0x79fd:call(bus,0x3184,0x7a00);break;
        // Original near Pascal frames, including the real runtime stack check.
        case 0x3184:case 0x495:case 0x313d:push(bus,r.bp);++r.ip;break;
        case 0x3185:r.bp=r.sp;r.ip=0x3187;break;
        case 0x496:r.bp=r.sp;r.ip=0x498;break;
        case 0x313e:r.bp=r.sp;r.ip=0x3140;break;
        case 0x3187:r.ax=2;r.ip=0x318a;break;
        case 0x498:r.ax=12;r.ip=0x49b;break;
        case 0x3140:r.ax=2;r.ip=0x3143;break;
        case 0x318a:farCall(bus,0x4df,0x318f);break;
        case 0x49b:farCall(bus,0x4df,0x4a0);break;
        case 0x3143:farCall(bus,0x4df,0x3148);break;
        case 0x318f:r.sp=arithmetic(r.sp,2,true);r.ip=0x3192;break;
        case 0x4a0:r.sp=arithmetic(r.sp,12,true);r.ip=0x4a3;break;
        case 0x3148:r.sp=arithmetic(r.sp,2,true);r.ip=0x314b;break;
        // Shared objective cache, completion flags and scratch addresses.
        case 0x3192:r.ax=local(4);r.ip=0x3195;break;
        case 0x3195:r.ax=arithmetic(r.ax,0x500,false);r.ip=0x3198;break;
        case 0x3198:r.ax=arithmetic(r.ax,25,false);r.ip=0x319b;break;
        case 0x319b:bus.writeWord(r.ds,0x2072,r.ax);r.ip=0x319e;break;
        case 0x319e:r.ax=bus.readWord(r.ds,0x208a);r.ip=0x31a1;break;
        case 0x31a1:arithmetic(r.ax,bus.readWord(r.ds,0x2088),true);r.ip=0x31a5;break;
        case 0x31a5:branch(flag(0x40),0x31ee,0x31a7);break;
        case 0x31a7:r.ax=bus.readWord(r.ds,0x2088);r.ip=0x31aa;break;
        case 0x31aa:bus.writeWord(r.ds,0x208a,r.ax);r.ip=0x31ad;break;
        case 0x31ad:push(bus,0xfff5);r.ip=0x31af;break;
        case 0x31af:r.di=0x1ab2;r.ip=0x31b2;break;
        case 0x31b2:push(bus,r.ds);r.ip=0x31b3;break;
        case 0x31b3:push(bus,r.di);r.ip=0x31b4;break;
        case 0x31b4:r.di=0x1aae;r.ip=0x31b7;break;
        case 0x31b7:push(bus,r.ds);r.ip=0x31b8;break;
        case 0x31b8:push(bus,r.di);r.ip=0x31b9;break;
        case 0x31b9:call(bus,0x495,0x31bc);break;
        case 0x31bc:r.ax=bus.readWord(r.ds,0x2086);r.ip=0x31bf;break;
        case 0x31bf:store(-2,r.ax);r.ip=0x31c2;break;
        case 0x31c2:r.ax=bus.readWord(r.ds,0x2088);r.ip=0x31c5;break;
        case 0x31c5:r.dx=logic(0);r.ip=0x31c7;break;
        case 0x31c7:r.cx=r.ax;r.ip=0x31c9;break;
        case 0x31c9:r.bx=r.dx;r.ip=0x31cb;break;
        case 0x31cb:r.ax=local(-2);r.ip=0x31ce;break;
        case 0x31ce:r.dx=(r.ax&0x8000u)?0xffff:0;r.ip=0x31cf;break;
        case 0x31cf:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x31d1;break;
        case 0x31d1:r.dx=arithmetic(r.dx,r.bx,true,16,true);r.ip=0x31d3;break;
        case 0x31d3:store(-2,r.ax);r.ip=0x31d6;break;
        case 0x31d6:arithmetic(local(-2),0,true);r.ip=0x31da;break;
        case 0x31da:branch(!flag(0x40) && flag(0x80)==flag(0x800),0x31e6,0x31dc);break;
        case 0x31dc:r.ax=logic(0);r.ip=0x31de;break;
        case 0x31de:store(-2,r.ax);r.ip=0x31e1;break;
        case 0x31e1:bus.writeByte(r.ds,0x79c5,1);r.ip=0x31e6;break;
        case 0x31e6:push(bus,local(-2));r.ip=0x31e9;break;
        case 0x31e9:push(bus,2);r.ip=0x31eb;break;
        case 0x31eb:call(bus,0x313d,0x31ee);break;
        case 0x31ee:al(bus.readByte(r.ds,0x79b6));r.ip=0x31f1;break;
        case 0x31f1:arithmetic(lo(r.ax),bus.readByte(r.ds,0x79b5),true,8);r.ip=0x31f5;break;
        case 0x31f5:branch(flag(0x40),0x324d,0x31f7);break;
        case 0x31f7:push(bus,0xfff6);r.ip=0x31f9;break;
        case 0x31f9:r.di=0x1ab2;r.ip=0x31fc;break;
        case 0x31fc:push(bus,r.ds);r.ip=0x31fd;break;
        case 0x31fd:push(bus,r.di);r.ip=0x31fe;break;
        case 0x31fe:r.di=0x1aae;r.ip=0x3201;break;
        case 0x3201:push(bus,r.ds);r.ip=0x3202;break;
        case 0x3202:push(bus,r.di);r.ip=0x3203;break;
        case 0x3203:call(bus,0x495,0x3206);break;
        case 0x3206:al(bus.readByte(r.ds,0x79b5));r.ip=0x3209;break;
        case 0x3209:bus.writeByte(r.ds,0x79b6,lo(r.ax));r.ip=0x320c;break;
        case 0x320c:r.ax=local(4);r.ip=0x320f;break;
        case 0x320f:r.ax=arithmetic(r.ax,0x1900,false);r.ip=0x3212;break;
        case 0x3212:r.ax=arithmetic(r.ax,25,false);r.ip=0x3215;break;
        case 0x3215:bus.writeWord(r.ds,0x2072,r.ax);r.ip=0x3218;break;
        case 0x3218:al(bus.readByte(r.ds,0x79b3));r.ip=0x321b;break;
        case 0x321b:r.ax=static_cast<uint16_t>(lo(r.ax));logic(0,8);r.ip=0x321d;break;
        case 0x321d:store(-2,r.ax);r.ip=0x3220;break;
        case 0x3220:al(bus.readByte(r.ds,0x79b5));r.ip=0x3223;break;
        case 0x3223:r.ax=static_cast<uint16_t>(lo(r.ax));logic(0,8);r.ip=0x3225;break;
        case 0x3225:arithmetic(r.ax,local(-2),true);r.ip=0x3228;break;
        case 0x3228:branch(flag(0x80)==flag(0x800),0x323b,0x322a);break;
        case 0x322a:al(bus.readByte(r.ds,0x79b5));r.ip=0x322d;break;
        case 0x322d:r.ax=static_cast<uint16_t>(lo(r.ax));logic(0,8);r.ip=0x322f;break;
        case 0x322f:r.dx=r.ax;r.ip=0x3231;break;
        case 0x3231:r.ax=local(-2);r.ip=0x3234;break;
        case 0x3234:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x3236;break;
        case 0x3236:store(-2,r.ax);r.ip=0x3239;break;
        case 0x3239:r.ip=0x3245;break;
        case 0x323b:r.ax=logic(0);r.ip=0x323d;break;
        case 0x323d:store(-2,r.ax);r.ip=0x3240;break;
        case 0x3240:bus.writeByte(r.ds,0x79c6,1);r.ip=0x3245;break;
        case 0x3245:push(bus,local(-2));r.ip=0x3248;break;
        case 0x3248:push(bus,2);r.ip=0x324a;break;
        case 0x324a:call(bus,0x313d,0x324d);break;
        case 0x324d:arithmetic(bus.readByte(r.ds,0x79c5),0,true,8);r.ip=0x3252;break;
        case 0x3252:branch(flag(0x40),0x326a,0x3254);break;
        case 0x3254:arithmetic(bus.readByte(r.ds,0x79c6),0,true,8);r.ip=0x3259;break;
        case 0x3259:branch(flag(0x40),0x326a,0x325b);break;
        case 0x325b:push(bus,0xffe0);r.ip=0x325d;break;
        case 0x325d:r.di=0x1ab2;r.ip=0x3260;break;
        case 0x3260:push(bus,r.ds);r.ip=0x3261;break;
        case 0x3261:push(bus,r.di);r.ip=0x3262;break;
        case 0x3262:r.di=0x1aae;r.ip=0x3265;break;
        case 0x3265:push(bus,r.ds);r.ip=0x3266;break;
        case 0x3266:push(bus,r.di);r.ip=0x3267;break;
        case 0x3267:call(bus,0x495,0x326a);break;
        case 0x326a:case 0x567:case 0x3180:r.sp=r.bp;r.bp=pop(bus);++r.ip;break;
        case 0x326b:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+2u);if(state_.hudOnly) state_.outcome=FrameHudOutcome::Returned;break;
        case 0x568:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+10u);break;
        case 0x3181:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+4u);break;
        // Two-slot palette request, with original byte-count wrap and duplicate scan.
        case 0x4a3:pointer(bus,r.ss,stackOffset(8),r.di,r.es);r.ip=0x4a6;break;
        case 0x4a6:push(bus,r.es);r.ip=0x4a7;break;
        case 0x4a7:push(bus,r.di);r.ip=0x4a8;break;
        case 0x4a8:r.di=stackOffset(-4);r.ip=0x4ab;break;
        case 0x4ab:push(bus,r.ss);r.ip=0x4ac;break;
        case 0x4ac:push(bus,r.di);r.ip=0x4ad;break;
        case 0x4ad:push(bus,3);r.ip=0x4af;break;
        case 0x4af:farCall(bus,0x90e,0x4b4);break;
        case 0x4b4:pointer(bus,r.ss,stackOffset(4),r.di,r.es);r.ip=0x4b7;break;
        case 0x4b7:push(bus,r.es);r.ip=0x4b8;break;
        case 0x4b8:push(bus,r.di);r.ip=0x4b9;break;
        case 0x4b9:r.di=stackOffset(-8);r.ip=0x4bc;break;
        case 0x4bc:push(bus,r.ss);r.ip=0x4bd;break;
        case 0x4bd:push(bus,r.di);r.ip=0x4be;break;
        case 0x4be:push(bus,3);r.ip=0x4c0;break;
        case 0x4c0:farCall(bus,0x90e,0x4c5);break;
        case 0x4c5:al(bus.readByte(r.ds,0x79cb));r.ip=0x4c8;break;
        case 0x4c8:r.ax=lo(r.ax);logic(0,8);r.ip=0x4ca;break;
        case 0x4ca:r.ax=increment(r.ax,false);r.ip=0x4cb;break;
        case 0x4cb:bus.writeByte(r.ss,stackOffset(-9),lo(r.ax));r.ip=0x4ce;break;
        case 0x4ce:arithmetic(bus.readByte(r.ds,0x79cb),0,true,8);r.ip=0x4d3;break;
        case 0x4d3:branch(flag(1)||flag(0x40),0x508,0x4d5);break;
        case 0x4d5:al(bus.readByte(r.ds,0x79cb));r.ip=0x4d8;break;
        case 0x4d8:bus.writeByte(r.ss,stackOffset(-11),lo(r.ax));r.ip=0x4db;break;
        case 0x4db:al(1);r.ip=0x4dd;break;
        case 0x4dd:arithmetic(lo(r.ax),bus.readByte(r.ss,stackOffset(-11)),true,8);r.ip=0x4e0;break;
        case 0x4e0:branch(!flag(1)&&!flag(0x40),0x508,0x4e2);break;
        case 0x4e2:bus.writeByte(r.ss,stackOffset(-10),lo(r.ax));r.ip=0x4e5;break;
        case 0x4e5:r.ip=0x4ea;break;
        case 0x4e7:bus.writeByte(r.ss,stackOffset(-10),lo(increment(bus.readByte(r.ss,stackOffset(-10)),false,8)));r.ip=0x4ea;break;
        case 0x4ea:al(bus.readByte(r.ss,stackOffset(-10)));r.ip=0x4ed;break;
        case 0x4ed:r.ax=lo(r.ax);logic(0,8);r.ip=0x4ef;break;
        case 0x4ef:r.di=r.ax;r.ip=0x4f1;break;
        case 0x4f1:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x79cd)));r.ip=0x4f5;break;
        case 0x4f5:arithmetic(lo(r.ax),bus.readByte(r.ss,stackOffset(12)),true,8);r.ip=0x4f8;break;
        case 0x4f8:branch(!flag(0x40),0x500,0x4fa);break;
        case 0x4fa:al(bus.readByte(r.ss,stackOffset(-10)));r.ip=0x4fd;break;
        case 0x4fd:bus.writeByte(r.ss,stackOffset(-9),lo(r.ax));r.ip=0x500;break;
        case 0x500:al(bus.readByte(r.ss,stackOffset(-10)));r.ip=0x503;break;
        case 0x503:arithmetic(lo(r.ax),bus.readByte(r.ss,stackOffset(-11)),true,8);r.ip=0x506;break;
        case 0x506:branch(!flag(0x40),0x4e7,0x508);break;
        case 0x508:arithmetic(bus.readByte(r.ss,stackOffset(-9)),3,true,8);r.ip=0x50c;break;
        case 0x50c:branch(!flag(1),0x567,0x50e);break;
        case 0x50e:al(bus.readByte(r.ss,stackOffset(-9)));r.ip=0x511;break;
        case 0x511:arithmetic(lo(r.ax),bus.readByte(r.ds,0x79cb),true,8);r.ip=0x515;break;
        case 0x515:branch(flag(1)||flag(0x40),0x51b,0x517);break;
        case 0x517:bus.writeByte(r.ds,0x79cb,lo(increment(bus.readByte(r.ds,0x79cb),false,8)));r.ip=0x51b;break;
        case 0x51b:r.dx=static_cast<uint16_t>((r.dx&0xff00u)|bus.readByte(r.ss,stackOffset(12)));r.ip=0x51e;break;
        case 0x51e:al(bus.readByte(r.ss,stackOffset(-9)));r.ip=0x521;break;
        case 0x521:r.ax=lo(r.ax);logic(0,8);r.ip=0x523;break;
        case 0x523:r.di=r.ax;r.ip=0x525;break;
        case 0x525:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x79cd),lo(r.dx));r.ip=0x529;break;
        case 0x529:r.di=stackOffset(-4);r.ip=0x52c;break;
        case 0x52c:push(bus,r.ss);r.ip=0x52d;break;
        case 0x52d:push(bus,r.di);r.ip=0x52e;break;
        case 0x52e:al(bus.readByte(r.ss,stackOffset(-9)));r.ip=0x531;break;
        case 0x531:r.ax=lo(r.ax);logic(0,8);r.ip=0x533;break;
        case 0x533:r.di=r.ax;r.ip=0x535;break;
        case 0x535:r.si=r.di;r.ip=0x537;break;
        case 0x537:r.di=shift(r.di,1);r.ip=0x539;break;
        case 0x539:r.di=arithmetic(r.di,r.si,false);r.ip=0x53b;break;
        case 0x53b:r.di=arithmetic(r.di,0x79cf,false);r.ip=0x53f;break;
        case 0x53f:push(bus,r.ds);r.ip=0x540;break;
        case 0x540:push(bus,r.di);r.ip=0x541;break;
        case 0x541:push(bus,3);r.ip=0x543;break;
        case 0x543:farCall(bus,0x90e,0x548);break;
        case 0x548:r.di=stackOffset(-8);r.ip=0x54b;break;
        case 0x54b:push(bus,r.ss);r.ip=0x54c;break;
        case 0x54c:push(bus,r.di);r.ip=0x54d;break;
        case 0x54d:al(bus.readByte(r.ss,stackOffset(-9)));r.ip=0x550;break;
        case 0x550:r.ax=lo(r.ax);logic(0,8);r.ip=0x552;break;
        case 0x552:r.di=r.ax;r.ip=0x554;break;
        case 0x554:r.si=r.di;r.ip=0x556;break;
        case 0x556:r.di=shift(r.di,1);r.ip=0x558;break;
        case 0x558:r.di=arithmetic(r.di,r.si,false);r.ip=0x55a;break;
        case 0x55a:r.di=arithmetic(r.di,0x79d9,false);r.ip=0x55e;break;
        case 0x55e:push(bus,r.ds);r.ip=0x55f;break;
        case 0x55f:push(bus,r.di);r.ip=0x560;break;
        case 0x560:push(bus,3);r.ip=0x562;break;
        case 0x562:farCall(bus,0x90e,0x567);break;
        // Decimal digits use the shared elapsed-time scratch word as a glyph pointer.
        case 0x314b:arithmetic(local(4),0,true);r.ip=0x314f;break;
        case 0x314f:branch(flag(1)||flag(0x40),0x3180,0x3151);break;
        case 0x3151:r.ax=local(6);r.ip=0x3154;break;
        case 0x3154:r.dx=logic(0);r.ip=0x3156;break;
        case 0x3156:r.cx=10;r.ip=0x3159;break;
        case 0x3159:case 0x3176:{const auto value=(uint32_t{r.dx}<<16)|r.ax;if(!r.cx || value/r.cx>65535) throw std::domain_error("HUD DIV left recovered domain");r.ax=static_cast<uint16_t>(value/r.cx);r.dx=static_cast<uint16_t>(value%r.cx);r.ip=static_cast<uint16_t>(r.ip+2u);break;}
        case 0x315b:std::swap(r.ax,r.dx);r.ip=0x315c;break;
        case 0x315c:r.ax=shift(r.ax,6);r.ip=0x315f;break;
        case 0x315f:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0x2070),false);r.ip=0x3163;break;
        case 0x3163:bus.writeWord(r.ds,0x2074,r.ax);r.ip=0x3166;break;
        case 0x3166:call(bus,0x1156,0x3169);break;
        case 0x3169:bus.writeWord(r.ds,0x2072,arithmetic(bus.readWord(r.ds,0x2072),9,true));r.ip=0x316e;break;
        case 0x316e:r.ax=local(6);r.ip=0x3171;break;
        case 0x3171:r.dx=logic(0);r.ip=0x3173;break;
        case 0x3173:r.cx=10;r.ip=0x3176;break;
        case 0x3178:store(6,r.ax);r.ip=0x317b;break;
        case 0x317b:store(4,increment(local(4),true));r.ip=0x317e;break;
        case 0x317e:r.ip=0x314b;break;
        case 0x1156:r.di=bus.readWord(r.ds,0x2072);r.ip=0x115a;break;
        case 0x115a:r.ax=0xa000;r.ip=0x115d;break;
        case 0x115d:push(bus,r.ax);r.ip=0x115e;break;
        case 0x115e:r.es=pop(bus);r.ip=0x115f;break;
        case 0x115f:r.cx=8;r.ip=0x1162;break;
        case 0x1162:r.si=bus.readWord(r.ds,0x2074);r.ip=0x1166;break;
        case 0x1166:push(bus,r.cx);r.ip=0x1167;break;
        case 0x1167:r.cx=4;r.ip=0x116a;break;
        case 0x116a:repeated(bus,copies,true);break;
        case 0x116c:r.di=arithmetic(r.di,0x138,false);r.ip=0x1170;break;
        case 0x1170:r.cx=pop(bus);r.ip=0x1171;break;
        case 0x1171:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x1166,0x1173);break;
        case 0x1173:r.ip=pop(bus);break;
        default:throw std::domain_error("Frame HUD reached an unrecovered instruction");
        }
    }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) {return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};}
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) {return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};}
    FrameHudSnapshot state_;
};

}
