#pragma once

#include "core/frame_camera.hpp"
#include "core/frame_view_copy.hpp"
#include "core/frame_world_raster.hpp"

#include <variant>
#include <type_traits>

namespace lezac::core {

enum class FrameRenderOutcome { Running, Returned, RuntimeError };
struct FrameRenderSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint64_t dispatchedInstructions=0,transferredWords=0;
    std::variant<std::monostate,FrameCameraSnapshot,FrameWorldRasterSnapshot,FrameViewCopySnapshot> callee;
    FrameRenderOutcome outcome=FrameRenderOutcome::Running;
    bool operator==(const FrameRenderSnapshot&) const = default;
};

// Original 7A13..7A57, including every camera/raster/copy instruction on one bus.
class FrameRenderOperation {
public:
    using CopyBudget=FrameWorldRasterOperation::CopyBudget;
    FrameRenderOperation(DosGetTimeRegisters r,uint16_t game):state_{r,game,0,0,{}} {
        if(r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x7a13)
            throw std::invalid_argument("Render caller entry differs");
    }
    explicit FrameRenderOperation(FrameRenderSnapshot state):state_(state) {}
    const FrameRenderSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return state_.outcome!=FrameRenderOutcome::Running;}
    bool returned() const noexcept {return state_.outcome==FrameRenderOutcome::Returned;}
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while(used<budget && !finished()) {
            instruction(bus,copies);++used;++state_.dispatchedInstructions;
            if(std::holds_alternative<std::monostate>(state_.callee) &&
                    state_.registers.cs==state_.gameSegment && state_.registers.ip==0x7a57)
                state_.outcome=FrameRenderOutcome::Returned;
        }
        return used;
    }
private:
    FrameRenderSnapshot state_;
    void compareByte(uint8_t value) {
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5}) |
            (value==0?0x40u:0u)|(value&0x80?0x80u:0u)|
            (std::popcount(value)%2==0?4u:0u);
    }
    template<class Operation,class Snapshot>
    void advanceCallee(Snapshot snapshot,const TimerIrqBus& bus,const CopyBudget& copies) {
        Operation operation(snapshot);
        if constexpr(std::is_same_v<Operation,FrameCameraOperation>) {
            if(operation.advance(1,bus)!=1) throw std::domain_error("Camera did not dispatch");
            if(operation.finished() && !operation.returned()) state_.outcome=FrameRenderOutcome::RuntimeError;
        } else {
            if(operation.advance(1,bus,copies)!=1) throw std::domain_error("Raster/copy did not dispatch");
            state_.transferredWords+=operation.snapshot().transferredWords-snapshot.transferredWords;
        }
        state_.registers=operation.snapshot().registers;
        if(operation.returned()) state_.callee=std::monostate{};
        else state_.callee=operation.snapshot();
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        if(const auto* s=std::get_if<FrameCameraSnapshot>(&state_.callee)) {
            advanceCallee<FrameCameraOperation>(*s,bus,copies);return;
        }
        if(const auto* s=std::get_if<FrameWorldRasterSnapshot>(&state_.callee)) {
            advanceCallee<FrameWorldRasterOperation>(*s,bus,copies);return;
        }
        if(const auto* s=std::get_if<FrameViewCopySnapshot>(&state_.callee)) {
            advanceCallee<FrameViewCopyOperation>(*s,bus,copies);return;
        }
        auto& r=state_.registers;
        if(r.cs!=state_.gameSegment) throw std::domain_error("Render caller left recovered code");
        const auto push=[&](uint16_t value) {r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value);};
        const auto camera=[&](uint16_t next) {
            push(next);r.ip=0x3587;state_.callee=FrameCameraOperation(r,state_.gameSegment).snapshot();
        };
        const auto driver=[&](uint16_t ip,uint16_t next) {
            push(r.cs);push(next);r.cs=static_cast<uint16_t>(state_.gameSegment+0x8ac);r.ip=ip;
            if(ip==0xf4) state_.callee=FrameWorldRasterOperation(r,state_.gameSegment).snapshot();
            else state_.callee=FrameViewCopyOperation(r,state_.gameSegment).snapshot();
        };
        switch(r.ip) {
        case 0x7a13:compareByte(bus.readByte(r.ds,0x79e6));r.ip=0x7a18;break;
        case 0x7a18:r.ip=r.flags&0x40?0x7a35:0x7a1a;break;
        case 0x7a1a:push(bus.readWord(r.ds,0xc21e));r.ip=0x7a1e;break;
        case 0x7a1e:push(bus.readWord(r.ds,0xc220));r.ip=0x7a22;break;
        case 0x7a22:camera(0x7a25);break;
        case 0x7a25:driver(0xf4,0x7a2a);break;
        case 0x7a2a:r.ax=bus.readWord(r.ds,0x79f0);r.ip=0x7a2d;break;
        case 0x7a2d:bus.writeWord(r.ds,0xc1f4,r.ax);r.ip=0x7a30;break;
        case 0x7a30:driver(0x3c8,0x7a35);break;
        case 0x7a35:compareByte(bus.readByte(r.ds,0x79e7));r.ip=0x7a3a;break;
        case 0x7a3a:r.ip=r.flags&0x40?0x7a57:0x7a3c;break;
        case 0x7a3c:push(bus.readWord(r.ds,0xc226));r.ip=0x7a40;break;
        case 0x7a40:push(bus.readWord(r.ds,0xc228));r.ip=0x7a44;break;
        case 0x7a44:camera(0x7a47);break;
        case 0x7a47:driver(0xf4,0x7a4c);break;
        case 0x7a4c:r.ax=bus.readWord(r.ds,0x79f2);r.ip=0x7a4f;break;
        case 0x7a4f:bus.writeWord(r.ds,0xc1f4,r.ax);r.ip=0x7a52;break;
        case 0x7a52:driver(0x3c8,0x7a57);break;
        default:throw std::domain_error("Render caller reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
