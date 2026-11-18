"""Random A64 programs (assembled by clang) -> CPU emulator vs ONE fixed quantum interpreter circuit."""
import os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qcpu.machine import Config, QuantumARM, words_from_bytes, validate
from qcpu.bitsim import simulate_basis, read_reg
from tools.reference import run_reference


def assemble(lines):
    with tempfile.TemporaryDirectory() as d:
        s, o, b = (os.path.join(d, n) for n in ("p.s", "p.o", "p.bin"))
        open(s, "w").write(".text\n" + "\n".join(lines) + "\n")
        subprocess.run(["clang", "--target=aarch64-linux-gnu", "-c", s, "-o", o], check=True)
        subprocess.run(["llvm-objcopy", "-O", "binary", "--only-section=.text", o, b], check=True)
        return open(b, "rb").read()


def rand_instr(r, nreg):
    x = lambda: f"x{r.randrange(nreg)}"
    k = r.choice(["movz", "add", "eor"])
    if k == "movz": return f"movz {x()}, #{r.randrange(65536)}"
    if k == "add":  return f"add {x()}, {x()}, #{r.randrange(4096)}"
    return f"eor {x()}, {x()}, {x()}"


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    cfg = Config(W=4, NREG=4, STEPS=4, SLOTS=4, decoder="full")
    m = QuantumARM(cfg)
    r = random.Random(1)
    fails = 0
    for t in range(N):
        prog = [rand_instr(r, 4) for _ in range(cfg.STEPS)]
        code = assemble(prog); words = words_from_bytes(code); validate(words, cfg)
        ref = [v & 15 for v in run_reference(code, 4)]
        full = m.load_program(words).compose(m.qc)
        out = simulate_basis(full)
        q = [read_reg(full, out, X) for X in m.X]
        clean = not any(read_reg(full, out, reg) for reg in m.scratch)
        if q != ref or not clean:
            fails += 1; print("FAIL", prog, ref, q, clean)
    print(f"{N - fails}/{N} random 4-instruction programs: quantum interpreter == ARM CPU (low 4 bits), scratch clean")
    sys.exit(1 if fails else 0)
