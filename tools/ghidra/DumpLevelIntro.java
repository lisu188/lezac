// Dump the original level-intro routine, caption references, and caller context.
// @category LEZAC

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.File;
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.Set;

public class DumpLevelIntro extends GhidraScript {
    private PrintWriter out;
    private final Set<Address> dumpedFunctions = new HashSet<>();

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File output = args.length > 0
            ? new File(args[0])
            : new File("/tmp/lezac-ghidra-out/level_intro_dump.txt");
        File parent = output.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        try (PrintWriter writer = new PrintWriter(output)) {
            out = writer;
            out.printf("program=%s language=%s%n",
                currentProgram.getName(), currentProgram.getLanguageID());
            dumpBytes("caption_data", "1000:b290", 0x50);
            dumpReferences("caption_references", "1000:b2aa", 0x24);
            dumpRange("palette_ramp", "1000:0139", "1000:01fb");
            dumpRange("striped_background", "1000:01fc", "1000:030a");
            dumpRange("level_loader_intro_call", "1000:2adc", "1000:2c72");
            dumpContainingFunction(addr("1000:146a"));
            dumpRange("new_game_state", "1000:2efd", "1000:2f9e");
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

    private void dumpBytes(String name, String start, int length) throws Exception {
        Address base = addr(start);
        Memory memory = currentProgram.getMemory();
        out.printf("%n== %s %s len=0x%x ==%n", name, start, length);
        for (int offset = 0; offset < length; offset += 16) {
            out.printf("%s: ", base.add(offset));
            for (int i = 0; i < 16 && offset + i < length; ++i) {
                out.printf("%02x ", memory.getByte(base.add(offset + i)) & 0xff);
            }
            out.println();
        }
    }

    private void dumpReferences(String name, String start, int length) throws Exception {
        Address base = addr(start);
        out.printf("%n== %s %s len=0x%x ==%n", name, start, length);
        for (int offset = 0; offset < length; ++offset) {
            Address target = base.add(offset);
            ReferenceIterator references =
                currentProgram.getReferenceManager().getReferencesTo(target);
            while (references.hasNext()) {
                Reference reference = references.next();
                out.printf("target=%s from=%s type=%s operand=%d%n",
                    target, reference.getFromAddress(), reference.getReferenceType(),
                    reference.getOperandIndex());
                dumpContainingFunction(reference.getFromAddress());
            }
        }
    }

    private void dumpContainingFunction(Address referenceAddress) throws Exception {
        Function function = getFunctionContaining(referenceAddress);
        if (function == null || !dumpedFunctions.add(function.getEntryPoint())) {
            return;
        }

        out.printf("%n== function %s %s ==%n",
            function.getName(), function.getEntryPoint());
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
            DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
            if (result.decompileCompleted() && result.getDecompiledFunction() != null) {
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

    private void dumpRange(String name, String start, String end) {
        out.printf("%n== %s %s..%s ==%n", name, start, end);
        InstructionIterator instructions = currentProgram.getListing().getInstructions(
            new AddressSet(addr(start), addr(end)), true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            out.printf("%s: %-8s %s%n", instruction.getAddress(),
                instruction.getMnemonicString(), operands(instruction));
        }
    }
}
