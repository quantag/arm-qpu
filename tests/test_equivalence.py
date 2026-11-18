"""Same A64 bytes on a CPU (Unicorn AArch64 emulator) and on the quantum interpreter.
Run: python3 -m tests.test_equivalence   (from repo root)"""
import hashlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qiskit import qpy
import io
from qcpu.machine import Config, QuantumARM, words_from_bytes, validate
from qcpu.bitsim import simulate_basis, read_reg
from tools.reference import run_reference


def circuit_hash(qc):
    buf = io.BytesIO(); qpy.dump(qc, buf); return hashlib.sha256(buf.getvalue()).hexdigest()[:16]


def check(machine, path, aer=False):
    cfg = machine.cfg
    code = open(path, "rb").read()
    words = words_from_bytes(code)
    validate(words, cfg)
    assert len(words) == cfg.STEPS, f"{path}: interpreter is built for {cfg.STEPS} steps"
    ref = [v & ((1 << cfg.W) - 1) for v in run_reference(code, cfg.NREG)]
    full = machine.load_program(words).compose(machine.qc)
    out = simulate_basis(full)
    q = [read_reg(full, out, r) for r in machine.X]
    dirty = [r.name for r in machine.scratch if read_reg(full, out, r)]
    mem_ok = all(read_reg(full, out, machine.mem[s]) == read_reg(full, simulate_basis(machine.load_program(words)), machine.mem[s])
                 for s in range(cfg.SLOTS))
    pc = read_reg(full, out, machine.pc)
    line = f"{os.path.basename(path):10s} bytes={code.hex()}  CPU={ref}  QPU-sim={q}"
    ok = q == ref and not dirty and mem_ok and pc == cfg.STEPS % cfg.SLOTS
    if aer:
        q2 = run_aer(machine, full)
        line += f"  Aer={q2}"
        ok &= q2 == ref
    print(("PASS " if ok else "FAIL ") + line + (f"  dirty={dirty}" if dirty else ""))
    return ok


def run_aer(machine, full):
    from qiskit import ClassicalRegister, transpile
    from qiskit_aer import AerSimulator
    qc = full.copy()
    cregs = []
    for r in machine.X:
        cr = ClassicalRegister(r.size, "c" + r.name); qc.add_register(cr); qc.measure(r, cr); cregs.append(cr)
    sim = AerSimulator(method="matrix_product_state")
    tqc = transpile(qc, basis_gates=["u", "x", "cx", "ccx", "cswap", "measure"], optimization_level=0)
    res = sim.run(tqc, shots=8).result().get_counts()
    assert len(res) == 1, res
    key = next(iter(res)).split()[::-1]   # cregs printed in reverse order
    return [int(k, 2) for k in key]


if __name__ == "__main__":
    aer = "--aer" in sys.argv
    ok = True
    m3 = QuantumARM(Config(W=4, NREG=4, STEPS=3, SLOTS=4, decoder="full"))
    print(f"[full decoder, 3 steps] qubits={m3.qc.num_qubits} interpreter sha256={circuit_hash(m3.qc)}")
    for p in ("arm/prog1.bin", "arm/prog3.bin"):
        ok &= check(m3, p, aer)
    m2 = QuantumARM(Config(W=4, NREG=2, STEPS=2, SLOTS=2, decoder="min", ops=("movz", "add")))
    print(f"[hardware-size, 2 steps] qubits={m2.qc.num_qubits} interpreter sha256={circuit_hash(m2.qc)}")
    ok &= check(m2, "arm/prog2.bin", aer)
    sys.exit(0 if ok else 1)
