#pragma once

#include "core/frame_hud.hpp"
#include "core/player_start.hpp"

#include <variant>

namespace lezac::core {

enum class FrameWaitingOutcome { Running, Completed, EndRun, RuntimeError };
using FrameWaitingCallee = std::variant<std::monostate, FrameHudSnapshot,
    FrameDrawingSnapshot, PlayerStartSnapshot>;
struct FrameWaitingSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint32_t idToggleMask = 0;
    FrameWaitingOutcome outcome = FrameWaitingOutcome::Running;
    FrameWaitingCallee callee;
    std::optional<TimerIrqSnapshot> timer = std::nullopt;
    uint64_t dispatchedInstructions = 0, timerInstructions = 0, timerDeliveries = 0, stringTransfers = 0;
    bool operator==(const FrameWaitingSnapshot&) const = default;
};

// Original two-player prepass 7C3D..7EBB, including its real drawing/placement
// callees. Entry into 1B14 is an explicit UI handoff, not a completed end run.
class FrameWaitingOperation {
public:
    using CopyBudget = FrameHudOperation::CopyBudget;
    FrameWaitingOperation(DosGetTimeRegisters r, uint16_t game, uint32_t idToggle)
        : state_{r, game, idToggle, FrameWaitingOutcome::Running, std::monostate{}} {
        if (r.cs != game || r.ds != static_cast<uint16_t>(game + 0xaa2) ||
            r.ip != 0x7c3d || (idToggle != 0 && idToggle != 0x200000))
            throw std::invalid_argument("Waiting prepass entry differs");
    }
    explicit FrameWaitingOperation(FrameWaitingSnapshot state) : state_(state) {
        if (state_.timer && !std::holds_alternative<std::monostate>(state_.callee) &&
            !std::holds_alternative<PlayerStartSnapshot>(state_.callee))
            throw std::invalid_argument("Waiting prepass has conflicting IRQ owners");
    }
    const FrameWaitingSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != FrameWaitingOutcome::Running && !state_.timer; }
    bool completed() const noexcept { return finished() && state_.outcome == FrameWaitingOutcome::Completed; }
    DosGetTimeRegisters registers() const {
        if (state_.timer) return fromTimer(state_.timer->registers);
        return std::visit([&](const auto& child) -> DosGetTimeRegisters {
            using Child = std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child, FrameHudSnapshot>) return FrameHudOperation(child).registers();
            else if constexpr (std::is_same_v<Child, FrameDrawingSnapshot>) return FrameDrawingOperation(child).registers();
            else if constexpr (std::is_same_v<Child, PlayerStartSnapshot>) return child.registers;
            else return state_.registers;
        }, state_.callee);
    }
    bool interruptInProgress() const {
        if (state_.timer) return true;
        return std::visit([](const auto& child) {
            using Child = std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child, FrameHudSnapshot>) return FrameHudOperation(child).interruptInProgress();
            else if constexpr (std::is_same_v<Child, FrameDrawingSnapshot>) return FrameDrawingOperation(child).interruptInProgress();
            else return false;
        }, state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || interruptInProgress() || !(registers().flags & 0x200u))
            throw std::logic_error("Waiting prepass IRQ is not eligible");
        if (auto* hud = std::get_if<FrameHudSnapshot>(&state_.callee)) {
            FrameHudOperation operation(*hud); operation.deliverTimerInterrupt(bus); *hud = operation.snapshot();
        } else if (auto* drawing = std::get_if<FrameDrawingSnapshot>(&state_.callee)) {
            FrameDrawingOperation operation(*drawing); operation.deliverTimerInterrupt(bus); *drawing = operation.snapshot();
        } else {
            auto r = registers();
            const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value); };
            push(static_cast<uint16_t>(r.flags)); push(r.cs); push(r.ip);
            r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = 0xfea5;
            state_.timer = TimerIrqOperation(toTimer(r), state_.gameSegment, state_.idToggleMask).snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus, const CopyBudget& copies) {
        uint64_t used = 0;
        while (used < budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation timer(*state_.timer);
                if (timer.advance(1, bus) != 1) throw std::domain_error("Waiting IRQ did not dispatch");
                ++state_.timerInstructions;
                if (timer.returned()) {
                    const auto r = fromTimer(timer.snapshot().registers);
                    if (auto* start = std::get_if<PlayerStartSnapshot>(&state_.callee)) start->registers = r;
                    else state_.registers = r;
                    state_.timer.reset();
                } else state_.timer = timer.snapshot();
            } else if (!std::holds_alternative<std::monostate>(state_.callee)) {
                bool done = false;
                std::visit([&](auto& child) {
                    using Child = std::remove_cvref_t<decltype(child)>;
                    if constexpr (!std::is_same_v<Child, std::monostate>) {
                        if constexpr (std::is_same_v<Child, PlayerStartSnapshot>) {
                            PlayerStartOperation operation(child);
                            if (operation.advance(1, bus) != 1) throw std::domain_error("Waiting placement did not dispatch");
                            child = operation.snapshot(); done = operation.finished();
                            if (done) finishCallee(child.registers, operation.returned());
                        } else {
                            using Operation = std::conditional_t<std::is_same_v<Child, FrameHudSnapshot>, FrameHudOperation, FrameDrawingOperation>;
                            Operation operation(child); const bool timer = operation.interruptInProgress();
                            const auto transfers = child.stringTransfers;
                            if (operation.advance(1, bus, copies) != 1) throw std::domain_error("Waiting drawing did not dispatch");
                            if (timer) ++state_.timerInstructions;
                            child = operation.snapshot(); state_.stringTransfers += child.stringTransfers - transfers;
                            done = operation.finished();
                            if (done) finishCallee(operation.registers(), operation.returned());
                        }
                    }
                }, state_.callee);
                if (done) state_.callee = std::monostate{};
            } else {
                instruction(bus);
                if (state_.registers.cs == state_.gameSegment && state_.registers.ip == 0x7ebb)
                    state_.outcome = FrameWaitingOutcome::Completed;
            }
            ++used; ++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    static constexpr uint32_t Arithmetic = 0x8d5;
    static uint8_t lo(uint16_t value) { return static_cast<uint8_t>(value); }
    static uint32_t resultFlags(uint16_t value, unsigned bits) {
        return (value == 0 ? 0x40u : 0u) | (value & (1u << (bits - 1)) ? 0x80u : 0u) |
            (std::popcount(lo(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract = false, unsigned bits = 16) {
        const uint32_t mask = bits == 8 ? 255u : 65535u, sign = 1u << (bits - 1);
        const uint32_t wide = subtract ? uint32_t{left} - right : uint32_t{left} + right;
        const auto value = static_cast<uint16_t>(wide & mask);
        uint32_t flags = resultFlags(value, bits) | (((left ^ right ^ value) & 16u) ? 16u : 0u);
        if (subtract ? left < right : wide > mask) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & sign) : (~(left ^ right) & (left ^ value) & sign)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | flags;
        return value;
    }
    uint16_t increment(uint16_t value, bool down = false, unsigned bits = 16) {
        const auto carry = state_.registers.flags & 1u;
        const auto result = arithmetic(value, 1, down, bits);
        state_.registers.flags = (state_.registers.flags & ~uint32_t{1}) | carry;
        return result;
    }
    uint16_t shift(uint16_t value, unsigned count, bool right = false) {
        const auto before = value;
        const auto carry = right ? (value >> (count - 1)) & 1u : (value >> (16 - count)) & 1u;
        value = static_cast<uint16_t>(right ? value >> count : uint32_t{value} << count);
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | resultFlags(value, 16) | 16u | carry |
            ((right ? before : before ^ value) & 0x8000u ? 0x800u : 0u);
        return value;
    }
    uint16_t signedMultiply(uint16_t value, int factor) {
        const int32_t product = int32_t{std::bit_cast<int16_t>(value)} * factor;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x801}) |
            (product < -32768 || product > 32767 ? 0x801u : 0u);
        return static_cast<uint16_t>(product);
    }
    void finishCallee(DosGetTimeRegisters r, bool returned) {
        state_.registers = r;
        if (!returned) state_.outcome = FrameWaitingOutcome::RuntimeError;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (r.cs != state_.gameSegment) throw std::domain_error("Waiting prepass left recovered code");
        const auto flag = [&](uint32_t bit) { return (r.flags & bit) != 0; };
        const auto al = [&](uint8_t value) { r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | value); };
        const auto at = [&](int delta) { return static_cast<uint16_t>(r.bp + delta); };
        const auto local = [&](int delta) { return bus.readWord(r.ss, at(delta)); };
        const auto store = [&](int delta, uint16_t value) { bus.writeWord(r.ss, at(delta), value); };
        const auto les = [&](int delta) { r.di = local(delta); r.es = local(delta + 2); };
        const auto player = [&] { return bus.readWord(r.ds, 0x2082); };
        const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value); };
        const auto branch = [&](bool yes, uint16_t target, uint16_t next) { r.ip = yes ? target : next; };
        const auto call = [&](uint16_t target, uint16_t next) {
            push(next); r.ip = target;
            if (target == 0x326e || target == 0x29db)
                state_.callee = FrameHudOperation(r, 0, state_.gameSegment, state_.idToggleMask).snapshot();
            else if (target == 0x7c5) state_.callee = FrameDrawingOperation(r, state_.gameSegment, state_.idToggleMask).snapshot();
            else if (target == 0x56b) state_.callee = PlayerStartOperation(r, state_.gameSegment).snapshot();
            else if (target == 0x1b14) state_.outcome = FrameWaitingOutcome::EndRun;
            else throw std::domain_error("Waiting prepass called unrecovered code");
        };
        switch (r.ip) {
        case 0x7c3d:bus.writeWord(r.ds,0x2082,1);r.ip=0x7c43;break;
        case 0x7c43:r.ip=0x7c49;break;
        case 0x7c45:bus.writeWord(r.ds,0x2082,increment(player()));r.ip=0x7c49;break;
        case 0x7c49:case 0x7c54:case 0x7c5f:case 0x7ca7:case 0x7caf:case 0x7cba:case 0x7d2a:case 0x7d38:case 0x7d44:case 0x7d52:case 0x7d5e:case 0x7d6c:case 0x7d78:case 0x7ddb:case 0x7e94:r.di=player();r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7c4d:arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x1b75)),0,true,8);r.ip=0x7c52;break;
        case 0x7c52:branch(flag(1)||flag(0x40),0x7c77,0x7c54);break;
        case 0x7c58:arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x79e5)),1,true,8);r.ip=0x7c5d;break;
        case 0x7c5d:branch(!flag(0x40),0x7c77,0x7c5f);break;
        case 0x7c63:r.di=shift(r.di,1);r.ip=0x7c65;break;
        case 0x7c65:r.ax=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0x79f2));r.ip=0x7c69;break;
        case 0x7c69:r.ax=arithmetic(r.ax,121);r.ip=0x7c6c;break;
        case 0x7c6c:case 0x7c73:case 0x7cdb:case 0x7d1f:push(r.ax);++r.ip;break;
        case 0x7c6d:push(163);r.ip=0x7c70;break;
        case 0x7c70:case 0x7d1c:al(bus.readByte(r.ds,0x2082));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7c74:call(0x326e,0x7c77);break;
        case 0x7c77:case 0x7ce9:case 0x7d11:case 0x7de9:case 0x7ea7:r.di=signedMultiply(player(),38);r.ip=static_cast<uint16_t>(r.ip+5u);break;
        case 0x7c7c:case 0x7d16:r.di=arithmetic(r.di,0x1b62);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7c80:store(-4,r.di);r.ip=0x7c83;break;
        case 0x7c83:store(-2,r.ds);r.ip=0x7c86;break;
        case 0x7c86:case 0x7c93:case 0x7c9a:case 0x7e82:case 0x7e8c:les(-4);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7c89:arithmetic(bus.readByte(r.es,static_cast<uint16_t>(r.di+21)),2,true,8);r.ip=0x7c8e;break;
        case 0x7c8e:branch(flag(0x40),0x7c93,0x7c90);break;
        case 0x7c90:case 0x7ca4:case 0x7d0e:r.ip=0x7db5;break;
        case 0x7c96:{const auto a=static_cast<uint16_t>(r.di+16);bus.writeWord(r.es,a,increment(bus.readWord(r.es,a),true));r.ip=0x7c9a;break;}
        case 0x7c9d:arithmetic(bus.readWord(r.es,static_cast<uint16_t>(r.di+16)),0,true);r.ip=0x7ca2;break;
        case 0x7ca2:branch(flag(0x40),0x7ca7,0x7ca4);break;
        case 0x7cab:{const auto a=static_cast<uint16_t>(r.di+0x79e9);bus.writeByte(r.ds,a,lo(increment(bus.readByte(r.ds,a),true,8)));r.ip=0x7caf;break;}
        case 0x7cb3:arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x79e9)),255,true,8);r.ip=0x7cb8;break;
        case 0x7cb8:branch(!flag(0x40),0x7d11,0x7cba);break;
        case 0x7cbe:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x79e5),0);r.ip=0x7cc3;break;
        case 0x7cc3:bus.writeByte(r.ds,0x79b8,lo(increment(bus.readByte(r.ds,0x79b8),true,8)));r.ip=0x7cc7;break;
        case 0x7cc7:bus.writeWord(r.ds,0x78cc,arithmetic(bus.readWord(r.ds,0x78cc),6));r.ip=0x7ccc;break;
        case 0x7ccc:arithmetic(bus.readByte(r.ds,0x79b8),1,true,8);r.ip=0x7cd1;break;
        case 0x7cd1:branch(!flag(0x40),0x7ce9,0x7cd3);break;
        case 0x7cd3:case 0x7d81:r.ax=player();r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7cd6:case 0x7d84:r.ax=increment(r.ax,true);++r.ip;break;
        case 0x7cd7:r.ax=signedMultiply(r.ax,160);r.ip=0x7cdb;break;
        case 0x7cdc:case 0x7ce4:push(0);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x7cde:case 0x7ce1:push(160);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7ce6:call(0x7c5,0x7ce9);break;
        case 0x7cee:case 0x7dee:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x1b63)));r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7cf2:case 0x7df2:r.ax=lo(r.ax);r.flags=(r.flags&~Arithmetic)|resultFlags(0,8);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x7cf4:case 0x7d85:case 0x7df4:r.di=r.ax;r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x7cf6:case 0x7d87:case 0x7df6:r.di=shift(r.di,3);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7cf9:bus.writeWord(r.ds,static_cast<uint16_t>(r.di+0xc21e),10000);r.ip=0x7cff;break;
        case 0x7cff:arithmetic(bus.readByte(r.ds,0x79b8),0,true,8);r.ip=0x7d04;break;
        case 0x7d04:branch(!flag(0x40),0x7d0e,0x7d06);break;
        case 0x7d06:push(1);r.ip=0x7d08;break;
        case 0x7d08:call(0x1b14,0x7d0b);break;
        case 0x7d1a:push(r.ds);r.ip=0x7d1b;break;
        case 0x7d1b:push(r.di);r.ip=0x7d1c;break;
        case 0x7d20:call(0x56b,0x7d23);break;
        case 0x7d23:push(player());r.ip=0x7d27;break;
        case 0x7d27:call(0x29db,0x7d2a);break;
        case 0x7d2e:case 0x7d3c:case 0x7d48:case 0x7d56:case 0x7d62:case 0x7d70:r.di=shift(r.di,2);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7d31:case 0x7d4b:case 0x7d65:{const auto n=r.ip==0x7d31?100:r.ip==0x7d4b?10:2;const auto a=r.ip==0x7d31?0x1b68:r.ip==0x7d4b?0x1b69:0x1b6a;arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(r.di+a)),static_cast<uint16_t>(n),true,8);r.ip=static_cast<uint16_t>(r.ip+5u);break;}
        case 0x7d36:branch(!flag(1),0x7d44,0x7d38);break;
        case 0x7d50:branch(!flag(1),0x7d5e,0x7d52);break;
        case 0x7d6a:branch(!flag(1),0x7d78,0x7d6c);break;
        case 0x7d3f:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x1b68),100);r.ip=0x7d44;break;
        case 0x7d59:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x1b69),10);r.ip=0x7d5e;break;
        case 0x7d73:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x1b6a),2);r.ip=0x7d78;break;
        case 0x7d7c:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x79e5),2);r.ip=0x7d81;break;
        case 0x7d8a:case 0x7df9:r.di=arithmetic(r.di,0xc21e);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7d8e:case 0x7dfd:store(-8,r.di);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7d91:case 0x7e00:store(-6,r.ds);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7d94:r.ax=bus.readWord(r.ds,0xc3c0);r.ip=0x7d97;break;
        case 0x7d97:case 0x7da5:case 0x7dad:case 0x7e03:case 0x7e17:case 0x7e63:case 0x7e6d:les(-8);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7d9a:bus.writeWord(r.es,static_cast<uint16_t>(r.di+6),r.ax);r.ip=0x7d9e;break;
        case 0x7d9e:case 0x7dca:arithmetic(bus.readByte(r.ds,0x79ca),0,true,8);r.ip=static_cast<uint16_t>(r.ip+5u);break;
        case 0x7da3:branch(!flag(0x40),0x7db5,0x7da5);break;
        case 0x7da8:case 0x7db0:bus.writeByte(r.es,static_cast<uint16_t>(r.di+(r.ip==0x7da8?4:5)),1);r.ip=static_cast<uint16_t>(r.ip+5u);break;
        case 0x7db5:arithmetic(player(),1,true);r.ip=0x7dba;break;
        case 0x7dba:branch(!flag(0x40),0x7dc4,0x7dbc);break;
        case 0x7dbc:case 0x7dc4:al(bus.readByte(r.ds,r.ip==0x7dbc?0x1b7b:0x1b80));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7dbf:case 0x7dc7:bus.writeByte(r.ds,0x79a3,lo(r.ax));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7dc2:r.ip=0x7dca;break;
        case 0x7dcf:branch(!flag(0x40),0x7ddb,0x7dd1);break;
        case 0x7dd1:bus.writeByte(r.ds,0x79a3,0);r.ip=0x7dd6;break;
        case 0x7dd6:bus.writeByte(r.ds,0x79b9,229);r.ip=0x7ddb;break;
        case 0x7ddf:arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x79e5)),2,true,8);r.ip=0x7de4;break;
        case 0x7de4:branch(flag(0x40),0x7de9,0x7de6);break;
        case 0x7de6:r.ip=0x7eb1;break;
        case 0x7e06:r.ax=bus.readWord(r.es,static_cast<uint16_t>(r.di+2u));r.ip=0x7e0a;break;
        case 0x7e0a:r.ax=arithmetic(r.ax,7);r.ip=0x7e0d;break;
        case 0x7e0d:case 0x7e1d:r.ax=shift(r.ax,3,true);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7e10:case 0x7e46:case 0x7e56:r.ax=increment(r.ax);++r.ip;break;
        case 0x7e11:{const uint32_t v=uint32_t{r.ax}*bus.readWord(r.ds,0xc204);r.ax=static_cast<uint16_t>(v);r.dx=static_cast<uint16_t>(v>>16);r.flags=(r.flags&~uint32_t{0x801})|(r.dx?0x801u:0u);r.ip=0x7e15;break;}
        case 0x7e15:r.dx=r.ax;r.ip=0x7e17;break;
        case 0x7e1a:r.ax=bus.readWord(r.es,r.di);r.ip=0x7e1d;break;
        case 0x7e20:r.ax=arithmetic(r.ax,r.dx);r.ip=0x7e22;break;
        case 0x7e22:bus.writeWord(r.ds,0x2074,r.ax);r.ip=0x7e25;break;
        case 0x7e25:case 0x7e34:case 0x7e43:case 0x7e53:r.ax=bus.readWord(r.ds,0x2074);r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x7e28:case 0x7e37:case 0x7e47:case 0x7e57:r.di=bus.readWord(r.ds,0xc1e0);r.es=bus.readWord(r.ds,0xc1e2);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7e2c:case 0x7e3b:case 0x7e4b:case 0x7e5b:r.di=arithmetic(r.di,r.ax);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x7e2e:case 0x7e4d:arithmetic(bus.readByte(r.es,r.di),1,true,8);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7e32:branch(flag(1),0x7e43,0x7e34);break;
        case 0x7e3d:case 0x7e5d:arithmetic(bus.readByte(r.es,r.di),76,true,8);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x7e41:branch(flag(1)||flag(0x40),0x7e6d,0x7e43);break;
        case 0x7e51:branch(flag(1),0x7e74,0x7e53);break;
        case 0x7e61:branch(!flag(1)&&!flag(0x40),0x7e74,0x7e63);break;
        case 0x7e66:arithmetic(bus.readWord(r.es,static_cast<uint16_t>(r.di+2)),24,true);r.ip=0x7e6b;break;
        case 0x7e6b:branch(flag(1)||flag(0x40),0x7e74,0x7e6d);break;
        case 0x7e70:{const auto a=static_cast<uint16_t>(r.di+2);bus.writeWord(r.es,a,increment(bus.readWord(r.es,a),true));r.ip=0x7e74;break;}
        case 0x7e74:arithmetic(bus.readByte(r.ds,0x79a3),1,true,8);r.ip=0x7e79;break;
        case 0x7e79:branch(!flag(0x40),0x7eb1,0x7e7b);break;
        case 0x7e7b:arithmetic(player(),1,true);r.ip=0x7e80;break;
        case 0x7e80:branch(!flag(0x40),0x7e8c,0x7e82);break;
        case 0x7e85:case 0x7e8f:bus.writeByte(r.es,static_cast<uint16_t>(r.di+21),r.ip==0x7e85?0:1);r.ip=static_cast<uint16_t>(r.ip+5u);break;
        case 0x7e8a:r.ip=0x7e94;break;
        case 0x7e98:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x79e5),1);r.ip=0x7e9d;break;
        case 0x7e9d:case 0x7ea2:bus.writeByte(r.ds,r.ip==0x7e9d?0x1b7b:0x1b80,0);r.ip=static_cast<uint16_t>(r.ip+5u);break;
        case 0x7eac:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x1b86),100);r.ip=0x7eb1;break;
        case 0x7eb1:arithmetic(player(),2,true);r.ip=0x7eb6;break;
        case 0x7eb6:branch(flag(0x40),0x7ebb,0x7eb8);break;
        case 0x7eb8:r.ip=0x7c45;break;
        default:throw std::domain_error("Waiting prepass reached an unrecovered instruction");
        }
    }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    FrameWaitingSnapshot state_;
};

} // namespace lezac::core
