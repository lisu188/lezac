// Dump original GRAN loading, camera, visual-table, and boss-motion paths.
// @category LEZAC

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.File;
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.Set;

public class DumpGranPlacement extends GhidraScript {
    private PrintWriter out;
    private final Set<Address> dumpedFunctions = new HashSet<>();

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File output = args.length > 0
            ? new File(args[0])
            : new File("/tmp/lezac-ghidra-out/gran_placement_dump.txt");
        File parent = output.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        try (PrintWriter writer = new PrintWriter(output)) {
            out = writer;
            out.printf("program=%s language=%s%n",
                currentProgram.getName(), currentProgram.getLanguageID());
            dumpFunctionAt("generic_actor_file_reader", "1000:08a5");
            dumpRange("level7_gran_callsite", "1000:2e60", "1000:2e90");
            dumpFunctionAt("level_loader", "1000:2adc");
            dumpFunctionAt("camera_update", "1000:3587");
            dumpFunctionAt("boss_link_recompute", "1000:432a");
            dumpFunctionAt("boss_link_apply", "1000:5872");
            dumpFunctionAt("boss_head_brain", "1000:5cb0");
            dumpFunctionAt("actor_update", "1000:6053");
            dumpFunctionAt("overlay_draw", "18ac:00f4");
            dumpFunctionAt("overlay_present", "18ac:03c8");
            dumpFunctionAt("overlay_visual_allocate", "18ac:0517");
            dumpReferences("actor_table", "1000:1bae", 0x26);
            dumpReferences("camera_globals", "1000:c1e0", 0x40);
            dumpReferences("visual_table", "1000:c21e", 0x60);
        }
    }

    private Address addr(String text) {
        return currentProgram.getAddressFactory().getAddress(text);
    }

    private String operands(Instruction instruction) {
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < instruction.getNumOperands(); ++i) {
            if (i > 0) {
                result.append(", ");
            }
            result.append(instruction.getDefaultOperandRepresentation(i));
        }
        return result.toString();
    }

    private void dumpFunctionAt(String label, String anchor) throws Exception {
        Function function = getFunctionContaining(addr(anchor));
        if (function == null) {
            out.printf("%n== %s %s: no containing function ==%n", label, anchor);
            return;
        }
        dumpFunction(label, function);
    }

    private void dumpFunction(String label, Function function) throws Exception {
        if (!dumpedFunctions.add(function.getEntryPoint())) {
            out.printf("%n== %s %s: already dumped ==%n",
                label, function.getEntryPoint());
            return;
        }

        out.printf("%n== %s function=%s entry=%s ==%n",
            label, function.getName(), function.getEntryPoint());
        InstructionIterator instructions =
            currentProgram.getListing().getInstructions(function.getBody(), true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            out.printf("%s: %-8s %s%n", instruction.getAddress(),
                instruction.getMnemonicString(), operands(instruction));
        }

        DecompInterface decompiler = new DecompInterface();
        try {
            decompiler.openProgram(currentProgram);
            DecompileResults result =
                decompiler.decompileFunction(function, 120, monitor);
            if (result.decompileCompleted()
                    && result.getDecompiledFunction() != null) {
                out.printf("%n-- decompile %s --%n%s%n",
                    function.getName(), result.getDecompiledFunction().getC());
            } else {
                out.printf("%n-- decompile failed: %s --%n",
                    result.getErrorMessage());
            }
        } finally {
            decompiler.dispose();
        }
    }

    private void dumpRange(String label, String start, String end) {
        out.printf("%n== %s %s..%s ==%n", label, start, end);
        InstructionIterator instructions = currentProgram.getListing().getInstructions(
            new AddressSet(addr(start), addr(end)), true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            out.printf("%s: %-8s %s%n", instruction.getAddress(),
                instruction.getMnemonicString(), operands(instruction));
        }
    }

    private void dumpReferences(String label, String start, int length)
            throws Exception {
        Address base = addr(start);
        out.printf("%n== %s %s len=0x%x ==%n", label, start, length);
        for (int offset = 0; offset < length; ++offset) {
            Address target = base.add(offset);
            ReferenceIterator references =
                currentProgram.getReferenceManager().getReferencesTo(target);
            while (references.hasNext()) {
                Reference reference = references.next();
                out.printf("target=%s from=%s type=%s operand=%d%n",
                    target, reference.getFromAddress(), reference.getReferenceType(),
                    reference.getOperandIndex());
                Function function = getFunctionContaining(reference.getFromAddress());
                if (function != null) {
                    dumpFunction("reference_from_" + reference.getFromAddress(), function);
                }
            }
        }
    }
}
