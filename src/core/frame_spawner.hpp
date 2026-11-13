#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <stdexcept>
#include <utility>

namespace lezac::core {

enum class FrameSpawnerOutcome { Running, Returned, RuntimeError };
struct FrameSpawnerSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0;
    FrameSpawnerOutcome outcome = FrameSpawnerOutcome::Running;
    bool operator==(const FrameSpawnerSnapshot&) const = default;
};

// Original 7A57..7C3D, including allocation, visual/animation init and Random.
// The caller owns the bus and clock; no actor or spawner snapshots are copied.
class FrameSpawnerOperation {
public:
    FrameSpawnerOperation(DosGetTimeRegisters r, uint16_t game)
        : state_{r, game} {
        if (r.cs != game || r.ds != static_cast<uint16_t>(game + 0xaa2) || r.ip != 0x7a57)
            throw std::invalid_argument("Spawner frame entry differs");
    }
    explicit FrameSpawnerOperation(FrameSpawnerSnapshot state) : state_(state) {}
    const FrameSpawnerSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != FrameSpawnerOutcome::Running; }
    bool returned() const noexcept { return state_.outcome == FrameSpawnerOutcome::Returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t used = 0;
        while (used < budget && !finished()) {
            instruction(bus);
            ++used; ++state_.dispatchedInstructions;
            const auto& r = state_.registers;
            if (r.cs == state_.gameSegment && r.ip == 0x7c3d)
                state_.outcome = FrameSpawnerOutcome::Returned;
            if (r.cs == library() && r.ip == 0xe2)
                state_.outcome = FrameSpawnerOutcome::RuntimeError;
        }
        return used;
    }

private:
    FrameSpawnerSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment + 0x920); }
    uint16_t graphics() const { return static_cast<uint16_t>(state_.gameSegment + 0x8ac); }
    bool flag(uint32_t bit) const { return (state_.registers.flags & bit) != 0; }
    static uint32_t resultFlags(uint16_t value, bool byte) {
        return (value == 0 ? 0x40u : 0u) | (value & (byte ? 0x80 : 0x8000) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract = false,
                        bool byte = false, bool carry = false) {
        const uint32_t mask = byte ? 255u : 65535u, sign = byte ? 128u : 32768u;
        const uint32_t extra = carry && flag(1) ? 1u : 0u;
        const uint32_t wide = subtract ? uint32_t{left} - right - extra : uint32_t{left} + right + extra;
        const auto value = static_cast<uint16_t>(wide & mask);
        uint32_t flags = resultFlags(value, byte) | ((left ^ right ^ value) & 16u);
        if (subtract ? uint32_t{left} < uint32_t{right} + extra : wide > mask) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & sign) :
                       (~(left ^ right) & (left ^ value) & sign)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | flags;
        return value;
    }
    uint16_t logic(uint16_t value, bool byte = false) {
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | resultFlags(value, byte);
        return value;
    }
    uint16_t shift(uint16_t value, unsigned count) {
        auto& r = state_.registers;
        if (!count) return value;
        for (unsigned i = 0; i < count; ++i) {
            const auto carry = value >> 15;
            value = static_cast<uint16_t>(value << 1);
            r.flags = (r.flags & ~uint32_t{1}) | carry;
        }
        r.flags = (r.flags & ~uint32_t{0xc4}) | resultFlags(value, false);
        if (count == 1) r.flags = (r.flags & ~uint32_t{0x800}) |
            (((value >> 15) ^ (r.flags & 1u)) ? 0x800u : 0u);
        return value;
    }
    uint16_t signedMultiply(uint16_t value, int16_t factor) {
        const int32_t product = int32_t{std::bit_cast<int16_t>(value)} * factor;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x801}) |
            (product < -32768 || product > 32767 ? 0x801u : 0u);
        return static_cast<uint16_t>(product);
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto push = [&](uint16_t v) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, v); };
        const auto pop = [&] { const auto v = bus.readWord(r.ss, r.sp); r.sp = static_cast<uint16_t>(r.sp + 2u); return v; };
        const auto local = [&](int offset) { return bus.readWord(r.ss, static_cast<uint16_t>(r.bp + offset)); };
        const auto storeLocal = [&](int offset, uint16_t v) { bus.writeWord(r.ss, static_cast<uint16_t>(r.bp + offset), v); };
        const auto data = [&](uint16_t offset) { return bus.readWord(r.ds, offset); };
        const auto farCall = [&](uint16_t segment, uint16_t ip, uint16_t next) {
            push(r.cs); push(next); r.cs = segment; r.ip = ip;
        };
        const auto nearCall = [&](uint16_t ip, uint16_t next) { push(next); r.ip = ip; };
        const auto branch = [&](bool yes, uint16_t target, uint16_t next) { r.ip = yes ? target : next; };
        const auto les = [&](int offset) { r.di = local(offset); r.es = local(offset + 2); };
        const auto al = [&](uint16_t value) { r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | (value & 255u)); };
        const auto zeroAh = [&] { logic(0, true); r.ax &= 255u; };
        const auto read = [&](unsigned offset) { return bus.readByte(r.es, static_cast<uint16_t>(r.di + offset)); };
        const auto readWord = [&](unsigned offset) { return bus.readWord(r.es, static_cast<uint16_t>(r.di + offset)); };
        const auto write = [&](unsigned offset, uint16_t value) {
            bus.writeByte(r.es, static_cast<uint16_t>(r.di + offset), static_cast<uint8_t>(value));
        };
        const auto writeWord = [&](unsigned offset, uint16_t value) {
            bus.writeWord(r.es, static_cast<uint16_t>(r.di + offset), value);
        };
        const auto increment = [&](uint8_t value, bool decrement) {
            const auto carry = r.flags & 1u;
            const auto result = arithmetic(value, 1, decrement, true);
            r.flags = (r.flags & ~uint32_t{1}) | carry;
            return static_cast<uint8_t>(result);
        };
        const auto cwd = [&] { r.dx = (r.ax & 0x8000) ? 0xffff : 0; };
        const auto signedDivide = [&](uint16_t divisor) {
            const int64_t dividend = std::bit_cast<int32_t>((uint32_t{r.dx} << 16) | r.ax);
            const auto divisorSigned = std::bit_cast<int16_t>(divisor);
            if (!divisorSigned || dividend / divisorSigned < -32768 || dividend / divisorSigned > 32767)
                throw std::domain_error("Spawner allocator IDIV overflow");
            r.ax = static_cast<uint16_t>(dividend / divisorSigned);
            r.dx = static_cast<uint16_t>(dividend % divisorSigned);
        };
        if (r.cs == library()) {
            switch (r.ip) {
            case 0x4df:r.ax=arithmetic(r.ax,0x200);r.ip=0x4e2;break;
            case 0x4e2:branch(flag(1),0x4f1,0x4e4);break;
            case 0x4e4:r.ax=arithmetic(r.ax,r.sp,true);r.ip=0x4e6;break;
            case 0x4e6:branch(!flag(1),0x4f1,0x4e8);break;
            case 0x4e8:r.ax=arithmetic(0,r.ax,true);r.ip=0x4ea;break;
            case 0x4ea:arithmetic(r.ax,data(0x1afa),true);r.ip=0x4ee;break;
            case 0x4ee:branch(flag(1),0x4f1,0x4f0);break;
            case 0x4f0:r.ip=pop();r.cs=pop();break;
            case 0x4f1:r.ax=0xca;r.ip=0x4f4;break;
            case 0x4f4:r.ip=0xe2;break;
            case 0x13a8:nearCall(0x13f7,0x13ab);break;
            case 0x13ab:r.ax=logic(0);r.ip=0x13ad;break;
            case 0x13ad:r.bx=r.sp;r.ip=0x13af;break;
            case 0x13af:r.bx=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+4u));r.ip=0x13b3;break;
            case 0x13b3:logic(r.bx);r.ip=0x13b5;break;
            case 0x13b5:branch(flag(0x40),0x13bb,0x13b7);break;
            case 0x13b7:std::swap(r.ax,r.dx);r.ip=0x13b8;break;
            case 0x13b8: {
                const uint32_t value=(uint32_t{r.dx}<<16)|r.ax;
                if (!r.bx || value/r.bx>65535) throw std::domain_error("Spawner Random DIV overflow");
                r.ax=static_cast<uint16_t>(value/r.bx);r.dx=static_cast<uint16_t>(value%r.bx);r.ip=0x13ba;break;
            }
            case 0x13ba:std::swap(r.ax,r.dx);r.ip=0x13bb;break;
            case 0x13bb:r.ip=pop();r.cs=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;
            case 0x13f7:r.ax=data(0x1afe);r.ip=0x13fa;break;
            case 0x13fa:r.bx=data(0x1b00);r.ip=0x13fe;break;
            case 0x13fe:r.cx=r.ax;r.ip=0x1400;break;
            case 0x1400: {
                const uint32_t value=uint32_t{r.ax}*bus.readWord(r.cs,0x142d);
                r.ax=static_cast<uint16_t>(value);r.dx=static_cast<uint16_t>(value>>16);
                r.flags=(r.flags&~uint32_t{0x801})|(r.dx?0x801u:0u);r.ip=0x1405;break;
            }
            case 0x1405:r.cx=shift(r.cx,1);r.ip=0x1407;break;
            case 0x1407:r.cx=shift(r.cx,1);r.ip=0x1409;break;
            case 0x1409:r.cx=shift(r.cx,1);r.ip=0x140b;break;
            case 0x140b:r.cx=static_cast<uint16_t>((r.cx&255u)|(arithmetic(r.cx>>8,r.cx&255u,false,true)<<8));r.ip=0x140d;break;
            case 0x140d:r.dx=arithmetic(r.dx,r.cx);r.ip=0x140f;break;
            case 0x140f:r.dx=arithmetic(r.dx,r.bx);r.ip=0x1411;break;
            case 0x1411:r.bx=shift(r.bx,1);r.ip=0x1413;break;
            case 0x1413:r.bx=shift(r.bx,1);r.ip=0x1415;break;
            case 0x1415:r.dx=arithmetic(r.dx,r.bx);r.ip=0x1417;break;
            case 0x1417:case 0x141d: {
                const auto next=r.ip==0x1417?0x1419:0x141f;
                r.dx=static_cast<uint16_t>((r.dx&255u)|(arithmetic(r.dx>>8,r.bx&255u,false,true)<<8));
                r.ip=static_cast<uint16_t>(next);break;
            }
            case 0x1419:r.cx=static_cast<uint16_t>((r.cx&0xff00u)|5u);r.ip=0x141b;break;
            case 0x141b:r.bx=shift(r.bx,r.cx&255u);r.ip=0x141d;break;
            case 0x141f:r.ax=arithmetic(r.ax,1);r.ip=0x1422;break;
            case 0x1422:r.dx=arithmetic(r.dx,0,false,false,true);r.ip=0x1425;break;
            case 0x1425:bus.writeWord(r.ds,0x1afe,r.ax);r.ip=0x1428;break;
            case 0x1428:bus.writeWord(r.ds,0x1b00,r.dx);r.ip=0x142c;break;
            case 0x142c:r.ip=pop();break;
            default:throw std::domain_error("Spawner CRT reached an unrecovered instruction");
            }
            return;
        }
        if (r.cs == graphics()) {
            switch (r.ip) {
            case 0x517:push(r.bp);r.ip=0x518;break;
            case 0x518:r.bp=r.sp;r.ip=0x51a;break;
            case 0x51a:r.ax=4;r.ip=0x51d;break;
            case 0x51d:farCall(library(),0x4df,0x522);break;
            case 0x522:r.sp=arithmetic(r.sp,4,true);r.ip=0x525;break;
            case 0x525:arithmetic(bus.readByte(r.ds,0xc496),32,true,true);r.ip=0x52a;break;
            case 0x52a:branch(!flag(1)&&!flag(0x40),0x58e,0x52c);break;
            case 0x52c:al(bus.readByte(r.ds,0xc496));r.ip=0x52f;break;
            case 0x52f:zeroAh();r.ip=0x531;break;
            case 0x531:r.di=r.ax;r.ip=0x533;break;
            case 0x533:r.cx=static_cast<uint16_t>((r.cx&0xff00u)|3u);r.ip=0x535;break;
            case 0x535:r.di=shift(r.di,r.cx&255u);r.ip=0x537;break;
            case 0x537:r.di=arithmetic(r.di,0xc21e);r.ip=0x53b;break;
            case 0x53b:storeLocal(-4,r.di);r.ip=0x53e;break;
            case 0x53e:storeLocal(-2,r.ds);r.ip=0x541;break;
            case 0x541:r.ax=local(8);r.ip=0x544;break;
            case 0x544:les(-4);r.ip=0x547;break;
            case 0x547:writeWord(0,r.ax);r.ip=0x54a;break;
            case 0x54a:r.ax=local(6);r.ip=0x54d;break;
            case 0x54d:les(-4);r.ip=0x550;break;
            case 0x550:writeWord(2,r.ax);r.ip=0x554;break;
            case 0x554:r.di=local(10);r.ip=0x557;break;
            case 0x557:r.di=shift(r.di,1);r.ip=0x559;break;
            case 0x559:r.di=shift(r.di,1);r.ip=0x55b;break;
            case 0x55b:r.ax=data(static_cast<uint16_t>(r.di+0xc324));r.ip=0x55f;break;
            case 0x55f:les(-4);r.ip=0x562;break;
            case 0x562:writeWord(6,r.ax);r.ip=0x566;break;
            case 0x566:r.di=local(10);r.ip=0x569;break;
            case 0x569:r.di=shift(r.di,1);r.ip=0x56b;break;
            case 0x56b:r.di=shift(r.di,1);r.ip=0x56d;break;
            case 0x56d:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0xc322)));r.ip=0x571;break;
            case 0x571:les(-4);r.ip=0x574;break;
            case 0x574:write(4,r.ax);r.ip=0x578;break;
            case 0x578:r.di=local(10);r.ip=0x57b;break;
            case 0x57b:r.di=shift(r.di,1);r.ip=0x57d;break;
            case 0x57d:r.di=shift(r.di,1);r.ip=0x57f;break;
            case 0x57f:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0xc323)));r.ip=0x583;break;
            case 0x583:les(-4);r.ip=0x586;break;
            case 0x586:write(5,r.ax);r.ip=0x58a;break;
            case 0x58a:bus.writeByte(r.ds,0xc496,increment(bus.readByte(r.ds,0xc496),false));r.ip=0x58e;break;
            case 0x58e:r.sp=r.bp;r.ip=0x590;break;
            case 0x590:r.bp=pop();r.ip=0x591;break;
            case 0x591:r.ip=pop();r.cs=pop();r.sp=static_cast<uint16_t>(r.sp+6u);break;
            default:throw std::domain_error("Spawner visual constructor left recovered code");
            }
            return;
        }
        if (r.cs != state_.gameSegment) throw std::domain_error("Spawner left recovered code");
        switch (r.ip) {
        case 0x7a57:bus.writeByte(r.ds,0x79e8,0);r.ip=0x7a5c;break;
        case 0x7a5c:bus.writeByte(r.ds,0x79e9,0);r.ip=0x7a61;break;
        case 0x7a61:bus.writeByte(r.ds,0x79ae,0);r.ip=0x7a66;break;
        case 0x7a66:bus.writeByte(r.ds,0x79af,0);r.ip=0x7a6b;break;
        case 0x7a6b:arithmetic(bus.readByte(r.ds,0x79a6),0,true,true);r.ip=0x7a70;break;
        case 0x7a70:branch(!flag(1)&&!flag(0x40),0x7a75,0x7a72);break;
        case 0x7a72:r.ip=0x7c3d;break;
        case 0x7a75:bus.writeWord(r.ds,0x2082,1);r.ip=0x7a7b;break;
        case 0x7a7b:al(bus.readByte(r.ds,0x79a6));r.ip=0x7a7e;break;
        case 0x7a7e:zeroAh();r.ip=0x7a80;break;
        case 0x7a80:arithmetic(r.ax,data(0x2082),true);r.ip=0x7a84;break;
        case 0x7a84:branch(!flag(1),0x7a89,0x7a86);break;
        case 0x7a86:r.ip=0x7c3d;break;
        case 0x7a89:r.di=signedMultiply(data(0x2082),30);r.ip=0x7a8e;break;
        case 0x7a8e:r.di=arithmetic(r.di,0x74a8);r.ip=0x7a92;break;
        case 0x7a92:storeLocal(-4,r.di);r.ip=0x7a95;break;
        case 0x7a95:storeLocal(-2,r.ds);r.ip=0x7a98;break;
        case 0x7a98:les(-4);r.ip=0x7a9b;break;
        case 0x7a9b:write(27,increment(read(27),true));r.ip=0x7a9f;break;
        case 0x7a9f:les(-4);r.ip=0x7aa2;break;
        case 0x7aa2:arithmetic(read(27),0,true,true);r.ip=0x7aa7;break;
        case 0x7aa7:branch(flag(0x40),0x7aac,0x7aa9);break;
        case 0x7aa9:r.ip=0x7c36;break;
        case 0x7aac:les(-4);r.ip=0x7aaf;break;
        case 0x7aaf:arithmetic(read(10),0,true,true);r.ip=0x7ab4;break;
        case 0x7ab4:branch(!flag(1)&&!flag(0x40),0x7ab9,0x7ab6);break;
        case 0x7ab6:r.ip=0x7c36;break;
        case 0x7ab9:les(-4);r.ip=0x7abc;break;
        case 0x7abc:arithmetic(read(9),0,true,true);r.ip=0x7ac1;break;
        case 0x7ac1:branch(!flag(1)&&!flag(0x40),0x7ac6,0x7ac3);break;
        case 0x7ac3:r.ip=0x7c36;break;
        case 0x7ac6:les(-4);r.ip=0x7ac9;break;
        case 0x7ac9:arithmetic(read(8),1,true,true);r.ip=0x7ace;break;
        case 0x7ace:branch(flag(0x40),0x7ad3,0x7ad0);break;
        case 0x7ad0:r.ip=0x7c36;break;
        case 0x7ad3:les(-4);r.ip=0x7ad6;break;
        case 0x7ad6:al(read(28));r.ip=0x7ada;break;
        case 0x7ada:les(-4);r.ip=0x7add;break;
        case 0x7add:write(27,r.ax);r.ip=0x7ae1;break;
        case 0x7ae1:les(-4);r.ip=0x7ae4;break;
        case 0x7ae4:al(read(11));r.ip=0x7ae8;break;
        case 0x7ae8:zeroAh();r.ip=0x7aea;break;
        case 0x7aea:r.di=r.ax;r.ip=0x7aec;break;
        case 0x7aec:r.di=shift(r.di,1);r.ip=0x7aee;break;
        case 0x7aee:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x80)));r.ip=0x7af2;break;
        case 0x7af2:zeroAh();r.ip=0x7af4;break;
        case 0x7af4:r.di=r.ax;r.ip=0x7af6;break;
        case 0x7af6:r.di=shift(r.di,1);r.ip=0x7af8;break;
        case 0x7af8:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x58)));r.ip=0x7afc;break;
        case 0x7afc:bus.writeByte(r.ds,0x79a3,static_cast<uint8_t>(r.ax));r.ip=0x7aff;break;
        case 0x7aff:les(-4);r.ip=0x7b02;break;
        case 0x7b02:push(readWord(0));r.ip=0x7b05;break;
        case 0x7b05:les(-4);r.ip=0x7b08;break;
        case 0x7b08:push(readWord(2));r.ip=0x7b0c;break;
        case 0x7b0c:push(0);r.ip=0x7b0e;break;
        case 0x7b0e:push(0);r.ip=0x7b10;break;
        case 0x7b10:al(bus.readByte(r.ds,0x79a3));r.ip=0x7b13;break;
        case 0x7b13:zeroAh();r.ip=0x7b15;break;
        case 0x7b15:push(r.ax);r.ip=0x7b16;break;
        case 0x7b16:les(-4);r.ip=0x7b19;break;
        case 0x7b19:al(read(11));r.ip=0x7b1d;break;
        case 0x7b1d:push(r.ax);r.ip=0x7b1e;break;
        case 0x7b1e:push(0);r.ip=0x7b20;break;
        case 0x7b20:les(-4);r.ip=0x7b23;break;
        case 0x7b23:al(read(26));r.ip=0x7b27;break;
        case 0x7b27:push(r.ax);r.ip=0x7b28;break;
        case 0x7b28:nearCall(0x2f9f,0x7b2b);break;
        case 0x7b2b:arithmetic(data(0x2072),1,true);r.ip=0x7b30;break;
        case 0x7b30:branch(flag(0x40),0x7b35,0x7b32);break;
        case 0x7b32:r.ip=0x7c36;break;
        case 0x7b35:les(-4);r.ip=0x7b38;break;
        case 0x7b38:write(9,increment(read(9),true));r.ip=0x7b3c;break;
        case 0x7b3c:les(-4);r.ip=0x7b3f;break;
        case 0x7b3f:write(10,increment(read(10),true));r.ip=0x7b43;break;
        case 0x7b43:al(bus.readByte(r.ds,0x208d));r.ip=0x7b46;break;
        case 0x7b46:zeroAh();r.ip=0x7b48;break;
        case 0x7b48:r.di=signedMultiply(r.ax,38);r.ip=0x7b4b;break;
        case 0x7b4b:r.di=arithmetic(r.di,0x1bae);r.ip=0x7b4f;break;
        case 0x7b4f:storeLocal(-8,r.di);r.ip=0x7b52;break;
        case 0x7b52:storeLocal(-6,r.ds);r.ip=0x7b55;break;
        case 0x7b55:les(-4);r.ip=0x7b58;break;
        case 0x7b58:push(readWord(14));r.ip=0x7b5c;break;
        case 0x7b5c:farCall(library(),0x13a8,0x7b61);break;
        case 0x7b61:les(-4);r.ip=0x7b64;break;
        case 0x7b64:r.ax=arithmetic(r.ax,readWord(12));r.ip=0x7b68;break;
        case 0x7b68:les(-8);r.ip=0x7b6b;break;
        case 0x7b6b:writeWord(14,r.ax);r.ip=0x7b6f;break;
        case 0x7b6f:les(-4);r.ip=0x7b72;break;
        case 0x7b72:push(readWord(18));r.ip=0x7b76;break;
        case 0x7b76:farCall(library(),0x13a8,0x7b7b);break;
        case 0x7b7b:les(-4);r.ip=0x7b7e;break;
        case 0x7b7e:r.ax=arithmetic(r.ax,readWord(16));r.ip=0x7b82;break;
        case 0x7b82:les(-8);r.ip=0x7b85;break;
        case 0x7b85:writeWord(16,r.ax);r.ip=0x7b89;break;
        case 0x7b89:les(-4);r.ip=0x7b8c;break;
        case 0x7b8c:push(readWord(22));r.ip=0x7b90;break;
        case 0x7b90:farCall(library(),0x13a8,0x7b95);break;
        case 0x7b95:les(-4);r.ip=0x7b98;break;
        case 0x7b98:r.ax=arithmetic(r.ax,readWord(20));r.ip=0x7b9c;break;
        case 0x7b9c:les(-8);r.ip=0x7b9f;break;
        case 0x7b9f:writeWord(18,r.ax);r.ip=0x7ba3;break;
        case 0x7ba3:les(-4);r.ip=0x7ba6;break;
        case 0x7ba6:al(read(25));r.ip=0x7baa;break;
        case 0x7baa:zeroAh();r.ip=0x7bac;break;
        case 0x7bac:push(r.ax);r.ip=0x7bad;break;
        case 0x7bad:farCall(library(),0x13a8,0x7bb2);break;
        case 0x7bb2:r.dx=r.ax;r.ip=0x7bb4;break;
        case 0x7bb4:les(-4);r.ip=0x7bb7;break;
        case 0x7bb7:al(read(24));r.ip=0x7bbb;break;
        case 0x7bbb:zeroAh();r.ip=0x7bbd;break;
        case 0x7bbd:r.ax=arithmetic(r.ax,r.dx);r.ip=0x7bbf;break;
        case 0x7bbf:les(-8);r.ip=0x7bc2;break;
        case 0x7bc2:write(36,r.ax);r.ip=0x7bc6;break;
        case 0x7bc6:les(-4);r.ip=0x7bc9;break;
        case 0x7bc9:al(read(11));r.ip=0x7bcd;break;
        case 0x7bcd:zeroAh();r.ip=0x7bcf;break;
        case 0x7bcf:r.di=r.ax;r.ip=0x7bd1;break;
        case 0x7bd1:r.di=shift(r.di,1);r.ip=0x7bd3;break;
        case 0x7bd3:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x80)));r.ip=0x7bd7;break;
        case 0x7bd7:les(-8);r.ip=0x7bda;break;
        case 0x7bda:write(3,r.ax);r.ip=0x7bde;break;
        case 0x7bde:les(-4);r.ip=0x7be1;break;
        case 0x7be1:al(read(11));r.ip=0x7be5;break;
        case 0x7be5:zeroAh();r.ip=0x7be7;break;
        case 0x7be7:r.di=r.ax;r.ip=0x7be9;break;
        case 0x7be9:r.di=shift(r.di,1);r.ip=0x7beb;break;
        case 0x7beb:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x81)));r.ip=0x7bef;break;
        case 0x7bef:les(-8);r.ip=0x7bf2;break;
        case 0x7bf2:write(4,r.ax);r.ip=0x7bf6;break;
        case 0x7bf6:les(-8);r.ip=0x7bf9;break;
        case 0x7bf9:r.di=arithmetic(r.di,22);r.ip=0x7bfd;break;
        case 0x7bfd:push(r.es);r.ip=0x7bfe;break;
        case 0x7bfe:push(r.di);r.ip=0x7bff;break;
        case 0x7bff:al(bus.readByte(r.ds,0x79a3));r.ip=0x7c02;break;
        case 0x7c02:push(r.ax);r.ip=0x7c03;break;
        case 0x7c03:les(-4);r.ip=0x7c06;break;
        case 0x7c06:al(read(11));r.ip=0x7c0a;break;
        case 0x7c0a:zeroAh();r.ip=0x7c0c;break;
        case 0x7c0c:r.di=r.ax;r.ip=0x7c0e;break;
        case 0x7c0e:r.di=shift(r.di,1);r.ip=0x7c10;break;
        case 0x7c10:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x80)));r.ip=0x7c14;break;
        case 0x7c14:zeroAh();r.ip=0x7c16;break;
        case 0x7c16:r.di=r.ax;r.ip=0x7c18;break;
        case 0x7c18:r.di=shift(r.di,1);r.ip=0x7c1a;break;
        case 0x7c1a:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0x59)));r.ip=0x7c1e;break;
        case 0x7c1e:push(r.ax);r.ip=0x7c1f;break;
        case 0x7c1f:les(-4);r.ip=0x7c22;break;
        case 0x7c22:al(read(29));r.ip=0x7c26;break;
        case 0x7c26:push(r.ax);r.ip=0x7c27;break;
        case 0x7c27:push(1);r.ip=0x7c29;break;
        case 0x7c29:nearCall(0x6ab,0x7c2c);break;
        case 0x7c2c:al(bus.readByte(r.ds,0x2082));r.ip=0x7c2f;break;
        case 0x7c2f:les(-8);r.ip=0x7c32;break;
        case 0x7c32:write(37,r.ax);r.ip=0x7c36;break;
        case 0x7c36: {
            const auto carry=r.flags&1u;bus.writeWord(r.ds,0x2082,arithmetic(data(0x2082),1));
            r.flags=(r.flags&~uint32_t{1})|carry;r.ip=0x7c3a;break;
        }
        case 0x7c3a:r.ip=0x7a7b;break;
        case 0x2f9f:push(r.bp);r.ip=0x2fa0;break;
        case 0x2fa0:r.bp=r.sp;r.ip=0x2fa2;break;
        case 0x2fa2:r.ax=4;r.ip=0x2fa5;break;
        case 0x2fa5:farCall(library(),0x4df,0x2faa);break;
        case 0x2faa:r.sp=arithmetic(r.sp,4,true);r.ip=0x2fad;break;
        case 0x2fad:arithmetic(bus.readByte(r.ds,0x208d),30,true,true);r.ip=0x2fb2;break;
        case 0x2fb2:branch(flag(1),0x2fb7,0x2fb4);break;
        case 0x2fb4:r.ip=0x309a;break;
        case 0x2fb7:bus.writeByte(r.ds,0x208d,increment(bus.readByte(r.ds,0x208d),false));r.ip=0x2fbb;break;
        case 0x2fbb:bus.writeWord(r.ds,0x2072,1);r.ip=0x2fc1;break;
        case 0x2fc1:r.ax=local(14);r.ip=0x2fc4;break;
        case 0x2fc4:cwd();r.ip=0x2fc5;break;
        case 0x2fc5:r.ax=logic(r.ax^r.dx);r.ip=0x2fc7;break;
        case 0x2fc7:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x2fc9;break;
        case 0x2fc9:arithmetic(r.ax,0x7ff,true);r.ip=0x2fcc;break;
        case 0x2fcc:branch(flag(0x40)||(flag(0x80)!=flag(0x800)),0x2fe1,0x2fce);break;
        case 0x2fce:r.ax=local(14);r.ip=0x2fd1;break;
        case 0x2fd1:cwd();r.ip=0x2fd2;break;
        case 0x2fd2:r.ax=logic(r.ax^r.dx);r.ip=0x2fd4;break;
        case 0x2fd4:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x2fd6;break;
        case 0x2fd6:cwd();r.ip=0x2fd7;break;
        case 0x2fd7:signedDivide(local(14));r.ip=0x2fda;break;
        case 0x2fda:r.ax=signedMultiply(r.ax,0x7ff);r.ip=0x2fde;break;
        case 0x2fde:storeLocal(14,r.ax);r.ip=0x2fe1;break;
        case 0x2fe1:r.ax=local(12);r.ip=0x2fe4;break;
        case 0x2fe4:cwd();r.ip=0x2fe5;break;
        case 0x2fe5:r.ax=logic(r.ax^r.dx);r.ip=0x2fe7;break;
        case 0x2fe7:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x2fe9;break;
        case 0x2fe9:arithmetic(r.ax,0x7ff,true);r.ip=0x2fec;break;
        case 0x2fec:branch(flag(0x40)||(flag(0x80)!=flag(0x800)),0x3001,0x2fee);break;
        case 0x2fee:r.ax=local(12);r.ip=0x2ff1;break;
        case 0x2ff1:cwd();r.ip=0x2ff2;break;
        case 0x2ff2:r.ax=logic(r.ax^r.dx);r.ip=0x2ff4;break;
        case 0x2ff4:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x2ff6;break;
        case 0x2ff6:cwd();r.ip=0x2ff7;break;
        case 0x2ff7:signedDivide(local(12));r.ip=0x2ffa;break;
        case 0x2ffa:r.ax=signedMultiply(r.ax,0x7ff);r.ip=0x2ffe;break;
        case 0x2ffe:storeLocal(12,r.ax);r.ip=0x3001;break;
        case 0x3001:al(bus.readByte(r.ds,0x208d));r.ip=0x3004;break;
        case 0x3004:zeroAh();r.ip=0x3006;break;
        case 0x3006:r.di=signedMultiply(r.ax,38);r.ip=0x3009;break;
        case 0x3009:r.di=arithmetic(r.di,0x1bae);r.ip=0x300d;break;
        case 0x300d:storeLocal(-4,r.di);r.ip=0x3010;break;
        case 0x3010:storeLocal(-2,r.ds);r.ip=0x3013;break;
        case 0x3013:les(-4);r.ip=0x3016;break;
        case 0x3016:r.ax=logic(0);r.ip=0x3018;break;
        case 0x3018:writeWord(10,r.ax);r.ip=0x301c;break;
        case 0x301c:les(-4);r.ip=0x301f;break;
        case 0x301f:r.ax=logic(0);r.ip=0x3021;break;
        case 0x3021:writeWord(12,r.ax);r.ip=0x3025;break;
        case 0x3025:al(bus.readByte(r.ds,0xc496));r.ip=0x3028;break;
        case 0x3028:les(-4);r.ip=0x302b;break;
        case 0x302b:write(1,r.ax);r.ip=0x302f;break;
        case 0x302f:r.ax=local(14);r.ip=0x3032;break;
        case 0x3032:les(-4);r.ip=0x3035;break;
        case 0x3035:writeWord(6,r.ax);r.ip=0x3039;break;
        case 0x3039:r.ax=local(12);r.ip=0x303c;break;
        case 0x303c:les(-4);r.ip=0x303f;break;
        case 0x303f:writeWord(8,r.ax);r.ip=0x3043;break;
        case 0x3043:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+8u)));r.ip=0x3046;break;
        case 0x3046:les(-4);r.ip=0x3049;break;
        case 0x3049:write(0,r.ax);r.ip=0x304c;break;
        case 0x304c:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+6u)));r.ip=0x304f;break;
        case 0x304f:les(-4);r.ip=0x3052;break;
        case 0x3052:write(2,r.ax);r.ip=0x3056;break;
        case 0x3056:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+4u)));r.ip=0x3059;break;
        case 0x3059:les(-4);r.ip=0x305c;break;
        case 0x305c:write(21,r.ax);r.ip=0x3060;break;
        case 0x3060:arithmetic(local(10),31,true);r.ip=0x3064;break;
        case 0x3064:branch(flag(0x40),0x3082,0x3066);break;
        case 0x3066:r.di=local(10);r.ip=0x3069;break;
        case 0x3069:r.di=shift(r.di,2);r.ip=0x306c;break;
        case 0x306c:al(bus.readByte(r.ds,static_cast<uint16_t>(r.di+0xc323)));r.ip=0x3070;break;
        case 0x3070:zeroAh();r.ip=0x3072;break;
        case 0x3072:r.dx=r.ax;r.ip=0x3074;break;
        case 0x3074:r.ax=16;r.ip=0x3077;break;
        case 0x3077:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x3079;break;
        case 0x3079:les(-4);r.ip=0x307c;break;
        case 0x307c:write(20,r.ax);r.ip=0x3080;break;
        case 0x3080:r.ip=0x308a;break;
        case 0x3082:les(-4);r.ip=0x3085;break;
        case 0x3085:write(20,0);r.ip=0x308a;break;
        case 0x308a:push(local(10));r.ip=0x308d;break;
        case 0x308d:push(local(18));r.ip=0x3090;break;
        case 0x3090:push(local(16));r.ip=0x3093;break;
        case 0x3093:farCall(graphics(),0x517,0x3098);break;
        case 0x3098:r.ip=0x309f;break;
        case 0x309a:r.ax=logic(0);r.ip=0x309c;break;
        case 0x309c:bus.writeWord(r.ds,0x2072,r.ax);r.ip=0x309f;break;
        case 0x309f:r.sp=r.bp;r.bp=pop();r.ip=0x30a0;break;
        case 0x30a0:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+16u);break;
        case 0x6ab:push(r.bp);r.ip=0x6ac;break;
        case 0x6ac:r.bp=r.sp;r.ip=0x6ae;break;
        case 0x6ae:r.ax=4;r.ip=0x6b1;break;
        case 0x6b1:farCall(library(),0x4df,0x6b6);break;
        case 0x6b6:r.sp=arithmetic(r.sp,4,true);r.ip=0x6b9;break;
        case 0x6b9:les(12);r.ip=0x6bc;break;
        case 0x6bc:storeLocal(-4,r.di);r.ip=0x6bf;break;
        case 0x6bf:storeLocal(-2,r.es);r.ip=0x6c2;break;
        case 0x6c2:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+10u)));r.ip=0x6c5;break;
        case 0x6c5:les(-4);r.ip=0x6c8;break;
        case 0x6c8:write(0,r.ax);r.ip=0x6cb;break;
        case 0x6cb:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+10u)));r.ip=0x6ce;break;
        case 0x6ce:les(-4);r.ip=0x6d1;break;
        case 0x6d1:write(1,r.ax);r.ip=0x6d5;break;
        case 0x6d5:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+8u)));r.ip=0x6d8;break;
        case 0x6d8:les(-4);r.ip=0x6db;break;
        case 0x6db:write(2,r.ax);r.ip=0x6df;break;
        case 0x6df:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+6u)));r.ip=0x6e2;break;
        case 0x6e2:les(-4);r.ip=0x6e5;break;
        case 0x6e5:write(4,r.ax);r.ip=0x6e9;break;
        case 0x6e9:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+4u)));r.ip=0x6ec;break;
        case 0x6ec:les(-4);r.ip=0x6ef;break;
        case 0x6ef:write(5,r.ax);r.ip=0x6f3;break;
        case 0x6f3:les(-4);r.ip=0x6f6;break;
        case 0x6f6:write(6,1);r.ip=0x6fb;break;
        case 0x6fb:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+6u)));r.ip=0x6fe;break;
        case 0x6fe:les(-4);r.ip=0x701;break;
        case 0x701:write(3,r.ax);r.ip=0x705;break;
        case 0x705:r.sp=r.bp;r.bp=pop();r.ip=0x706;break;
        case 0x706:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+12u);break;
        default:throw std::domain_error("Spawner caller reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
