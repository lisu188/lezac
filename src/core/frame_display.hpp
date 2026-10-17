#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <cstdint>
#include <stdexcept>
#include <utility>

namespace lezac::core {

enum class FrameDisplayOutcome { Running, Returned, RuntimeError };
struct FrameDisplaySnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0;
    FrameDisplayOutcome outcome = FrameDisplayOutcome::Running;
    bool operator==(const FrameDisplaySnapshot&) const = default;
};

// Original game:7966..799A and its software Real48 calls, not a general floating-point API.
class FrameDisplayOperation {
public:
    FrameDisplayOperation(DosGetTimeRegisters registers, uint16_t gameSegment) : state_{registers, gameSegment} {
        if (registers.cs != gameSegment || registers.ip != 0x7966 ||
            registers.ds != static_cast<uint16_t>(gameSegment + 0xaa2))
            throw std::invalid_argument("Frame display caller entry differs");
    }
    explicit FrameDisplayOperation(FrameDisplaySnapshot state) : state_(state) {}
    const FrameDisplaySnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != FrameDisplayOutcome::Running; }
    bool returned() const noexcept { return state_.outcome == FrameDisplayOutcome::Returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !finished()) {
            advanceOne(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
            if (state_.registers.cs == state_.gameSegment && state_.registers.ip == 0x799a)
                state_.outcome = FrameDisplayOutcome::Returned;
            if (state_.registers.cs == library() && state_.registers.ip == 0x00e2)
                state_.outcome = FrameDisplayOutcome::RuntimeError;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Arithmetic = 0x8d5;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment + 0x920); }
    static uint8_t lo(uint16_t word) { return static_cast<uint8_t>(word); }
    static uint8_t hi(uint16_t word) { return static_cast<uint8_t>(word >> 8); }
    static void low(uint16_t& word, uint16_t byte) { word = static_cast<uint16_t>((word & 0xff00) | (byte & 255)); }
    static void high(uint16_t& word, uint16_t byte) { word = static_cast<uint16_t>((word & 255) | ((byte & 255) << 8)); }
    bool flag(uint32_t mask) const { return (state_.registers.flags & mask) != 0; }
    static uint32_t valueFlags(uint16_t value, unsigned bits) {
        return (value == 0 ? 0x40u : 0u) | ((value & (1u << (bits - 1))) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value, unsigned bits = 16) {
        value &= static_cast<uint16_t>(bits == 8 ? 255 : 65535);
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | valueFlags(value, bits);
        return value;
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract, unsigned bits = 16, bool carry = false) {
        const uint32_t mask = bits == 8 ? 255u : 65535u, sign = 1u << (bits - 1);
        const uint32_t extra = carry && flag(1) ? 1u : 0u;
        const uint32_t wide = subtract ? uint32_t{left} - right - extra : uint32_t{left} + right + extra;
        const auto value = static_cast<uint16_t>(wide & mask);
        uint32_t flags = valueFlags(value, bits) | (((left ^ right ^ value) & 16) ? 16u : 0u);
        if (subtract ? uint32_t{left} < uint32_t{right} + extra : wide > mask) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & sign) : (~(left ^ right) & (left ^ value) & sign)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | flags;
        return value;
    }
    uint16_t increment(uint16_t value, bool subtract, unsigned bits = 16) {
        const auto carry = state_.registers.flags & 1u;
        value = arithmetic(value, 1, subtract, bits);
        state_.registers.flags = (state_.registers.flags & ~uint32_t{1}) | carry;
        return value;
    }
    uint16_t shift(uint16_t value, bool right, unsigned bits = 16, unsigned count = 1) {
        count &= 31;
        if (!count) return value;
        if (count > bits) throw std::domain_error("Frame display shift left the recovered domain");
        const uint32_t sign = 1u << (bits - 1), mask = bits == 8 ? 255u : 65535u;
        const auto result = static_cast<uint16_t>((right ? uint32_t{value} >> count : uint32_t{value} << count) & mask);
        const bool carry = right ? ((value >> (count - 1)) & 1) : ((value >> (bits - count)) & 1);
        // Pinned DOSBox materializes otherwise undefined shift AF as one.
        const bool overflow = right ? count == 1 && (value & sign) : ((result ^ value) & sign) != 0;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | valueFlags(result, bits) | 16u |
            (carry ? 1u : 0u) | (overflow ? 0x800u : 0u);
        return result;
    }
    uint16_t rotate(uint16_t value, bool right) {
        const uint32_t carry = flag(1) ? 1u : 0u;
        const auto result = static_cast<uint16_t>(right ? (uint32_t{value} >> 1) | (carry << 15) :
            (uint32_t{value} << 1) | carry);
        const bool nextCarry = right ? (value & 1) != 0 : (value & 0x8000) != 0;
        const bool overflow = right ? ((result ^ (uint32_t{result} << 1)) & 0x8000) != 0 :
            ((result & 0x8000) != 0) != nextCarry;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x801}) |
            (nextCarry ? 1u : 0u) | (overflow ? 0x800u : 0u);
        return result;
    }
    void multiply(uint16_t factor, bool byte = false) {
        auto& r = state_.registers;
        const uint32_t product = static_cast<uint32_t>(byte ? lo(r.ax) : r.ax) * factor;
        r.ax = static_cast<uint16_t>(product);
        if (!byte) r.dx = static_cast<uint16_t>(product >> 16);
        const bool overflow = byte ? product > 255 : r.dx != 0;
        // MUL preserves materialized SF/PF/AF, but the pinned host explicitly sets ZF.
        r.flags = (r.flags & ~uint32_t{0x841}) | (overflow ? 0x801u : 0u) |
            ((byte ? lo(r.ax) : r.ax) == 0 ? 0x40u : 0u);
    }
    void advanceOne(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value); };
        const auto pop = [&] { const auto value = bus.readWord(r.ss, r.sp); r.sp = static_cast<uint16_t>(r.sp + 2u); return value; };
        const auto call = [&](uint16_t at, uint16_t next) { push(next); r.ip = at; };
        const auto farCall = [&](uint16_t at, uint16_t next) { push(r.cs); push(next); r.cs = library(); r.ip = at; };
        const auto branch = [&](bool condition, uint16_t yes, uint16_t no) { r.ip = condition ? yes : no; };
        if (r.cs == state_.gameSegment) {
            switch (r.ip) {
            case 0x7966: r.ax = bus.readWord(r.ds, 0x78c6); r.ip = 0x7969; break;
            case 0x7969: r.dx = logic(0); r.ip = 0x796b; break;
            case 0x796b: farCall(0x0f0f, 0x7970); break;
            case 0x7970: push(r.dx); r.ip = 0x7971; break;
            case 0x7971: push(r.bx); r.ip = 0x7972; break;
            case 0x7972: push(r.ax); r.ip = 0x7973; break;
            case 0x7973: r.ax = bus.readWord(r.ds, 0x78c8); r.ip = 0x7976; break;
            case 0x7976: r.dx = logic(0); r.ip = 0x7978; break;
            case 0x7978: farCall(0x0f0f, 0x797d); break;
            case 0x797d: r.cx = pop(); r.ip = 0x797e; break;
            case 0x797e: r.si = pop(); r.ip = 0x797f; break;
            case 0x797f: r.di = pop(); r.ip = 0x7980; break;
            case 0x7980: farCall(0x0f01, 0x7985); break;
            case 0x7985: r.cx = 0x0087; r.ip = 0x7988; break;
            case 0x7988: r.si = logic(0); r.ip = 0x798a; break;
            case 0x798a: r.di = 0x4800; r.ip = 0x798d; break;
            case 0x798d: farCall(0x0efb, 0x7992); break;
            case 0x7992: farCall(0x0f13, 0x7997); break;
            case 0x7997: bus.writeByte(r.ds, 0x79b5, lo(r.ax)); r.ip = 0x799a; break;
            default: throw std::domain_error("Frame display caller reached an unrecovered instruction");
            }
            return;
        }
        if (r.cs != library()) throw std::domain_error("Frame display left its recovered segments");
        switch (r.ip) {
        case 0x0ca5: r.ip = 0x0da6; break;
        case 0x0ca8: logic(lo(r.ax), 8); r.ip = 0x0caa; break;
        case 0x0caa: branch(flag(0x40), 0x0ca5, 0x0cac); break;
        case 0x0cac: logic(lo(r.cx), 8); r.ip = 0x0cae; break;
        case 0x0cae: branch(flag(0x40), 0x0ca5, 0x0cb0); break;
        case 0x0cb0: push(r.bp); r.ip = 0x0cb1; break;
        case 0x0cb1: r.bp = r.dx; r.ip = 0x0cb3; break;
        case 0x0cb3: r.dx = logic(r.dx ^ r.di); r.ip = 0x0cb5; break;
        case 0x0cb5: r.dx = logic(r.dx & 0x8000); r.ip = 0x0cb9; break;
        case 0x0cb9: { const auto al = lo(r.ax); low(r.ax, lo(r.dx)); low(r.dx, al); r.ip = 0x0cbb; break; }
        case 0x0cbb: low(r.dx, arithmetic(lo(r.dx), lo(r.cx), false, 8)); r.ip = 0x0cbd; break;
        case 0x0cbd: high(r.dx, arithmetic(hi(r.dx), lo(r.ax), false, 8, true)); r.ip = 0x0cbf; break;
        case 0x0cbf: low(r.cx, lo(r.ax)); r.ip = 0x0cc1; break;
        case 0x0cc1: r.bp = logic(r.bp | 0x8000); r.ip = 0x0cc5; break;
        case 0x0cc5: r.di = logic(r.di | 0x8000); r.ip = 0x0cc9; break;
        case 0x0cc9: push(r.dx); r.ip = 0x0cca; break;
        case 0x0cca: logic(hi(r.ax), 8); r.ip = 0x0ccc; break;
        case 0x0ccc: branch(!flag(0x40), 0x0cd2, 0x0cce); break;
        case 0x0cce: logic(r.bx); r.ip = 0x0cd0; break;
        case 0x0cd0: branch(flag(0x40), 0x0cdf, 0x0cd2); break;
        case 0x0cd2: logic(hi(r.cx), 8); r.ip = 0x0cd4; break;
        case 0x0cd4: branch(!flag(0x40), 0x0cfe, 0x0cd6); break;
        case 0x0cd6: logic(r.si); r.ip = 0x0cd8; break;
        case 0x0cd8: branch(!flag(0x40), 0x0cfe, 0x0cda); break;
        case 0x0cda: std::swap(r.ax, r.cx); r.ip = 0x0cdb; break;
        case 0x0cdb: std::swap(r.bx, r.si); r.ip = 0x0cdd; break;
        case 0x0cdd: std::swap(r.bp, r.di); r.ip = 0x0cdf; break;
        case 0x0cdf: r.ax = r.bp; r.ip = 0x0ce1; break;
        case 0x0ce1: low(r.ax, hi(r.ax)); r.ip = 0x0ce3; break;
        case 0x0ce3: multiply(hi(r.cx), true); r.ip = 0x0ce5; break;
        case 0x0ce5: r.bx = r.ax; r.ip = 0x0ce7; break;
        case 0x0ce7: r.ax = r.bp; r.ip = 0x0ce9; break;
        case 0x0ce9: multiply(r.si); r.ip = 0x0ceb; break;
        case 0x0ceb: r.bx = arithmetic(r.bx, r.ax, false); r.ip = 0x0ced; break;
        case 0x0ced: r.dx = arithmetic(r.dx, 0, false, 16, true); r.ip = 0x0cf0; break;
        case 0x0cf0: r.cx = r.dx; r.ip = 0x0cf2; break;
        case 0x0cf2: r.ax = r.bp; r.ip = 0x0cf4; break;
        case 0x0cf4: multiply(r.di); r.ip = 0x0cf6; break;
        case 0x0cf6: r.ax = arithmetic(r.ax, r.cx, false); r.ip = 0x0cf8; break;
        case 0x0cf8: r.dx = arithmetic(r.dx, 0, false, 16, true); r.ip = 0x0cfb; break;
        case 0x0cfb: r.ip = 0x0d79; break;
        case 0x0d79: std::swap(r.ax, r.bx); r.ip = 0x0d7a; break;
        case 0x0d7a: r.cx = pop(); r.ip = 0x0d7b; break;
        case 0x0d7b: r.bp = pop(); r.ip = 0x0d7c; break;
        case 0x0d7c: logic(hi(r.dx), 8); r.ip = 0x0d7e; break;
        case 0x0d7e: branch(flag(0x80), 0x0d87, 0x0d80); break;
        case 0x0d80: r.ax = shift(r.ax, false); r.ip = 0x0d82; break;
        case 0x0d82: r.bx = rotate(r.bx, false); r.ip = 0x0d84; break;
        case 0x0d84: r.dx = rotate(r.dx, false); r.ip = 0x0d86; break;
        case 0x0d86: r.cx = increment(r.cx, true); r.ip = 0x0d87; break;
        case 0x0d87: r.cx = arithmetic(r.cx, 0x8081, true); r.ip = 0x0d8b; break;
        case 0x0d8b: r.ax = arithmetic(r.ax, 0x80, false); r.ip = 0x0d8e; break;
        case 0x0d8e: r.bx = arithmetic(r.bx, 0, false, 16, true); r.ip = 0x0d91; break;
        case 0x0d91: r.dx = arithmetic(r.dx, 0, false, 16, true); r.ip = 0x0d94; break;
        case 0x0d94: branch(!flag(1), 0x0d99, 0x0d96); break;
        case 0x0d96: r.dx = rotate(r.dx, true); r.ip = 0x0d98; break;
        case 0x0d98: r.cx = increment(r.cx, false); r.ip = 0x0d99; break;
        case 0x0d99: logic(hi(r.cx) & 0x40, 8); r.ip = 0x0d9c; break;
        case 0x0d9c: branch(!flag(0x40), 0x0da6, 0x0d9e); break;
        case 0x0d9e: r.cx = increment(r.cx, false); r.ip = 0x0d9f; break;
        case 0x0d9f: low(r.ax, lo(r.cx)); r.ip = 0x0da1; break;
        case 0x0da1: high(r.dx, logic(hi(r.dx) ^ hi(r.cx), 8)); r.ip = 0x0da3; break;
        case 0x0da3: high(r.cx, shift(hi(r.cx), true, 8)); r.ip = 0x0da5; break;
        case 0x0da5: case 0x0dac: case 0x0e8c: case 0x0ee1: case 0x0ee3: case 0x0ee8: r.ip = pop(); break;
        case 0x0da6: r.ax = logic(0); r.ip = 0x0da8; break;
        case 0x0da8: r.bx = r.ax; r.ip = 0x0daa; break;
        case 0x0daa: r.dx = r.ax; r.ip = 0x0dac; break;
        case 0x0dad: logic(lo(r.ax), 8); r.ip = 0x0daf; break;
        case 0x0daf: branch(flag(0x40), 0x0da6, 0x0db1); break;
        case 0x0db1: push(r.bp); r.ip = 0x0db2; break;
        case 0x0db2: r.bp = r.dx; r.ip = 0x0db4; break;
        case 0x0db4: r.dx = logic(r.dx ^ r.di); r.ip = 0x0db6; break;
        case 0x0db6: r.di = logic(r.di | 0x8000); r.ip = 0x0dba; break;
        case 0x0dba: r.bp = logic(r.bp | 0x8000); r.ip = 0x0dbe; break;
        case 0x0dbe: r.dx = logic(r.dx & 0x8000); r.ip = 0x0dc2; break;
        case 0x0dc2: { const auto al = lo(r.ax); low(r.ax, lo(r.dx)); low(r.dx, al); r.ip = 0x0dc4; break; }
        case 0x0dc4: low(r.dx, arithmetic(lo(r.dx), lo(r.cx), true, 8)); r.ip = 0x0dc6; break;
        case 0x0dc6: high(r.dx, arithmetic(hi(r.dx), lo(r.ax), true, 8, true)); r.ip = 0x0dc8; break;
        case 0x0dc8: push(r.dx); r.ip = 0x0dc9; break;
        case 0x0dc9: low(r.ax, 2); r.ip = 0x0dcb; break;
        case 0x0dcb: r.dx = 1; r.ip = 0x0dce; break;
        case 0x0dce: arithmetic(r.bp, r.di, true); r.ip = 0x0dd0; break;
        case 0x0dd0: branch(!flag(0x40), 0x0dd8, 0x0dd2); break;
        case 0x0dd2: arithmetic(r.bx, r.si, true); r.ip = 0x0dd4; break;
        case 0x0dd4: branch(!flag(0x40), 0x0dd8, 0x0dd6); break;
        case 0x0dd6: arithmetic(hi(r.ax), hi(r.cx), true, 8); r.ip = 0x0dd8; break;
        case 0x0dd8: branch(flag(1), 0x0de0, 0x0dda); break;
        case 0x0dda: high(r.ax, arithmetic(hi(r.ax), hi(r.cx), true, 8)); r.ip = 0x0ddc; break;
        case 0x0ddc: r.bx = arithmetic(r.bx, r.si, true, 16, true); r.ip = 0x0dde; break;
        case 0x0dde: r.bp = arithmetic(r.bp, r.di, true, 16, true); r.ip = 0x0de0; break;
        case 0x0de0: r.dx = rotate(r.dx, false); r.ip = 0x0de2; break;
        case 0x0de2: branch(flag(1), 0x0df5, 0x0de4); break;
        case 0x0de4: high(r.ax, shift(hi(r.ax), false, 8)); r.ip = 0x0de6; break;
        case 0x0de6: r.bx = rotate(r.bx, false); r.ip = 0x0de8; break;
        case 0x0de8: r.bp = rotate(r.bp, false); r.ip = 0x0dea; break;
        case 0x0dea: branch(!flag(1), 0x0dce, 0x0dec); break;
        case 0x0dec: high(r.ax, arithmetic(hi(r.ax), hi(r.cx), true, 8)); r.ip = 0x0dee; break;
        case 0x0dee: r.bx = arithmetic(r.bx, r.si, true, 16, true); r.ip = 0x0df0; break;
        case 0x0df0: r.bp = arithmetic(r.bp, r.di, true, 16, true); r.ip = 0x0df2; break;
        case 0x0df2: r.flags &= ~uint32_t{1}; r.ip = 0x0df3; break;
        case 0x0df3: r.ip = 0x0de0; break;
        case 0x0df5: low(r.ax, increment(lo(r.ax), true, 8)); r.ip = 0x0df7; break;
        case 0x0df7: branch(flag(0x80), 0x0e03, 0x0df9); break;
        case 0x0df9: push(r.dx); r.ip = 0x0dfa; break;
        case 0x0dfa: r.dx = 1; r.ip = 0x0dfd; break;
        case 0x0dfd: branch(!flag(0x40), 0x0de4, 0x0dff); break;
        case 0x0dff: low(r.dx, 0x40); r.ip = 0x0e01; break;
        case 0x0e01: r.ip = 0x0de4; break;
        case 0x0e03: r.ax = r.dx; r.ip = 0x0e05; break;
        case 0x0e05: low(r.cx, 6); r.ip = 0x0e07; break;
        case 0x0e07: r.ax = shift(r.ax, false, 16, lo(r.cx)); r.ip = 0x0e09; break;
        case 0x0e09: r.bx = pop(); r.ip = 0x0e0a; break;
        case 0x0e0a: r.dx = pop(); r.ip = 0x0e0b; break;
        case 0x0e0b: r.cx = pop(); r.ip = 0x0e0c; break;
        case 0x0e0c: r.bp = pop(); r.ip = 0x0e0d; break;
        case 0x0e0d: r.ax = static_cast<uint16_t>(~r.ax); r.ip = 0x0e0f; break;
        case 0x0e0f: r.bx = static_cast<uint16_t>(~r.bx); r.ip = 0x0e11; break;
        case 0x0e11: r.dx = logic(r.dx ^ 0xffff); r.ip = 0x0e14; break;
        case 0x0e14: branch(flag(0x80), 0x0e1d, 0x0e16); break;
        case 0x0e16: r.ax = rotate(r.ax, false); r.ip = 0x0e18; break;
        case 0x0e18: r.bx = rotate(r.bx, false); r.ip = 0x0e1a; break;
        case 0x0e1a: r.dx = rotate(r.dx, false); r.ip = 0x0e1c; break;
        case 0x0e1c: r.cx = increment(r.cx, true); r.ip = 0x0e1d; break;
        case 0x0e1d: r.cx = arithmetic(r.cx, 0x8080, false); r.ip = 0x0e21; break;
        case 0x0e21: r.ip = 0x0d8b; break;
        case 0x0e4e: r.bx = r.ax; r.ip = 0x0e50; break;
        case 0x0e50: r.bx = logic(r.bx | r.dx); r.ip = 0x0e52; break;
        case 0x0e52: branch(flag(0x40), 0x0e8c, 0x0e54); break;
        case 0x0e54: high(r.cx, hi(r.dx)); r.ip = 0x0e56; break;
        case 0x0e56: logic(r.dx); r.ip = 0x0e58; break;
        case 0x0e58: branch(!flag(0x80), 0x0e64, 0x0e5a); break;
        case 0x0e5a: r.ax = static_cast<uint16_t>(~r.ax); r.ip = 0x0e5c; break;
        case 0x0e5c: r.dx = static_cast<uint16_t>(~r.dx); r.ip = 0x0e5e; break;
        case 0x0e5e: r.ax = arithmetic(r.ax, 1, false); r.ip = 0x0e61; break;
        case 0x0e61: r.dx = arithmetic(r.dx, 0, false, 16, true); r.ip = 0x0e64; break;
        case 0x0e64: r.bx = r.ax; r.ip = 0x0e66; break;
        case 0x0e66: r.ax = 0x00a0; r.ip = 0x0e69; break;
        case 0x0e69: logic(r.dx); r.ip = 0x0e6b; break;
        case 0x0e6b: branch(!flag(0x40), 0x0e79, 0x0e6d); break;
        case 0x0e6d: std::swap(r.bx, r.dx); r.ip = 0x0e6f; break;
        case 0x0e6f: low(r.ax, 0x90); r.ip = 0x0e71; break;
        case 0x0e71: logic(hi(r.dx), 8); r.ip = 0x0e73; break;
        case 0x0e73: branch(!flag(0x40), 0x0e79, 0x0e75); break;
        case 0x0e75: r.dx = static_cast<uint16_t>((r.dx << 8) | (r.dx >> 8)); r.ip = 0x0e77; break;
        case 0x0e77: low(r.ax, 0x88); r.ip = 0x0e79; break;
        case 0x0e79: logic(r.dx); r.ip = 0x0e7b; break;
        case 0x0e7b: branch(flag(0x80), 0x0e85, 0x0e7d); break;
        case 0x0e7d: low(r.ax, increment(lo(r.ax), true, 8)); r.ip = 0x0e7f; break;
        case 0x0e7f: r.bx = arithmetic(r.bx, r.bx, false); r.ip = 0x0e81; break;
        case 0x0e81: r.dx = arithmetic(r.dx, r.dx, false, 16, true); r.ip = 0x0e83; break;
        case 0x0e83: branch(!flag(0x80), 0x0e7d, 0x0e85); break;
        case 0x0e85: logic(hi(r.cx), 8); r.ip = 0x0e87; break;
        case 0x0e87: branch(flag(0x80), 0x0e8c, 0x0e89); break;
        case 0x0e89: high(r.dx, logic(hi(r.dx) & 0x7f, 8)); r.ip = 0x0e8c; break;
        case 0x0e8d: std::swap(r.ax, r.bx); r.ip = 0x0e8e; break;
        case 0x0e8e: low(r.cx, 0x9f); r.ip = 0x0e90; break;
        case 0x0e90: low(r.cx, arithmetic(lo(r.cx), lo(r.bx), true, 8)); r.ip = 0x0e92; break;
        case 0x0e92: branch(flag(1), 0x0ee2, 0x0e94); break;
        case 0x0e94: arithmetic(lo(r.cx), 0x1f, true, 8); r.ip = 0x0e97; break;
        case 0x0e97: branch(!flag(1) && !flag(0x40), 0x0ee4, 0x0e99); break;
        case 0x0e99: low(r.cx, increment(lo(r.cx), false, 8)); r.ip = 0x0e9b; break;
        case 0x0e9b: high(r.bx, hi(r.dx)); r.ip = 0x0e9d; break;
        case 0x0e9d: high(r.dx, logic(hi(r.dx) | 0x80, 8)); r.ip = 0x0ea0; break;
        case 0x0ea0: arithmetic(lo(r.cx), 0x11, true, 8); r.ip = 0x0ea3; break;
        case 0x0ea3: branch(flag(1), 0x0eac, 0x0ea5); break;
        case 0x0ea5: r.ax = r.dx; r.ip = 0x0ea7; break;
        case 0x0ea7: r.dx = logic(0); r.ip = 0x0ea9; break;
        case 0x0ea9: low(r.cx, arithmetic(lo(r.cx), 16, true, 8)); r.ip = 0x0eac; break;
        case 0x0eac: arithmetic(lo(r.cx), 9, true, 8); r.ip = 0x0eaf; break;
        case 0x0eaf: branch(flag(1), 0x0ebc, 0x0eb1); break;
        case 0x0eb1: low(r.ax, hi(r.ax)); r.ip = 0x0eb3; break;
        case 0x0eb3: high(r.ax, lo(r.dx)); r.ip = 0x0eb5; break;
        case 0x0eb5: low(r.dx, hi(r.dx)); r.ip = 0x0eb7; break;
        case 0x0eb7: high(r.dx, logic(0, 8)); r.ip = 0x0eb9; break;
        case 0x0eb9: low(r.cx, arithmetic(lo(r.cx), 8, true, 8)); r.ip = 0x0ebc; break;
        case 0x0ebc: r.dx = shift(r.dx, true); r.ip = 0x0ebe; break;
        case 0x0ebe: r.ax = rotate(r.ax, true); r.ip = 0x0ec0; break;
        case 0x0ec0: low(r.cx, increment(lo(r.cx), true, 8)); r.ip = 0x0ec2; break;
        case 0x0ec2: branch(!flag(0x40), 0x0ebc, 0x0ec4); break;
        case 0x0ec4: branch(!flag(1), 0x0ed2, 0x0ec6); break;
        case 0x0ec6: logic(hi(r.cx), 8); r.ip = 0x0ec8; break;
        case 0x0ec8: branch(flag(0x40), 0x0ed2, 0x0eca); break;
        case 0x0eca: r.ax = arithmetic(r.ax, 1, false); r.ip = 0x0ecd; break;
        case 0x0ecd: r.dx = arithmetic(r.dx, 0, false, 16, true); r.ip = 0x0ed0; break;
        case 0x0ed0: branch(flag(0x80), 0x0ee2, 0x0ed2); break;
        case 0x0ed2: logic(hi(r.bx), 8); r.ip = 0x0ed4; break;
        case 0x0ed4: branch(!flag(0x80), 0x0ee0, 0x0ed6); break;
        case 0x0ed6: r.ax = static_cast<uint16_t>(~r.ax); r.ip = 0x0ed8; break;
        case 0x0ed8: r.dx = static_cast<uint16_t>(~r.dx); r.ip = 0x0eda; break;
        case 0x0eda: r.ax = arithmetic(r.ax, 1, false); r.ip = 0x0edd; break;
        case 0x0edd: r.dx = arithmetic(r.dx, 0, false, 16, true); r.ip = 0x0ee0; break;
        case 0x0ee0: r.flags &= ~uint32_t{1}; r.ip = 0x0ee1; break;
        case 0x0ee2: r.flags |= 1; r.ip = 0x0ee3; break;
        case 0x0ee4: r.ax = logic(0); r.ip = 0x0ee6; break;
        case 0x0ee6: r.dx = logic(0); r.ip = 0x0ee8; break;
        case 0x0efb: call(0x0ca8, 0x0efe); break;
        case 0x0efe: branch(flag(1), 0x0f29, 0x0f00); break;
        case 0x0f00: case 0x0f0a: case 0x0f12: case 0x0f1a: r.ip = pop(); r.cs = pop(); break;
        case 0x0f01: logic(lo(r.cx), 8); r.ip = 0x0f03; break;
        case 0x0f03: branch(flag(0x40), 0x0f2f, 0x0f05); break;
        case 0x0f05: call(0x0dad, 0x0f08); break;
        case 0x0f08: branch(flag(1), 0x0f29, 0x0f0a); break;
        case 0x0f0f: call(0x0e4e, 0x0f12); break;
        case 0x0f13: high(r.cx, 0); r.ip = 0x0f15; break;
        case 0x0f15: call(0x0e8d, 0x0f18); break;
        case 0x0f18: branch(flag(1), 0x0f23, 0x0f1a); break;
        case 0x0f23: r.ax = 207; r.ip = 0x0f26; break;
        case 0x0f26: case 0x0f2c: case 0x0f32: r.ip = 0x00e2; break;
        case 0x0f29: r.ax = 205; r.ip = 0x0f2c; break;
        case 0x0f2f: r.ax = 200; r.ip = 0x0f32; break;
        default: throw std::domain_error("Frame display reached an unrecovered software Real48 instruction");
        }
    }
    FrameDisplaySnapshot state_;
};

}
