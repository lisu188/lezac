// Dump LEZAC visual effect and debris/collapse playback ranges.
// @category LEZAC

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.FlowType;
import java.io.File;
import java.io.PrintWriter;

public class DumpPlaybackRanges extends GhidraScript {
    private PrintWriter out;

    @Override
    protected void run() throws Exception {
        File outDir = new File("/tmp/lezac-ghidra-out");
        outDir.mkdirs();
        out = new PrintWriter(new File(outDir, "playback_ranges_dump.txt"));
        dumpRange("tile_damage_queue_370e", "1000:370e", "1000:3a55");
        dumpRange("debris_lookup_tail_3a56", "1000:3a56", "1000:3a7d");
        dumpRange("debris_scan_3a7e", "1000:3a7e", "1000:3b17");
        dumpRange("debris_scan_reverse_3b18", "1000:3b18", "1000:3bb1");
        dumpRange("collapse_forward_3bb2", "1000:3bb2", "1000:3d45");
        dumpRange("collapse_reverse_3d46", "1000:3d46", "1000:3ed9");
        dumpRange("tile_mutation_or_spawn_3eda", "1000:3eda", "1000:3fa5");
        dumpRange("effect_constructor_3fa6", "1000:3fa6", "1000:4149");
        dumpRange("effect_playback_432a", "1000:432a", "1000:4529");
        dumpRange("actor_effect_cleanup_33f0", "1000:33f0", "1000:3450");
        dumpBytes("globals_2070_20d0", "1000:2070", 0x60);
        dumpBytes("effect_slots_79e0_7a20", "1000:79e0", 0x40);
        dumpBytes("effect_table_c21e_c2a0", "1000:c21e", 0x82);
        out.close();
    }

    private Address addr(String text) {
        return currentProgram.getAddressFactory().getAddress(text);
    }

    private String ops(Instruction ins) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < ins.getNumOperands(); ++i) {
            if (i > 0) sb.append(", ");
            sb.append(ins.getDefaultOperandRepresentation(i));
        }
        return sb.toString();
    }

    private void dumpRange(String name, String start, String end) throws Exception {
        out.printf("%n== %s %s..%s ==%n", name, start, end);
        InstructionIterator it = currentProgram.getListing().getInstructions(
            new AddressSet(addr(start), addr(end)), true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            out.printf("%s: %-8s %s", ins.getAddress(), ins.getMnemonicString(), ops(ins));
            FlowType ft = ins.getFlowType();
            if (ft.isCall() || ft.isJump() || ft.isTerminal()) {
                out.printf(" ; flow=%s", ft);
            }
            out.println();
        }
    }

    private void dumpBytes(String name, String start, int len) throws Exception {
        Address base = addr(start);
        Memory mem = currentProgram.getMemory();
        out.printf("%n== %s %s len=0x%x ==%n", name, start, len);
        for (int off = 0; off < len; off += 16) {
            out.printf("%s: ", base.add(off));
            for (int i = 0; i < 16 && off + i < len; ++i) {
                out.printf("%02x ", mem.getByte(base.add(off + i)) & 0xff);
            }
            out.println();
        }
    }
}
