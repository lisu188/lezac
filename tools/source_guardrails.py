"""Explicit, role-aware source input for recovery guardrails.

Update source_ownership.json in the same change that moves an implementation.
Runtime predicates must use runtime sources; diagnostic text is not evidence of
a live consumer. The legacy App currently owns several roles in one file.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable


MANIFEST = Path("tools/source_ownership.json")
ROLES = {"runtime", "diagnostics", "dispatch"}
# OneDrive conflict copies are historical evidence, never production input.
HISTORICAL_SUFFIXES = ("-LIS.cpp", "-LIS.hpp")


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative: str
    roles: frozenset[str]
    text: str


def ownership(root: Path) -> dict:
    path = root / MANIFEST
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("owners"), dict):
        raise RuntimeError(f"{path}: invalid source ownership manifest")
    owners = data["owners"]
    for owner, roles in owners.items():
        if not isinstance(roles, dict) or not roles:
            raise RuntimeError(f"{path}: invalid owner {owner}")
        for role, paths in roles.items():
            if role not in ROLES or not isinstance(paths, list) or not paths:
                raise RuntimeError(f"{path}: invalid role {owner}/{role}")
            if len(paths) != len(set(paths)):
                raise RuntimeError(f"{path}: duplicate source in {owner}/{role}")
            for relative in paths:
                candidate = Path(relative)
                if (candidate.is_absolute() or ".." in candidate.parts
                        or "\\" in relative or candidate.parts[0] != "src"
                        or candidate.suffix not in (".cpp", ".hpp")
                        or relative.endswith(HISTORICAL_SUFFIXES)):
                    raise RuntimeError(f"{path}: invalid source path {relative!r}")
                try:
                    (root / candidate).resolve().relative_to(root.resolve())
                except ValueError as exc:
                    raise RuntimeError(f"{path}: source escapes root: {relative}") from exc
    return owners


def source_files(root: Path, owners: Iterable[str] | str | None = None,
                 roles: Iterable[str] | str = "runtime") -> list[SourceFile]:
    mapping = ownership(root)
    chosen = [owners] if isinstance(owners, str) else list(owners or mapping)
    selected_roles = {roles} if isinstance(roles, str) else set(roles)
    if not selected_roles or not selected_roles <= ROLES:
        raise RuntimeError(f"invalid source roles: {sorted(selected_roles)}")
    paths: dict[str, set[str]] = {}
    for owner in chosen:
        if owner not in mapping:
            raise RuntimeError(f"unknown source owner: {owner}")
        for role in selected_roles:
            for relative in mapping[owner].get(role, []):
                paths.setdefault(relative, set()).add(role)
    if not paths:
        raise RuntimeError(f"no source files for {chosen}/{sorted(selected_roles)}")
    return [SourceFile(root / relative, relative, frozenset(file_roles),
                       (root / relative).read_text(encoding="utf-8"))
            for relative, file_roles in paths.items()]


def mask_cpp(text: str) -> str:
    """Mask comments/literals without changing offsets or line numbers."""
    pattern = r'R"([^ ()\\\t\r\n]{0,16})\(.*?\)\1"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/'
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group()),
                  text, flags=re.DOTALL)


# These are inspection helpers, not a complete C++ parser. Signatures are
# matched only at definition boundaries, never at call sites or in comments.
DEFINITION = re.compile(
    r"(?m)^[ \t]*(?:[\w:<>,*&]+[ \t]+)+"
    r"(?P<name>(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)\s*"
    r"\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?\{"
)


def function_ranges(text: str, names: Iterable[str]) -> dict[str, tuple[int, int]]:
    masked = mask_cpp(text)
    expected = set(names)
    found = {}
    for match in DEFINITION.finditer(masked):
        qualified = match.group("name")
        name = qualified.rsplit("::", 1)[-1]
        if name not in expected:
            continue
        if name in found:
            raise RuntimeError(f"duplicate function definition: {name}")
        opening = match.end() - 1
        depth = 1
        cursor = opening + 1
        while cursor < len(masked) and depth:
            depth += (masked[cursor] == "{") - (masked[cursor] == "}")
            cursor += 1
        if depth:
            raise RuntimeError(f"unterminated function definition: {qualified}")
        found[name] = (text.count("\n", 0, match.start()) + 1,
                       text.count("\n", 0, cursor) + 1)
    return found


def unqualify_definitions(text: str) -> str:
    """Keep legacy exact signature predicates valid for out-of-line methods."""
    masked = mask_cpp(text)
    for match in reversed(list(DEFINITION.finditer(masked))):
        name = match.group("name")
        if "::" in name:
            start, end = match.span("name")
            text = text[:start] + name.rsplit("::", 1)[-1] + text[end:]
    return text


def source_text(root: Path, owners: Iterable[str] | str | None,
                roles: Iterable[str] | str = "runtime") -> str:
    return "\n".join(unqualify_definitions(source.text)
                     for source in source_files(root, owners, roles))


def diagnostic_text(root: Path) -> str:
    return source_text(root, ("diagnostics", "app"), ("diagnostics", "dispatch"))


def legacy_source_root(path: Path) -> Path | None:
    path = path.resolve()
    if path.parts[-3:] == ("src", "app", "app.cpp"):
        return path.parents[2]
    return None


def diagnostic_source_text(path: Path) -> str:
    """Preserve --source file overrides; route the legacy path through its map."""
    root = legacy_source_root(path)
    if root is not None:
        return diagnostic_text(root)
    return unqualify_definitions(path.read_text(encoding="utf-8"))


def check_inventory(root: Path) -> int:
    if not (root / MANIFEST).is_file():
        raise RuntimeError(f"missing source ownership manifest: {root / MANIFEST}")
    mapped = {source.path.resolve() for source in source_files(root, roles=ROLES)}
    actual = {path.resolve() for path in (root / "src").rglob("*")
              if path.suffix in (".cpp", ".hpp")
              and not path.name.endswith(HISTORICAL_SUFFIXES)}
    missing = actual - mapped
    if missing:
        raise RuntimeError("unmapped production source: " + ", ".join(
            str(path.relative_to(root.resolve())) for path in sorted(missing)))
    return len(mapped)
