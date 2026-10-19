#include "core/actor_steering_vector.hpp"
#include "core/actor_steering.hpp"

#include <array>
#include <bit>
#include <stdexcept>

namespace lezac::core {

ActorSteeringVector8 actorSteeringVector8(int16_t dx,int16_t dy,uint16_t speed) {
    constexpr uint16_t game=0x1000,data=0x1aa2,stackSegment=0x7000,bp=0x3fdc,sp=0x3fa2;
    std::array<uint8_t,4096> stack{};
    const auto byte=[&](uint16_t segment,uint16_t offset) -> uint8_t {
        if (segment==stackSegment && offset>=0x3000 && offset<0x4000) return stack[offset-0x3000u];
        if (segment==data && offset==0x1afa) return 0;
        if (segment==data && offset==0x1afb) return 2;
        if (segment==data && offset==0x2074) return static_cast<uint8_t>(speed);
        if (segment==data && offset==0x2075) return static_cast<uint8_t>(speed>>8);
        throw std::domain_error("Actor steering read left owned stack/inputs");
    };
    const auto word=[&](uint16_t segment,uint16_t offset) {
        return static_cast<uint16_t>(byte(segment,offset)|(uint16_t{byte(segment,static_cast<uint16_t>(offset+1u))}<<8));
    };
    const auto writeByte=[&](uint16_t segment,uint16_t offset,uint8_t value) {
        if (segment!=stackSegment || offset<0x3000 || offset>=0x4000)
            throw std::domain_error("Actor steering write left owned stack");
        stack[offset-0x3000u]=value;
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
        [](uint16_t) -> uint8_t { throw std::domain_error("Actor steering attempted hardware input"); },
        [](uint16_t,uint8_t) { throw std::domain_error("Actor steering attempted hardware output"); }
    };
    writeWord(stackSegment,bp-4,static_cast<uint16_t>(dx));
    writeWord(stackSegment,bp-6,static_cast<uint16_t>(dy));
    DosGetTimeRegisters r{};r.cs=game;r.ds=data;r.ss=stackSegment;r.bp=bp;r.sp=sp;r.ip=0x710d;
    ActorSteeringOperation operation(r,game,0,ActorSteeringEntry::CallSite);
    while (!operation.finished()) {
        if (operation.snapshot().cpu.dispatchedInstructions>=65536 ||
            operation.advance(4096,bus,[](uint16_t n) { return n; })==0)
            throw std::domain_error("Actor steering exceeded execution reserve");
    }
    const auto end=operation.registers();
    if (operation.snapshot().outcome!=ActorSteeringOutcome::Returned ||
        end.cs!=game || end.ip!=0x714f || end.bp!=bp || end.sp!=sp)
        throw std::domain_error("Actor steering did not complete its actual caller");
    return {std::bit_cast<int16_t>(word(stackSegment,bp-12)),std::bit_cast<int16_t>(word(stackSegment,bp-14))};
}

} // namespace lezac::core
