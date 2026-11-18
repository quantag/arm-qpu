# arm-qpu — the same ARM64 machine code on a CPU and on a quantum stored-program processor

The same raw AArch64 (A64) instruction bytes, produced by a standard assembler (clang), are executed:

1. on a conventional ARM64 CPU (Unicorn/QEMU emulator here, or a real ARM machine via `tools/make_harness.py`), and
2. on a **quantum von Neumann interpreter**: one fixed quantum circuit with program memory, a program counter, fetch, decode, register file, ALU and write-back, all made of quantum gates.

The program is **not** compiled into the circuit. Its 32-bit instruction words are loaded as the initial basis state of the program-memory qubits. The same circuit (its SHA-256 is printed by the tests) runs different programs. Nothing inside it is measured or classically dispatched.

## Status (simulation)

| Test | Result |
|---|---|
| `MOVZ X0,#5; ADD X1,X0,#3; EOR X2,X0,X1` | CPU = QPU-sim = Aer = `X0=5, X1=8, X2=13` |
| Second program (`MOVZ X2,#9; EOR X1,X2,X2; ADD X2,X2,#4`), same circuit | match |
| 300 random 4-instruction programs (random regs/immediates) | 300/300 match, all scratch qubits returned to \|0⟩ |
| Program in superposition (`MOVZ X0,#5` and `#4` at once) | outputs `(5,8)` and `(4,7)`, entangled, ~50/50 |
| Interference test (H, U, Z, U†, H) | deterministic flip, which proves the execution is coherent |

Not yet run on physical QPU hardware.

## Scope (honest claim boundary)

* Supported encodings: `MOVZ Xd,#imm16` (hw=0), `ADD Xd,Xn,#imm12` (sh=0), `EOR Xd,Xn,Xm` (no shift); registers X0..X3.
* Registers are W bits wide (default 4). For these instructions the low W bits of the 64-bit ARM result depend only on the low W bits of the operands. So the machine computes **exactly bits [W-1:0]** of the real AArch64 result. That is a restricted model, not full AArch64.
* The program length is fixed when the interpreter is built (no branches yet).
* Register overwrite is made reversible by a controlled-SWAP into a per-step history register.

## Resources (`python3 tools/resources.py`)

| Configuration | Qubits | CZ gates (all-to-all, before routing) |
|---|---|---|
| Full decoder, 4 regs, 3 instructions | 207 | ~11 000 |
| Minimal decoder, 4 regs, 3 instructions | 117 | ~6 600 |
| Minimal decoder, 2 regs, MOVZ+ADD, 2 instructions (hardware target) | 66 | ~1 450 |

The "minimal decoder" stores only the instruction bits the decoder reads. The classical loader checks first that every word is a supported encoding.

## Run

```bash
pip install -r requirements.txt
python3 -m tests.test_equivalence --aer   # CPU vs quantum interpreter
python3 -m tests.test_fuzz 300            # random programs (needs clang + llvm-objcopy)
python3 -m tests.test_coherence           # superposition / interference
python3 tools/resources.py

# on a real ARM64 machine (e.g. Apple Silicon Mac):
python3 tools/make_harness.py arm/prog1.bin > harness.c && cc harness.c -o harness && ./harness
```

## Layout

`arm/` sources, `.o` and raw `.text` `.bin` · `qcpu/machine.py` quantum interpreter · `qcpu/bitsim.py` exact basis-state simulator · `tools/reference.py` CPU reference · `tests/`
