#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <optional>
#include <stdexcept>

namespace lezac::core {

enum class CrtKeyboardOutcome { Running, Returned, BreakOutput };
struct CrtKeyboardSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0, callbackBase=0;
    uint32_t idToggleMask=0;
    CrtKeyboardOutcome outcome=CrtKeyboardOutcome::Running;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0, biosCallbacks=0, timerInstructions=0, timerDeliveries=0;
    bool lastBiosReadEmpty=false;
    bool operator==(const CrtKeyboardSnapshot&) const = default;
};

// Original CRT:02FD..0330 and CheckBreak:0143..015C, plus pinned BIOS INT16.
// Console output/INT23 after the break-flush handoff are not implemented here.
class CrtKeyboardOperation {
public:
    CrtKeyboardOperation(DosGetTimeRegisters r,uint16_t callbackBase,uint16_t game,uint32_t idToggle)
        :state_{r,game,callbackBase,idToggle} {
        if(r.cs!=static_cast<uint16_t>(game+0x84a) || r.ds!=static_cast<uint16_t>(game+0xaa2) ||
            (r.ip!=0x2fd && r.ip!=0x30f) || callbackBase>0xffec || (idToggle!=0 && idToggle!=0x200000))
            throw std::invalid_argument("CRT keyboard entry differs from the recovered profile");
    }
    explicit CrtKeyboardOperation(CrtKeyboardSnapshot state):state_(state) {}
    const CrtKeyboardSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return !state_.timer && state_.outcome!=CrtKeyboardOutcome::Running;}
    bool returned() const noexcept {return finished() && state_.outcome==CrtKeyboardOutcome::Returned;}
    bool interruptInProgress() const noexcept {return state_.timer.has_value();}
    DosGetTimeRegisters registers() const {
        if(!state_.timer) return state_.registers;
        const auto& r=state_.timer->registers;
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    // The original BIOS conversion changes the caller's word even for a non-enhanced key.
    static bool enhancedKey(uint16_t& key) {
        const auto scan=static_cast<uint8_t>(key>>8),ascii=static_cast<uint8_t>(key);
        if(scan==0xe0) {
            key=static_cast<uint16_t>(ascii | (ascii==0x0a || ascii==0x0d ? 0x1c00u : 0x3500u));
            return false;
        }
        if(scan>0x84 || (ascii==0xf0 && scan)) return true;
        if(scan && ascii==0xe0) key&=0xff00;
        return false;
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if(state_.timer || !(state_.registers.flags&0x200u))
            throw std::logic_error("CRT keyboard timer is not eligible");
        auto& r=state_.registers;
        push(bus,static_cast<uint16_t>(r.flags));push(bus,r.cs);push(bus,r.ip);
        r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
        state_.timer=TimerIrqOperation({r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags},
            state_.gameSegment,state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t consumed=0;
        while(consumed<budget && !finished()) {
            if(state_.timer) {
                TimerIrqOperation timer(*state_.timer);
                if(timer.advance(1,bus)!=1) throw std::domain_error("CRT keyboard timer did not dispatch");
                ++state_.timerInstructions;
                if(timer.returned()) {
                    const auto& r=timer.snapshot().registers;
                    state_.registers={r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
                    state_.timer.reset();
                } else state_.timer=timer.snapshot();
            } else instruction(bus);
            ++consumed;++state_.dispatchedInstructions;
        }
        return consumed;
    }
private:
    void push(const TimerIrqBus& bus,uint16_t value) {
        auto& r=state_.registers;r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value);
    }
    uint16_t pop(const TimerIrqBus& bus) {
        auto& r=state_.registers;const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value;
    }
    void al(uint8_t value) {state_.registers.ax=static_cast<uint16_t>((state_.registers.ax&0xff00u)|value);}
    void ah(uint8_t value) {state_.registers.ax=static_cast<uint16_t>((state_.registers.ax&0xffu)|(uint16_t{value}<<8));}
    void byteFlags(uint8_t left,uint8_t right,bool subtract) {
        const auto value=static_cast<uint8_t>(subtract ? left-right : left|right);
        uint32_t flags=(value==0?0x40u:0u)|((value&0x80u)?0x80u:0u)|
            (std::popcount(value)%2==0?4u:0u);
        if(subtract) {
            if(left<right) flags|=1;
            if((left^right^value)&0x10u) flags|=0x10;
            if((left^right)&(left^value)&0x80u) flags|=0x800;
        }
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|flags;
    }
    uint16_t nextHead(const TimerIrqBus& bus,uint16_t head) const {
        const auto start=bus.readWord(0x40,0x80),end=bus.readWord(0x40,0x82);
        if(start!=0x1e || end!=0x3e || head<start || head>=end || (head&1u))
            throw std::domain_error("BIOS keyboard ring differs from the pinned VGA profile");
        const auto next=static_cast<uint16_t>(head+2u);return next>=end?start:next;
    }
    void bios(const TimerIrqBus& bus) {
        // FE38 executes the host service atomically; the empty-read NOP/jump loop remains explicit.
        auto& r=state_.registers;
        const auto function=static_cast<uint8_t>(r.ax>>8);
        if(function!=0 && function!=1) throw std::domain_error("Unrecovered BIOS INT16 function");
        const auto flagsOffset=static_cast<uint16_t>(r.sp+4u);
        auto saved=bus.readWord(r.ss,flagsOffset);
        if(function==1) saved|=0x200;
        bool found=false;
        for(unsigned attempts=0;attempts<16;++attempts) {
            const auto head=bus.readWord(0x40,0x1a),tail=bus.readWord(0x40,0x1c);
            if(head==tail) break;
            auto key=bus.readWord(0x40,head);
            if(function==0 || enhancedKey(key)) {
                bus.writeWord(0x40,0x1a,nextHead(bus,head));
                if(function==1) continue;
                key=bus.readWord(0x40,head);
                if(enhancedKey(key)) break;
            }
            r.ax=key;found=true;break;
        }
        if(function==1) {
            saved=static_cast<uint16_t>((saved&~uint16_t{0x40})|(found?0u:0x40u));
            bus.writeWord(r.ss,flagsOffset,saved);
        }
        state_.lastBiosReadEmpty=function==0 && !found;
        r.ip=static_cast<uint16_t>(state_.callbackBase+(state_.lastBiosReadEmpty?6u:5u));
        ++state_.biosCallbacks;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        if(r.cs==0xf000) {
            const auto offset=static_cast<uint16_t>(r.ip-state_.callbackBase);
            if(offset==0) {r.flags|=0x200;++r.ip;return;}
            if(offset==1) {bios(bus);return;}
            if(offset==5) {
                const auto ip=pop(bus),cs=pop(bus),flags=pop(bus);
                const uint32_t mask=0x7fd5u|state_.idToggleMask;
                r.flags=(r.flags&~mask)|(uint32_t{flags}&mask)|2u;r.cs=cs;r.ip=ip;return;
            }
            if(offset>=6 && offset<=17) {++r.ip;return;}
            if(offset==18) {r.ip=static_cast<uint16_t>(state_.callbackBase+1u);return;}
            throw std::domain_error("BIOS keyboard callback left recovered code");
        }
        if(r.cs!=static_cast<uint16_t>(state_.gameSegment+0x84a))
            throw std::domain_error("CRT keyboard left recovered code");
        switch(r.ip) {
        case 0x2fd:byteFlags(bus.readByte(r.ds,0x7f6d),0,true);r.ip=0x302;break;
        case 0x302:r.ip=(r.flags&0x40u)?0x304:0x30c;break;
        case 0x304:ah(1);r.ip=0x306;break;
        case 0x306:case 0x31d:case 0x152:case 0x158: {
            if(bus.readWord(0,0x58)!=state_.callbackBase || bus.readWord(0,0x5a)!=0xf000)
                throw std::domain_error("CRT keyboard INT16 vector differs");
            const auto next=static_cast<uint16_t>(r.ip+2u);
            push(bus,static_cast<uint16_t>(r.flags));push(bus,r.cs);push(bus,next);
            r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=state_.callbackBase;break;
        }
        case 0x308:al(0);r.ip=0x30a;break;
        case 0x30a:r.ip=(r.flags&0x40u)?0x30e:0x30c;break;
        case 0x30c:al(1);r.ip=0x30e;break;
        case 0x30e:case 0x330: {
            const auto ip=pop(bus),cs=pop(bus);r.ip=ip;r.cs=cs;state_.outcome=CrtKeyboardOutcome::Returned;break;
        }
        case 0x30f:al(bus.readByte(r.ds,0x7f6d));r.ip=0x312;break;
        case 0x312:bus.writeByte(r.ds,0x7f6d,0);r.ip=0x317;break;
        case 0x317:byteFlags(static_cast<uint8_t>(r.ax),static_cast<uint8_t>(r.ax),false);r.ip=0x319;break;
        case 0x319:r.ip=(r.flags&0x40u)?0x31b:0x32d;break;
        case 0x31b:ah(0);byteFlags(0,0,false);r.ip=0x31d;break;
        case 0x31f:byteFlags(static_cast<uint8_t>(r.ax),static_cast<uint8_t>(r.ax),false);r.ip=0x321;break;
        case 0x321:r.ip=(r.flags&0x40u)?0x323:0x32d;break;
        case 0x323:bus.writeByte(r.ds,0x7f6d,static_cast<uint8_t>(r.ax>>8));r.ip=0x327;break;
        case 0x327:byteFlags(static_cast<uint8_t>(r.ax>>8),static_cast<uint8_t>(r.ax>>8),false);r.ip=0x329;break;
        case 0x329:r.ip=(r.flags&0x40u)?0x32b:0x32d;break;
        case 0x32b:al(3);r.ip=0x32d;break;
        case 0x32d:push(bus,0x330);r.ip=0x143;break;
        case 0x143:byteFlags(bus.readByte(r.ds,0x7f6e),0,true);r.ip=0x148;break;
        case 0x148:r.ip=(r.flags&0x40u)?0x14a:0x14b;break;
        case 0x14a:r.ip=pop(bus);break;
        case 0x14b:bus.writeByte(r.ds,0x7f6e,0);r.ip=0x150;break;
        case 0x150:ah(1);r.ip=0x152;break;
        case 0x154:r.ip=(r.flags&0x40u)?0x15c:0x156;if(r.ip==0x15c) state_.outcome=CrtKeyboardOutcome::BreakOutput;break;
        case 0x156:ah(0);r.ip=0x158;break;
        case 0x15a:r.ip=0x150;break;
        default:throw std::domain_error("CRT keyboard reached an unrecovered instruction");
        }
    }
    CrtKeyboardSnapshot state_;
};

}
