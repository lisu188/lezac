"""Compile prefix and lifecycle faults against continuous original execution."""
import argparse
from pathlib import Path

import check_frame_post_render_fixture as fixture
from test_transient_update_mutations import run

FAULTS=(
    ('prefix_actor_handoff','frame_iteration.hpp','handoff(r,0x7ebb);','handoff(r,0x804e);'),
    ('prefix_completed_work','frame_iteration.hpp',
        'return std::array<uint64_t,3>{child.dispatchedInstructions,child.timerInstructions,child.timerDeliveries};',
        'return std::array<uint64_t,3>{0,child.timerInstructions,child.timerDeliveries};'),
    ('spawner_reset','frame_spawner.hpp',
        'case 0x7a57:bus.writeByte(r.ds,0x79e8,0);','case 0x7a57:bus.writeByte(r.ds,0x79e8,1);'),
    ('spawner_secondary_reset','frame_spawner.hpp',
        'case 0x7a61:bus.writeByte(r.ds,0x79ae,0);','case 0x7a61:bus.writeByte(r.ds,0x79ae,1);'),
    ('spawner_countdown','frame_spawner.hpp',
        'case 0x7a9b:write(27,increment(read(27),true));','case 0x7a9b:write(27,increment(read(27),false));'),
    ('spawner_pool_growth','frame_spawner.hpp',
        'case 0x2fb7:bus.writeByte(r.ds,0x208d,increment(bus.readByte(r.ds,0x208d),false));',
        'case 0x2fb7:bus.writeByte(r.ds,0x208d,increment(bus.readByte(r.ds,0x208d),true));'),
    ('waiting_first_player','frame_waiting.hpp',
        'case 0x7c3d:bus.writeWord(r.ds,0x2082,1);','case 0x7c3d:bus.writeWord(r.ds,0x2082,2);'),
    ('dying_countdown','frame_waiting.hpp',
        'case 0x7c96:{const auto a=static_cast<uint16_t>(r.di+16);bus.writeWord(r.es,a,increment(bus.readWord(r.es,a),true));',
        'case 0x7c96:{const auto a=static_cast<uint16_t>(r.di+16);bus.writeWord(r.es,a,increment(bus.readWord(r.es,a),false));'),
    ('reserve_consumption','frame_waiting.hpp',
        'lo(increment(bus.readByte(r.ds,a),true,8))','lo(increment(bus.readByte(r.ds,a),false,8))'),
    ('last_player_removal','frame_waiting.hpp',
        'case 0x7cc3:bus.writeByte(r.ds,0x79b8,lo(increment(bus.readByte(r.ds,0x79b8),true,8)));',
        'case 0x7cc3:bus.writeByte(r.ds,0x79b8,lo(increment(bus.readByte(r.ds,0x79b8),false,8)));'),
    ('cleared_gate_restart','frame_waiting.hpp',
        'case 0x7dd6:bus.writeByte(r.ds,0x79b9,229);','case 0x7dd6:bus.writeByte(r.ds,0x79b9,228);'),
    ('end_run_outcome','frame_iteration.hpp',
        'case FramePrefixOutcome::EndRunUi:return FrameIterationOutcome::EndRunUi;',
        'case FramePrefixOutcome::EndRunUi:return FrameIterationOutcome::Restart;'),
    ('placement_target','frame_waiting.hpp','case 0x7d20:call(0x56b,0x7d23);','case 0x7d20:call(0x56c,0x7d23);'),
    ('waiting_handoff','frame_prefix.hpp',
        'if (next == 1) state_.callee = FrameWaitingOperation(',
        'if (next == 0) state_.callee = FrameWaitingOperation('),
)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run(args.cxx,args.out,fixture,FAULTS,'frame_post_render',
        test_source='tests/core/frame_iteration_test.cpp',error_marker=b'frame_iteration_error=')
