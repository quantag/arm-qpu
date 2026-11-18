"""Resource report: logical qubits, Toffoli-level gates, and 2-qubit gate count / depth after
transpiling to a generic hardware basis (all-to-all connectivity; real devices add routing SWAPs)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qiskit import transpile
from qcpu.machine import Config, QuantumARM

CONFIGS = {
    "full decoder, 4 regs, 3 steps (prog1)": Config(W=4, NREG=4, STEPS=3, SLOTS=4, decoder="full"),
    "min decoder, 4 regs, 3 steps (prog1)": Config(W=4, NREG=4, STEPS=3, SLOTS=4, decoder="min"),
    "min decoder, 2 regs, 2 steps, MOVZ+ADD (prog2)": Config(W=4, NREG=2, STEPS=2, SLOTS=2, decoder="min", ops=("movz", "add")),
}
if __name__ == "__main__":
    for name, cfg in CONFIGS.items():
        qc = QuantumARM(cfg).qc
        ops = qc.count_ops()
        t = transpile(qc, basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=1)
        n2 = t.count_ops().get("cz", 0)
        print(f"{name}\n  qubits={qc.num_qubits}  high-level={dict(ops)}\n  -> CZ={n2}  depth={t.depth()}  2q-depth={t.depth(lambda i: i.operation.num_qubits == 2)}")
