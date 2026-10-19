#include "core/actor_motion_prefix.hpp"
#include "core/actor_motion.hpp"

#include <bit>
#include <stdexcept>

namespace lezac::core {

ActorMotionPrefixResult actorMotionPrefix(const ActorMotionPrefixInput& input,
        std::span<const uint8_t,512> animationBytes) {
    constexpr uint16_t game=0x1000,data=0x1aa2,stackSegment=0x7000,actorSegment=0x5000;
    constexpr uint16_t bp=0x3fdc,sp=bp-58,actorOffset=0x1bd4;
    std::array<uint8_t,4096> stack{};
    auto actor=input.actor;
    auto shared=input.shared;
    auto randomSeed=input.randomSeed;
    constexpr std::array<uint16_t,3> sharedOffsets{0xc1e8,0x2072,0x2074};
    const auto byte=[&](uint16_t segment,uint16_t offset) -> uint8_t {
        if (segment==stackSegment && offset>=0x3000 && offset<0x4000) return stack[offset-0x3000u];
        if (segment==actorSegment && offset>=actorOffset && offset<actorOffset+actor.size())
            return actor[offset-actorOffset];
        if (segment==static_cast<uint16_t>(game+0x920) && (offset==0x142d || offset==0x142e))
            return offset==0x142d ? uint8_t{5} : uint8_t{0x84};
        if (segment==data) {
            if (offset==0x1afa || offset==0x1afb) return offset==0x1afa ? uint8_t{0} : uint8_t{2};
            if (offset>=0x1afe && offset<0x1b02)
                return static_cast<uint8_t>(randomSeed>>((offset-0x1afeu)*8u));
            if (offset>=0x2054 && offset<0x2058) return input.tiles[offset-0x2054u];
            if (offset==0x78c2 || offset==0x78c3)
                return static_cast<uint8_t>(input.tick>>((offset-0x78c2u)*8u));
            if (offset>=0x58 && offset<0x258) return animationBytes[offset-0x58u];
            for (size_t i=0;i<shared.size();++i)
                if (offset==sharedOffsets[i] || offset==sharedOffsets[i]+1u)
                    return static_cast<uint8_t>(shared[i]>>((offset-sharedOffsets[i])*8u));
        }
        throw std::domain_error("Actor motion prefix read left owned inputs/stack");
    };
    const auto word=[&](uint16_t segment,uint16_t offset) {
        return static_cast<uint16_t>(byte(segment,offset)|(uint16_t{byte(segment,static_cast<uint16_t>(offset+1u))}<<8));
    };
    const auto writeByte=[&](uint16_t segment,uint16_t offset,uint8_t value) {
        if (segment==stackSegment && offset>=0x3000 && offset<0x4000) {
            stack[offset-0x3000u]=value;return;
        }
        if (segment==actorSegment && offset>=actorOffset && offset<actorOffset+actor.size()) {
            actor[offset-actorOffset]=value;return;
        }
        if (segment==data) {
            if (offset>=0x1afe && offset<0x1b02) {
                const auto shift=(offset-0x1afeu)*8u;
                randomSeed=(randomSeed&~(uint32_t{255}<<shift))|(uint32_t{value}<<shift);return;
            }
            for (size_t i=0;i<shared.size();++i) {
                if (offset==sharedOffsets[i] || offset==sharedOffsets[i]+1u) {
                    const auto shift=(offset-sharedOffsets[i])*8u;
                    shared[i]=static_cast<uint16_t>((shared[i]&~(255u<<shift))|(uint32_t{value}<<shift));return;
                }
            }
        }
        throw std::domain_error("Actor motion prefix write left owned outputs/stack");
    };
    const auto writeWord=[&](uint16_t segment,uint16_t offset,uint16_t value) {
        writeByte(segment,offset,static_cast<uint8_t>(value));
        writeByte(segment,static_cast<uint16_t>(offset+1u),static_cast<uint8_t>(value>>8));
    };
    const TimerIrqBus bus{
        byte,word,
        [&](uint16_t s,uint16_t o) { return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16); },
        writeByte,writeWord,
        [&](uint16_t s,uint16_t o,uint32_t value) {
            writeWord(s,o,static_cast<uint16_t>(value));writeWord(s,static_cast<uint16_t>(o+2u),static_cast<uint16_t>(value>>16));
        },
        [](uint16_t) -> uint8_t { throw std::domain_error("Actor motion prefix attempted hardware input"); },
        [](uint16_t,uint8_t) { throw std::domain_error("Actor motion prefix attempted hardware output"); }
    };
    const auto store=[&](int offset,uint16_t value) { writeWord(stackSegment,static_cast<uint16_t>(bp+offset),value); };
    store(4,actorOffset);store(6,actorSegment);
    store(-4,static_cast<uint16_t>(input.dx));store(-6,static_cast<uint16_t>(input.dy));
    store(-12,static_cast<uint16_t>(input.vx8));store(-14,static_cast<uint16_t>(input.vy8));
    store(-48,static_cast<uint16_t>(input.originalX));store(-44,static_cast<uint16_t>(input.x));
    store(-46,static_cast<uint16_t>(input.y));
    for (auto [offset,value] : std::array<std::array<int,2>,7>{{
            {{-34,input.edges[0]}},{{-33,input.edges[1]}},{{-35,input.edges[2]}},{{-36,input.edges[3]}},
            {{-15,actor[0]}},{{-49,actor[21]}},{{-32,input.facingRequest}}}})
        writeByte(stackSegment,static_cast<uint16_t>(bp+offset),static_cast<uint8_t>(value));
    DosGetTimeRegisters r{};r.cs=game;r.ds=data;r.ss=stackSegment;r.sp=sp;r.bp=bp;r.ip=0x7018;r.ax=actor[21];
    ActorMotionOperation operation(r,game,0);
    while (!operation.finished() && !(operation.registers().cs==game && operation.registers().ip==0x732c)) {
        if (operation.snapshot().cpu.dispatchedInstructions>=65536 ||
            operation.advance(1,bus,[](uint16_t n) { return n; })!=1)
            throw std::domain_error("Actor motion prefix exceeded execution reserve");
    }
    const auto end=operation.registers();
    ActorMotionPrefixOutcome outcome=ActorMotionPrefixOutcome::Terrain;
    if (operation.finished()) {
        if (operation.snapshot().outcome==ActorMotionOutcome::DivideError) outcome=ActorMotionPrefixOutcome::DivideError;
        else if (operation.snapshot().outcome==ActorMotionOutcome::RuntimeError) outcome=ActorMotionPrefixOutcome::RuntimeError;
        else throw std::domain_error("Actor motion prefix reached an unexpected handoff");
    } else if (end.bp!=bp || end.sp!=sp) {
        throw std::domain_error("Actor motion prefix did not restore its live caller stack");
    }
    const auto local=[&](int offset) { return std::bit_cast<int16_t>(word(stackSegment,static_cast<uint16_t>(bp+offset))); };
    return {actor,local(-44),local(-46),local(-12),local(-14),shared,randomSeed,
        byte(stackSegment,bp-32),outcome,end.ip,operation.snapshot().cpu.dispatchedInstructions};
}

} // namespace lezac::core
