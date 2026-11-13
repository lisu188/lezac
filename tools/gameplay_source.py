import re
from pathlib import Path

from source_guardrails import mask_cpp, source_files, unqualify_definitions


def argument_names(parameters: str) -> list[str]:
    parts, start, depth = [], 0, 0
    for index, char in enumerate(parameters):
        depth += (char in "(<[{") - (char in ")>]}")
        if char == "," and depth == 0:
            parts.append(parameters[start:index])
            start = index + 1
    parts.append(parameters[start:])
    names = []
    for part in parts:
        if not part.strip():
            continue
        depth = 0
        for index, char in enumerate(part):
            depth += (char in "(<[{") - (char in ")>]}")
            if char == "=" and depth == 0:
                part = part[:index]
                break
        name = re.search(r"([A-Za-z_]\w*)\s*$", part)
        if name is None:
            raise RuntimeError("unrecognized gameplay parameter declaration")
        names.append(name[1])
    return names


def gameplay_source_text(root: Path, *, headers: bool = False, owners: tuple[str, ...] = ()) -> str:
    files = source_files(root, (*owners, "app", "gameplay"), "runtime")
    operation_path = "src/gameplay/gameplay_operations.cpp"
    operations = [source for source in files if source.relative == operation_path]
    if not operations:
        if (root / operation_path).exists():
            raise RuntimeError("gameplay operation source has no runtime owner")
        return "\n".join(unqualify_definitions(source.text) for source in files)
    operation = operations[0]
    masked = mask_cpp(operation.text)
    definitions = list(re.finditer(r"\bGameplayOperations::([A-Za-z_]\w*)\s*\(", masked))
    names = []
    signatures = set()
    for match in definitions:
        if match[1] == "GameplayOperations":
            continue
        cursor, depth = match.end(), 1
        while cursor < len(masked) and depth:
            depth += (masked[cursor] == "(") - (masked[cursor] == ")")
            cursor += 1
        if depth or not re.match(r"\s*(?:const\s*)?\{", masked[cursor:]):
            raise RuntimeError("gameplay owner reference is not a definition: " + match[1])
        signature = re.sub(r"\s+", "", masked[match.start():cursor])
        if signature in signatures:
            raise RuntimeError("duplicate gameplay operation definition: " + match[1])
        signatures.add(signature)
        names.append(match[1])
    if not names:
        raise RuntimeError("missing gameplay operation definitions")
    app = next((source for source in files if source.relative == "src/app/app.cpp"), None)
    if app is None:
        raise RuntimeError("gameplay application source has no runtime owner")
    lines = app.text.splitlines(keepends=True)
    direct = r"\{returngameplayReplay_\.(?P<direct>\w+)\((?P<direct_args>[^;{}]*)\);\}"
    active = r"\{returnwithGameplay\(\[&\]\(auto&game\)->decltype\(auto\)\{returngame\.(?P<active>\w+)\((?P<active_args>[^;{}]*)\);\}\);\}"
    static = r"\{returnlezac::diagnostics::GameplayReplay::(?P<static>\w+)\((?P<static_args>[^;{}]*)\);\}"
    forwarding = re.compile(rf"(?:{direct}|{active}|{static})$")
    seen = []
    masked_app = mask_cpp(app.text)
    offset = 0
    for index, line in enumerate(masked_app.splitlines(keepends=True)):
        positions = [at for at, char in enumerate(line) if not char.isspace()]
        compact = "".join(line[at] for at in positions)
        match = forwarding.search(compact)
        if match is not None:
            name = match["direct"] or match["active"] or match["static"]
            cursor = offset + positions[match.start()] - 1
            while cursor >= 0 and masked_app[cursor].isspace():
                cursor -= 1
            if masked_app[max(0, cursor - 4):cursor + 1] == "const":
                cursor -= 5
                while cursor >= 0 and masked_app[cursor].isspace():
                    cursor -= 1
            if cursor < 0 or masked_app[cursor] != ")":
                raise RuntimeError("missing gameplay forwarding signature: " + name)
            parameter_end = cursor
            cursor, depth = cursor - 1, 1
            while cursor >= 0 and depth:
                depth += (masked_app[cursor] == ")") - (masked_app[cursor] == "(")
                cursor -= 1
            parameters = masked_app[cursor + 2:parameter_end]
            expected = ",".join(argument_names(parameters))
            arguments = next(match[kind + "_args"] for kind in ("direct", "active", "static")
                             if match[kind] is not None)
            if arguments != expected:
                raise RuntimeError("gameplay forwarding arguments differ: " + name)
            while cursor >= 0 and masked_app[cursor].isspace():
                cursor -= 1
            end = cursor + 1
            while cursor >= 0 and (masked_app[cursor].isalnum() or masked_app[cursor] == "_"):
                cursor -= 1
            start = cursor + 1
            if depth or name not in names or masked_app[start:end] != name:
                raise RuntimeError("unexpected gameplay forwarding body: " + name)
            first = masked_app.count("\n", 0, start)
            line_start = masked_app.rfind("\n", 0, start) + 1
            if not masked_app[line_start:start].strip():
                first -= 1
            seen.append(name)
            for row in range(first, index + 1):
                lines[row] = "\n" if lines[row].endswith("\n") else ""
        offset += len(line)
    if sorted(seen) != sorted(names):
        raise RuntimeError("missing or duplicate gameplay application forwarding boundary: " + str(sorted(set(names) - set(seen))))
    replacements = []
    for match in definitions:
        if match[1] == "GameplayOperations":
            continue
        replacements.append((match.start(), len("GameplayOperations::"), ""))
        start = operation.text.rfind("\n", 0, match.start()) + 1
        if not operation.text[start:match.start()].strip():
            start = operation.text.rfind("\n", 0, start - 1) + 1
        replacements.append((start, 0, "    "))
    normalized = operation.text
    for start, size, replacement in sorted(replacements, reverse=True):
        normalized = normalized[:start] + replacement + normalized[start + size:]
    return "\n".join([normalized] + ["".join(lines) if source is app
                     else unqualify_definitions(source.text) for source in files if source is not operation and
                     (headers or source.path.suffix == ".cpp" or source.relative == "src/gameplay/session_support.hpp")])
