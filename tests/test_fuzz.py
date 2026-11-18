"""Differential fuzzing: random A64 programs (assembled by clang) executed on the CPU emulator and
on ONE fixed quantum interpreter circuit (exact basis-state simulation). Compares X0..X7, NZCV,
data memory and the full PC trace.   Run: python3 -m tests.test_fuzz [N] [seed]"""
import os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qcpu.machine import Config, QuantumARM
from qcpu.bitsim import simulate, value
from qcpu.reference import run_reference, layout, DATA_BASE

W, MEM, NREG, SLOTS = 8, 8, 8, 32
COND = "eq ne cs cc mi pl vs vc hi ls ge lt gt le al".split()
LIMM = [1, 3, 7, 0xf, 0x3c, 0x55, 0xaa, 0xf0, 0xfe, 0x7f, 0x80, 0xfffffff0, 0xffffff00, 0x6, 0x18]


def assemble(lines):
    with tempfile.TemporaryDirectory() as d:
        s, o, b = (os.path.join(d, n) for n in ("p.s", "p.o", "p.bin"))
        open(s, "w").write(".text\n" + "\n".join(lines) + "\n")
        r = subprocess.run(["clang", "--target=aarch64-linux-gnu", "-c", s, "-o", o], capture_output=True)
        if r.returncode: return None
        subprocess.run(["llvm-objcopy", "-O", "binary", "--only-section=.text", o, b], check=True)
        return open(b, "rb").read()


def gen(r, n):
    R = lambda: f"w{r.randrange(7)}"           # w7 holds the data pointer
    sh = lambda: r.choice(["", f", lsl #{r.randrange(4)}", f", lsr #{r.randrange(3)}", f", asr #{r.randrange(3)}"])
    out = []
    for i in range(n):
        k = r.randrange(23)
        if k == 0: out.append(f"{r.choice(['movz', 'movn'])} {R()}, #{r.randrange(40)}")
        elif k == 1: out.append(f"movk {R()}, #{r.randrange(40)}")
        elif k == 2: out.append(f"{r.choice(['add', 'sub', 'adds', 'subs'])} {R()}, {R()}, #{r.randrange(30)}")
        elif k == 3: out.append(f"{r.choice(['add', 'sub', 'adds', 'subs'])} {R()}, {R()}, {R()}{sh()}")
        elif k == 4: out.append(f"{r.choice(['and', 'orr', 'eor', 'bic', 'orn', 'eon', 'ands', 'bics'])} {R()}, {R()}, {R()}{sh()}")
        elif k == 5: out.append(f"{r.choice(['and', 'orr', 'eor', 'ands'])} {R()}, {R()}, #{r.choice(LIMM)}")
        elif k == 6: out.append(f"{r.choice(['lsl', 'lsr', 'asr'])} {R()}, {R()}, #{r.randrange(6)}")
        elif k == 7: out.append(r.choice([f"sxtb {R()}, {R()}", f"uxtb {R()}, {R()}", f"ubfx {R()}, {R()}, #{r.randrange(4)}, #{r.randrange(1, 4)}",
                                          f"sbfx {R()}, {R()}, #{r.randrange(4)}, #{r.randrange(1, 4)}", f"ubfiz {R()}, {R()}, #{r.randrange(4)}, #{r.randrange(1,4)}"]))
        elif k == 8: out.append(f"{r.choice(['lslv', 'lsrv', 'asrv'])} {R()}, {R()}, {R()}")
        elif k == 9: out.append(f"{r.choice(['csel', 'csinc', 'csinv', 'csneg'])} {R()}, {R()}, {R()}, {r.choice(COND)}")
        elif k == 10: out.append(r.choice([f"mul {R()}, {R()}, {R()}", f"madd {R()}, {R()}, {R()}, {R()}", f"msub {R()}, {R()}, {R()}, {R()}"]))
        elif k == 11: out.append(f"{r.choice(['cmp', 'cmn'])} {R()}, {r.choice(['#' + str(r.randrange(20)), R()])}")
        elif k == 12: out.append(f"{r.choice(['str', 'ldr'])} {R()}, [x7, #{4 * r.randrange(MEM)}]")
        elif k == 13: out.append(f"cset {R()}, {r.choice(COND)}")
        elif k == 14: out.append(f"{r.choice(['b.' + r.choice(COND), 'cbz ' + R() + ',', 'cbnz ' + R() + ','])} L{min(n, i + 1 + r.randrange(3))}")
        elif k == 15: out.append(f"tst {R()}, #{r.choice(LIMM)}")
        elif k == 16: out.append(f"{r.choice(['udiv', 'sdiv'])} {R()}, {R()}, {R()}")
        elif k == 17: out.append(f"{r.choice(['ccmp', 'ccmn'])} {R()}, {r.choice(['#' + str(r.randrange(32)), R()])}, #{r.randrange(16)}, {r.choice(COND)}")
        elif k == 18: out.append(f"{r.choice(['tbz', 'tbnz'])} {R()}, #{r.randrange(9)}, L{min(n, i + 1 + r.randrange(3))}")
        elif k == 19: out.append(r.choice([f"stur {R()}, [x7, #{4 * r.randrange(MEM)}]", f"ldur {R()}, [x7, #{4 * r.randrange(MEM)}]",
                                           f"stp {R()}, {R()}, [x7, #{4 * r.randrange(MEM - 1)}]", f"ldp {R()}, {R()}, [x7, #{4 * r.randrange(MEM - 1)}]",
                                           (lambda k: f"and w{k}, w{k}, #7\n    ldr {R()}, [x7, x{k}, lsl #2]")(r.randrange(7)), f"ldrsw x{r.randrange(7)}, [x7, #{4 * r.randrange(MEM)}]"]))
        elif k == 20: out.append(f"{r.choice(['add', 'sub'])} w{r.randrange(7)}, w{r.randrange(7)}, w{r.randrange(7)}, {r.choice(['uxtw', 'sxtw', 'uxtb', 'sxth'])} #{r.randrange(3)}")
        elif k == 21: out.append(f"{r.choice(['smull', 'umull'])} x{r.randrange(7)}, {R()}, {R()}")
        else: out.append("bl FN")
    lines = []
    for i, ins in enumerate(out):
        lines += [f"L{i}:", "    " + ins]
    return [".globl f", "f:", "    mov x29, x30"] + lines + [f"L{n}:", "    mov x30, x29", "    ret",
            "FN:", "    add w5, w5, #3", "    ret"]


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    r = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    m = QuantumARM(Config(W=W, regs=tuple(range(NREG)) + (29, 30), sp=False, SLOTS=SLOTS, STEPS=32, MEM=MEM))
    print(f"one interpreter circuit: {m.n} qubits, {len(m.g)} gates")
    stats = dict(ok=0, skipped=0, fail=0)
    for t in range(N):
        lines = gen(r, r.randrange(4, 14))
        code = assemble(lines)
        if code is None: continue
        cw = [int.from_bytes(code[i:i + 4], "little") for i in range(0, len(code), 4)]
        if len(cw) >= SLOTS: continue
        words = layout(cw, SLOTS)
        args = [r.randrange(-20, 40) for _ in range(7)] + [DATA_BASE]
        mem = [r.randrange(-50, 50) for _ in range(MEM)]
        ref = run_reference(words, W, 0, args, MEM, mem, max_steps=32)
        if ref["issues"] or not ref["halted"]:
            stats["skipped"] += 1; continue
        regs = {i: (a - DATA_BASE if i == 7 else a) for i, a in enumerate(args)}
        regs[30] = 4 * (SLOTS - 1)
        st = simulate(m.g, m.n, m.load_bits(words, regs, mem))
        mk = (1 << W) - 1
        got = ([value(st, m.X[k]) for k in range(NREG)], [st[q] for q in m.nzcv], [value(st, x) for x in m.ram],
               [value(st, p) for p in m.pc_hist[:ref["steps"]]])
        exp = ([ref["regs"][k] & mk for k in range(NREG)], ref["flags"], [v & mk for v in ref["mem"]], ref["trace"])
        if got == exp and not any(st[q] for q in m.trap):
            stats["ok"] += 1
        else:
            stats["fail"] += 1
            print("FAIL\n  " + "\n  ".join(lines)); print("  args", args, "mem", mem)
            for name, g_, e_ in zip(("regs", "nzcv", "mem", "trace"), got, exp):
                if g_ != e_: print(f"  {name}: qpu={g_}\n  {' ' * len(name)}  cpu={e_}")
    print(stats)
    sys.exit(1 if stats["fail"] else 0)
