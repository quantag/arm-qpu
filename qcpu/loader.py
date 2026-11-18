"""Load AArch64 machine code: the whole .text / __text section of an ELF or Mach-O object or executable
(so calls between functions work), with BL/B relocations of object files applied, or a raw .bin."""
import os


def _patch_branch(code, off, target):
    w = int.from_bytes(code[off:off + 4], "little")
    if (w & 0x7C000000) != 0x14000000:          # B / BL
        return False
    imm = ((target - off) >> 2) & 0x3FFFFFF
    code[off:off + 4] = ((w & 0xFC000000) | imm).to_bytes(4, "little")
    return True


def load_program(path, entry=None):
    """Returns dict(words, entry_index, entry, functions={name: index}, unresolved=[...])."""
    data = open(path, "rb").read()
    magic = data[:4]
    if magic == b"\x7fELF" or magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
        import lief
        lief.logging.disable()
        b = lief.parse(path)
        unresolved = []
        if isinstance(b, lief.MachO.FatBinary):
            b = next(x for x in b if x.header.cpu_type == lief.MachO.Header.CPU_TYPE.ARM64)
        if isinstance(b, lief.ELF.Binary):
            if b.header.machine_type != lief.ELF.ARCH.AARCH64:
                raise ValueError("not an AArch64 ELF file")
            text = b.get_section(".text")
            rel = b.header.file_type == lief.ELF.Header.FILE_TYPE.REL
            base = 0 if rel else text.virtual_address
            code = bytearray(text.content)
            funcs = {s.name: s.value - base for s in b.symbols
                     if s.type == lief.ELF.Symbol.TYPE.FUNC and s.name and 0 <= s.value - base < len(code)}
            if rel:
                for r in b.relocations:
                    if getattr(r, "section", None) is None or r.section.name != ".text":
                        continue
                    if r.type in (lief.ELF.Relocation.TYPE.AARCH64_CALL26, lief.ELF.Relocation.TYPE.AARCH64_JUMP26):
                        name = r.symbol.name
                        if name in funcs and _patch_branch(code, r.address, funcs[name] + r.addend):
                            continue
                    unresolved.append(f"offset {r.address}: {r.type} {r.symbol.name if r.has_symbol else ''}")
        else:
            if b.header.cpu_type != lief.MachO.Header.CPU_TYPE.ARM64:
                raise ValueError("not an arm64 Mach-O file")
            text = b.get_section("__text")
            code = bytearray(text.content)
            funcs = {s.name[1:] if s.name.startswith("_") else s.name: s.value - text.virtual_address
                     for s in b.symbols if s.name.startswith("_") and 0 <= s.value - text.virtual_address < len(code)}
            for r in text.relocations:
                a = r.address
                if a + 4 > len(code):
                    a -= text.offset
                name = r.symbol.name[1:] if r.has_symbol and r.symbol.name.startswith("_") else None
                if "BRANCH26" in str(r.type) and name in funcs and _patch_branch(code, a, funcs[name]):
                    continue
                unresolved.append(f"offset {a}: {r.type} {name or ''}")
        if not funcs:
            raise ValueError("no function symbols found in the code section")
        if entry is None:
            entry = "main" if "main" in funcs else min(funcs, key=funcs.get)
        if entry not in funcs:
            raise ValueError(f"function '{entry}' not found; available: {', '.join(sorted(funcs, key=funcs.get))}")
        words = [int.from_bytes(code[i:i + 4], "little") for i in range(0, len(code) - len(code) % 4, 4)]
        return dict(words=words, entry=entry, entry_index=funcs[entry] // 4,
                    functions={n: o // 4 for n, o in sorted(funcs.items(), key=lambda t: t[1])}, unresolved=unresolved)
    if len(data) % 4:
        raise ValueError("raw binary length is not a multiple of 4")
    words = [int.from_bytes(data[i:i + 4], "little") for i in range(0, len(data), 4)]
    return dict(words=words, entry=os.path.basename(path), entry_index=0, functions={}, unresolved=[])
