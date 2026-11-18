"""Coherence tests: the interpreter is a unitary with no measurement / classical dispatch inside.
1) Superposed program: MOVZ X0,#5 and MOVZ X0,#4 differ in one instruction bit. Put that
   program-memory qubit in |+>: one run executes BOTH programs, outputs are entangled.
2) Interference (Deutsch-style): H(bit) -> U -> Z(X1[0]) -> U^dagger -> H(bit) -> measure.
   Outcome flips deterministically only if the whole fetch/decode/execute path is coherent;
   any hidden measurement or classical branching would give 0/1 at 50/50."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qiskit import ClassicalRegister, transpile
from qiskit_aer import AerSimulator
from qcpu.machine import Config, QuantumARM, words_from_bytes

BASIS = ["u", "x", "h", "z", "cx", "ccx", "cswap", "measure"]
sim = AerSimulator(method="matrix_product_state")


def run(qc, shots=2000):
    return sim.run(transpile(qc, basis_gates=BASIS, optimization_level=0), shots=shots).result().get_counts()


if __name__ == "__main__":
    m = QuantumARM(Config(W=4, NREG=2, STEPS=2, SLOTS=2, decoder="min", ops=("movz", "add")))
    assert not any(i.operation.name in ("measure", "reset", "if_else") for i in m.qc.data)
    words = words_from_bytes(open("arm/prog2.bin", "rb").read())   # MOVZ X0,#5 ; ADD X1,X0,#3
    bit = m.mem[0][m.bitpos[5]]     # instruction 0, bit 5 = imm16[0]: #5 <-> #4

    qc = m.load_program(words); qc.h(bit); qc.compose(m.qc, inplace=True)
    c0, c1 = ClassicalRegister(4, "x0"), ClassicalRegister(4, "x1")
    qc.add_register(c0); qc.add_register(c1); qc.measure(m.X[0], c0); qc.measure(m.X[1], c1)
    counts = {tuple(int(v, 2) for v in k.split()[::-1]): n for k, n in run(qc).items()}
    print("superposed program -> (X0, X1):", counts)
    assert set(counts) == {(5, 8), (4, 7)}

    def interfere(with_z):
        qc = m.load_program(words); qc.h(bit); qc.compose(m.qc, inplace=True)
        if with_z: qc.z(m.X[1][0])
        qc.compose(m.qc.inverse(), inplace=True); qc.h(bit)
        cr = ClassicalRegister(1, "w"); qc.add_register(cr); qc.measure(bit, cr)
        return run(qc)
    a, b = interfere(False), interfere(True)
    print("interference without phase:", a, " with phase on X1[0]:", b)
    # deterministic and opposite outcomes; a decohered/classically-dispatched machine gives 50/50 in the second case
    assert len(a) == 1 and len(b) == 1 and set(a) != set(b)
    print("PASS: coherent execution of a superposition of two ARM programs")
