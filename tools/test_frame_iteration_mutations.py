"""Compile continuous-frame ownership and handoff faults against original evidence."""
import argparse
from pathlib import Path

import check_frame_iteration_fixture as fixture
from test_transient_update_mutations import run

FAULTS=(
    ('actor_handoff','frame_iteration.hpp','handoff(r,0x804e);','handoff(r,0x806a);'),
    ('queue_bypass','frame_iteration.hpp',
        'handoff(r,0x804e);return FrameTransientQueuesOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();',
        'handoff(r,0x804e);return FrameTailOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();'),
    ('completed_work_lost','frame_iteration.hpp',
        'return std::array<uint64_t,3>{child.dispatchedInstructions,child.timerInstructions,child.timerDeliveries};',
        'return std::array<uint64_t,3>{0,child.timerInstructions,child.timerDeliveries};'),
    ('mandatory_past_phase','frame_iteration.hpp','!row[0] || row[1]>row[0]','row[1]>row[0]'),
    ('completed_phase_ownership','frame_iteration.hpp','if (row!=std::array<uint64_t,3>{}) invalid();','if (false) invalid();'),
    ('active_work_conservation','frame_iteration.hpp',
        'if (totals!=std::array<uint64_t,3>{child.dispatchedInstructions,child.timerInstructions,child.timerDeliveries}) invalid();',
        'if (false) invalid();'),
    ('parent_sp_binding','frame_iteration.hpp','child.callerSp!=state_.callerSp','false'),
    ('parent_bp_binding','frame_iteration.hpp','child.callerBp!=state_.callerBp','false'),
    ('actor_runtime_route','frame_iteration.hpp',
        'case FrameActorPassOutcome::RuntimeError:return FrameIterationOutcome::RuntimeError;',
        'case FrameActorPassOutcome::RuntimeError:return FrameIterationOutcome::DivideError;'),
    ('queue_runtime_route','frame_iteration.hpp',
        'case FrameTransientQueuesOutcome::RuntimeError:return FrameIterationOutcome::RuntimeError;',
        'case FrameTransientQueuesOutcome::RuntimeError:return FrameIterationOutcome::DivideError;'),
    ('view_change_route','frame_iteration.hpp',
        'case FrameTailOutcome::ViewChange:return FrameIterationOutcome::ViewChange;',
        'case FrameTailOutcome::ViewChange:return FrameIterationOutcome::NextFrame;'),
    ('irq_work_accounting','frame_iteration.hpp','if (timer) ++state_.timerInstructions;','if (timer) state_.timerInstructions+=0;'),
    ('irq_delivery_accounting','frame_iteration.hpp','++state_.timerDeliveries;','state_.timerDeliveries+=0;'),
    ('dispatch_accounting','frame_iteration.hpp','++used;++state_.dispatchedInstructions;','++used;state_.dispatchedInstructions+=2;'),
)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run(args.cxx,args.out,fixture,FAULTS,'frame_iteration',
        test_source='tests/core/frame_iteration_test.cpp',unit=True,error_marker=b'frame_iteration_error=')
