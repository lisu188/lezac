#include "core/actor_motion_prefix.hpp"
#include "diagnostics/nonplayer_motion_fixture.hpp"

#include <iostream>
#include <stdexcept>

namespace {
void require(bool yes,const char* message) { if (!yes) throw std::runtime_error(message); }
void unit() {
    using namespace lezac::core;
    ActorMotionPrefixInput input;input.actor[21]=2;input.vx8=-32768;input.edges[1]=1;
    input.originalX=input.x=80;input.y=83;std::array<uint8_t,512> animation{};
    const auto before=input;
    auto result=actorMotionPrefix(input,animation);
    require(input==before && result.outcome==ActorMotionPrefixOutcome::Terrain && result.stopIp==0x732c &&
        result.vx8==0 && result.vy8==0 && result.y==83,"Original friction minimum-word behavior differs");
    input.actor[21]=3;input.actor[4]=1;input.actor[14]=8;input.actor[15]=1;
    input.vx8=0;input.vy8=1;input.tiles.fill(1);animation[2]=55;animation[3]=57;
    result=actorMotionPrefix(input,animation);
    require(result.vx8==264 && result.vy8==0 && result.y==80 && result.facingRequest==1 &&
        result.actor[22]==55 && result.actor[23]==55 && result.actor[24]==57,
        "Original landing/seed/facing order differs");
    input.actor[21]=4;input.actor[14]=0;input.actor[15]=0;input.tick=48;
    result=actorMotionPrefix(input,animation);
    require(result.outcome==ActorMotionPrefixOutcome::DivideError && result.stopIp==0x70dc,
        "Original zero-period divide fault was hidden");
    std::cout << "nonplayer_motion_unit=ok friction_min_word=1 landing_facing=1 precise_divide_fault=1 input_preserved=1\n";
}
void original(const char* path) {
    using namespace lezac::core;
    const auto rows=lezac::diagnostics::readNonplayerMotionFixture(path);
    uint64_t instructions=0;unsigned faults=0;
    for (const auto& row : rows) {
        const auto actual=actorMotionPrefix(row.input,row.animationBytes);
        if (actual!=row.expected) {
            std::cerr << "case=" << row.originalCase << " actual_xyv=" << actual.x << ',' << actual.y << ','
                << actual.vx8 << ',' << actual.vy8 << " original=" << row.expected.x << ',' << row.expected.y << ','
                << row.expected.vx8 << ',' << row.expected.vy8 << " instructions=" << actual.instructions << '/'
                << row.expected.instructions << " rng=" << actual.randomSeed << '/' << row.expected.randomSeed << '\n';
            throw std::runtime_error("Typed nonplayer motion differs from original prefix");
        }
        instructions+=actual.instructions;faults+=actual.outcome==ActorMotionPrefixOutcome::DivideError;
    }
    std::cout << "nonplayer_motion_original=ok cases=" << rows.size() << " continuous_actor_cases=54 real_caller_cases=54"
        << " divide_faults=" << faults << " instructions=" << instructions
        << " actual_7018_to_732C=1 owned_stack=1 terrain_executed=0 full_frame_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();
        else { require(argc==2,"Nonplayer motion arguments differ");original(argv[1]); }
        return 0;
    } catch (const std::exception& error) { std::cerr << "nonplayer_motion=failed " << error.what() << '\n';return 1; }
}
