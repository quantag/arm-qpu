"""Interpreter vs specialised reversible circuit for one function.

    int f(int a, int b) { return (a + b) * (a ^ b); }     // clang -O1: add, eor, mul, ret

Interpreter: the quantum machine running the compiled binary (full decoder, and a decoder reduced
to the classes the function uses). Specialised: a reversible circuit for this one function, built
from the same adder and multiplier primitives (compute, copy the result, uncompute), which is what
partial evaluation of the interpreter for this program would aim at. Both are checked against Python.
Run: python3 tools/compare_specialized.py"""
import os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collections import Counter
from qcpu.bitsim import simulate, value
from qcpu.loader import ObjectImage
from qcpu.machine import Config, QuantumARM
from qcpu.reference import layout

W = 8
d = tempfile.mkdtemp()
open(f"{d}/f.c", "w").write("int f(int a, int b) { return (a + b) * (a ^ b); }\n")
subprocess.run(["clang", "--target=aarch64-linux-gnu", "-O1", "-c", f"{d}/f.c", "-o", f"{d}/f.o"], check=True)
prog = ObjectImage(f"{d}/f.o").link("f")
words = layout(prog["words"], 8)
sx = lambda v: (v & 255) - 256 if v & 128 else v & 255
ref = lambda a, b: sx((a + b) * (a ^ b))
rows = []

for name, classes in (("interpreter, full decoder (27 classes)", None),
                      ("interpreter, reduced decoder", ("addsub_reg", "logic_reg", "madd", "bra", "hlt"))):
    kw = dict(classes=classes) if classes else {}
    m = QuantumARM(Config(W=W, regs=(0, 1, 8, 9, 30), SLOTS=8, STEPS=5, MEM=0, **kw))
    r = random.Random(1)
    for _ in range(200):
        a, b = r.randrange(-128, 128), r.randrange(-128, 128)
        st = simulate(m.g, m.n, m.load_bits(words, {0: a, 1: b, 30: 28}))
        assert sx(value(st, m.X[0])) == ref(a, b)
    c = m.counts()
    rows.append((name, m.n, sum(c.values()), c.get("ccx", 0)))

# specialised circuit: out ^= (a + b) * (a ^ b), all scratch returned to |0>
s = QuantumARM(Config(W=W, regs=(0,), SLOTS=2, STEPS=0, MEM=0), defer=True)
s.g, s.ptr = [], 0
A, B, OUT = s.reg("a", W), s.reg("b", W), s.reg("out", W)
m0 = len(s.g)
S, _ = s.add(A, B, s.ZERO, W)
X = s.alloc(W)
for i in range(W):
    s.cx(A[i], X[i]); s.cx(B[i], X[i])
P = s._mul(S, X)
m1 = len(s.g)
for i in range(W): s.cx(P[i], OUT[i])
s.g.extend(reversed(s.g[m0:m1]))
r = random.Random(2)
for _ in range(2000):
    a, b = r.randrange(-128, 128), r.randrange(-128, 128)
    ones = [A[i] for i in range(W) if (a >> i) & 1] + [B[i] for i in range(W) if (b >> i) & 1]
    st = simulate(s.g, s.n, ones)
    assert sx(value(st, OUT)) == ref(a, b)
    assert not any(st[q] for q in s.pool[:s.ptr] + list(X))
c = Counter(g[0] for g in s.g)
rows.append(("specialised reversible circuit", s.n, sum(c.values()), c.get("ccx", 0)))

print(f"f(a, b) = (a + b) * (a ^ b), W = {W}, {len(prog['words'])} instructions, 5 machine cycles")
print(f"{'':42s} {'qubits':>8s} {'gates':>9s} {'Toffoli':>9s}")
for name, q, g, t in rows:
    print(f"{name:42s} {q:8d} {g:9d} {t:9d}")
print(f"ratio interpreter (full) / specialised: {rows[0][2] / rows[2][2]:.0f}x gates, {rows[0][1] / rows[2][1]:.0f}x qubits")
