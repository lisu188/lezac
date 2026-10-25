"""Compile frame queue caller faults against unit and authenticated original controls."""
import argparse
from pathlib import Path

import check_frame_transient_queues_fixture as fixture
from test_transient_update_mutations import run

FAULTS=(
    ('spark_threshold','frame_transient_queues.hpp',
        'compare(bus.readWord(r.ds,0x2076),0)','compare(bus.readWord(r.ds,0x2076),1)'),
    ('debris_threshold','frame_transient_queues.hpp',
        'compare(bus.readWord(r.ds,0x207e),200)','compare(bus.readWord(r.ds,0x207e),201)'),
    ('debris_boundary','frame_transient_queues.hpp',
        'case 0x805b:r.ip=flag(1) ?','case 0x805b:r.ip=flag(1) || flag(0x40) ?'),
    ('collapse_selection','frame_transient_queues.hpp',
        'case 0x8065:r.ip=flag(1) || flag(0x40) ?','case 0x8065:r.ip=true ?'),
    ('spark_return_word','frame_transient_queues.hpp',
        'call(0x45fa,0x8060)','call(0x45fa,0x806a)'),
    ('collapse_target','frame_transient_queues.hpp',
        'call(0x5102,0x806a)','call(0x45fa,0x806a)'),
    ('completed_dispatch','frame_transient_queues.hpp',
        'state_.completed[0]+=snapshot.dispatchedInstructions','state_.completed[0]+=0'),
    ('caller_register_restore','frame_transient_queues.hpp',
        'state_.caller.registers=r;','state_.caller.registers.ip=r.ip;'),
    ('error_outcome','frame_transient_queues.hpp',
        'state_.outcome=snapshot.outcome==TransientUpdateOutcome::RuntimeError ? FrameTransientQueuesOutcome::RuntimeError :',
        'state_.outcome=snapshot.outcome==TransientUpdateOutcome::RuntimeError ? FrameTransientQueuesOutcome::DivideError :'),
    ('caller_sp_guard','frame_transient_queues.hpp',
        'if (r.sp!=state_.callerSp || calls!=returns ||','if (false || calls!=returns ||'),
    ('caller_bp_guard','frame_transient_queues.hpp',
        'r.ss!=state_.callerSs || r.bp!=state_.callerBp || caller.transferredBytes ||',
        'r.ss!=state_.callerSs || false || caller.transferredBytes ||'),
    ('caller_pc_counter','frame_transient_queues.hpp',
        'case 0x8053:if (foreground!=1 ||','case 0x8053:if (false ||'),
    ('dispatch_conservation','frame_transient_queues.hpp',
        'conservation(state_.dispatchedInstructions,caller.dispatchedInstructions,state_.completed[0],active[0]);',
        'if (false) conservation(state_.dispatchedInstructions,caller.dispatchedInstructions,state_.completed[0],active[0]);'),
    ('compare_parity','frame_transient_queues.hpp',
        'std::popcount(static_cast<uint8_t>(value))%2==0','std::popcount(static_cast<uint8_t>(value))%2!=0'),
)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run(args.cxx,args.out,fixture,FAULTS,'frame_transient_queues',
        'tests/core/frame_transient_queues_test.cpp',True,b'frame_transient_queues_error=')
