"""Compiled collapse behavior and ownership faults against the original corpus."""
import argparse
from pathlib import Path
import check_collapse_update_fixture as fixture
from test_transient_update_mutations import run

FAULTS=(
    ('collapse_count','collapse_queue_instructions.hpp',
        'case 0x5110:r.ax=static_cast<uint16_t>(bus.readWord(r.ds,static_cast<uint16_t>(0x2080u)))',
        'case 0x5110:r.ax=0'),
    ('map_offset','collapse_queue_instructions.hpp',
        'case 0x4d54:bus.writeWord(r.ds,static_cast<uint16_t>(0x2092u),static_cast<uint16_t>(r.ax))',
        'case 0x4d54:bus.writeWord(r.ds,static_cast<uint16_t>(0x2092u),static_cast<uint16_t>(0))'),
    ('contact_count','collapse_queue_instructions.hpp',
        'case 0x4ed6:bus.writeWord(r.ds,static_cast<uint16_t>(0x2078u),static_cast<uint16_t>(increment(bus.readWord(r.ds,static_cast<uint16_t>(0x2078u)),false,false)))',
        'case 0x4ed6:bus.writeWord(r.ds,static_cast<uint16_t>(0x2078u),static_cast<uint16_t>(increment(bus.readWord(r.ds,static_cast<uint16_t>(0x2078u)),true,false)))'),
    ('vertical_blend','collapse_queue_instructions.hpp','case 0x53be:push(0x53c1);r.ip=0x3d46u;',
        'case 0x53be:push(0x53c1);r.ip=0x3bb2u;'),
    ('retired_word','collapse_queue_instructions.hpp',
        'case 0x50d1:r.ax=static_cast<uint16_t>(logic(r.ax&0x7fffu,false))',
        'case 0x50d1:r.ax=static_cast<uint16_t>(logic(r.ax&0x7ffeu,false))'),
    ('pool_count','collapse_queue_instructions.hpp',
        'case 0x50fa:bus.writeWord(r.ds,static_cast<uint16_t>(0x2080u),static_cast<uint16_t>(increment(bus.readWord(r.ds,static_cast<uint16_t>(0x2080u)),true,false)))',
        'case 0x50fa:bus.writeWord(r.ds,static_cast<uint16_t>(0x2080u),static_cast<uint16_t>(increment(bus.readWord(r.ds,static_cast<uint16_t>(0x2080u)),false,false)))'),
    ('copy_direction','collapse_queue_instructions.hpp','step=flag(0x400) ? 65535 : 1','step=flag(0x400) ? 1 : 65535'),
    ('copy_grant','collapse_queue_instructions.hpp','if (count>r.cx) throw','if (false) throw'),
    ('divide_outcome','transient_update.hpp',
        'catch (const CollapseQueueDivideFault&) {\n                ++fg.dispatchedInstructions;state_.outcome=TransientUpdateOutcome::DivideError;',
        'catch (const CollapseQueueDivideFault&) {\n                ++fg.dispatchedInstructions;state_.outcome=TransientUpdateOutcome::RuntimeError;'),
    ('termination','transient_update.hpp','r.ip==0xe9) state_.outcome=TransientUpdateOutcome::Terminated;',
        'r.ip==0xe9) state_.outcome=TransientUpdateOutcome::RuntimeError;'),
    ('entry_mode','transient_update.hpp','state_.entry=entry;',
        'state_.entry=entry==TransientUpdateEntry::Collapse ? TransientUpdateEntry::SparksAndDebris : entry;'),
    ('graphics_owner','transient_update.hpp','!(state_.entry==TransientUpdateEntry::Collapse && r.cs==graphics())','true'),
    ('terminal_validation','transient_update.hpp','if (finished()) validate();','if (false) validate();'),
    ('counter_conservation','transient_update.hpp','state_.dispatchedInstructions!=instructions','false'),
)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.cxx,args.out,corpus=fixture,faults=FAULTS,family='collapse_update')
