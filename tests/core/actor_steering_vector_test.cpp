#include "core/actor_steering_vector.hpp"
#include "diagnostics/actor_steering_fixture.hpp"

#include <iostream>

namespace {
void require(bool yes,const char* message) { if (!yes) throw std::runtime_error(message); }
void unit() {
    using lezac::core::actorSteeringVector8;using lezac::core::ActorSteeringVector8;
    require(actorSteeringVector8(0,0,65535)==ActorSteeringVector8{0,0},"Zero vector differs");
    require(actorSteeringVector8(1,0,32768)==ActorSteeringVector8{-32768,0},"Unsigned speed/low word differs");
    require(actorSteeringVector8(1,0,65535)==ActorSteeringVector8{-1,0},"Full unsigned speed differs");
    require(actorSteeringVector8(40,20,494)==ActorSteeringVector8{441,220},"Captured diagonal differs");
    require(actorSteeringVector8(-257,0,494)==ActorSteeringVector8{-493,0},"Original Real48 rounding differs");
    std::cout << "actor_steering_vector_unit=ok original_examples=5\n";
}
void replay(const char* path) {
    const auto rows=lezac::diagnostics::readActorSteeringFixture(path);unsigned callers=0,admitted=0;
    for (const auto& row : rows) {
        const auto result=lezac::core::actorSteeringVector8(row.dx,row.dy,row.speed);
        if (result.vx8!=row.vx8 || result.vy8!=row.vy8) {
            std::cerr << "case=" << row.originalCase << " input=" << row.dx << ',' << row.dy << ',' << row.speed
                << " actual=" << result.vx8 << ',' << result.vy8 << " original=" << row.vx8 << ',' << row.vy8 << '\n';
            throw std::runtime_error("Typed steering differs from original writes");
        }
        callers+=row.domain;admitted+=row.homingAdmitted;
    }
    require(rows.size()==2136 && callers==64 && admitted==2097,"Typed steering corpus differs");
    std::cout << "actor_steering_vector_original=ok cases=2136 original_live_caller_rows=64 app_homing_cases=2097"
        << " app_gate_excluded=39 real_callsite_in_API=1 original_expected_writes=1 full_frame_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {
        if (argc==1) unit();else { require(argc==2,"Steering vector arguments differ");replay(argv[1]); }
        return 0;
    } catch (const std::exception& error) { std::cerr << "actor_steering_vector=failed " << error.what() << '\n';return 1; }
}
