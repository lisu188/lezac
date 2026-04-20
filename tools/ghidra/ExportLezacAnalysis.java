// Export compact analysis anchors for LEZAC.EXE.
// @category LEZAC

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;
import java.io.File;
import java.io.PrintWriter;

public class ExportLezacAnalysis extends GhidraScript {
    @Override
    protected void run() throws Exception {
        File outDir = new File("/tmp/lezac-ghidra-out");
        outDir.mkdirs();
        try (PrintWriter out = new PrintWriter(new File(outDir, "lezac_summary.txt"))) {
            out.printf("name=%s%n", currentProgram.getName());
            out.printf("language=%s%n", currentProgram.getLanguageID());
            out.printf("entry=%s%n", currentProgram.getSymbolTable().getExternalEntryPointIterator().next());
            out.println();
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                out.printf("block %-8s %s..%s size=0x%x%n",
                    block.getName(), block.getStart(), block.getEnd(), block.getSize());
            }
            out.println();
            label(out, "1000:0c33", "lz_load_current_level");
            label(out, "1000:0faa", "lz_load_level_wrapper");
            label(out, "182d:0000", "lz_rle3_decode");
            label(out, "1000:2efd", "lz_start_new_game_state");
            label(out, "1000:3358", "lz_remove_actor_slot");
            label(out, "1000:3587", "lz_update_camera_from_player");
            label(out, "1000:370e", "lz_fragment_or_collapse_tile");
        }
    }

    private void label(PrintWriter out, String text, String name) throws Exception {
        Address addr = currentProgram.getAddressFactory().getAddress(text);
        if (addr == null) {
            out.printf("missing %s %s%n", text, name);
            return;
        }
        createLabel(addr, name, true, SourceType.USER_DEFINED);
        Function f = getFunctionAt(addr);
        if (f != null) {
            f.setName(name, SourceType.USER_DEFINED);
        }
        out.printf("%s %s%n", text, name);
    }
}

