# arm-qpu: run an ARM64 binary on a quantum computer

`arm_qpu.py` takes an AArch64 binary compiled from C (or any language), runs it on a
**quantum stored-program (von Neumann) processor** made entirely of quantum gates, runs the
same bytes on an ARM CPU emulator, and writes a report comparing the two.

The quantum processor is **one fixed reversible circuit** (X, CNOT, Toffoli, Fredkin gates).
It has program memory, a program counter, fetch, a decoder for 32 A64 instruction classes,
31 registers + SP, NZCV flags, data memory with a stack, an ALU (adder, barrel shifter,
multiplier, divider, bitmask decoder), and a branch unit with calls and returns.
The binary is **not compiled into the circuit**: its 32-bit instruction words are loaded as
the initial state of the program-memory qubits. Nothing inside the circuit is measured or
classically dispatched.

## Quick start: factorization in C

`examples/factor.c`:

```c
int smallest_factor(int n) {
    for (int d = 2; d * d <= n; d++)
        if (n % d == 0)
            return d;
    return n;
}

int factorize(int n, int *out) {          /* writes the prime factors to out[] */
    int k = 0;
    while (n > 1) {
        int p = smallest_factor(n);
        out[k++] = p;
        n /= p;
    }
    return k;
}
```

Compile it to an AArch64 object file (any of these):

```bash
# Linux / any OS with clang (cross-compiles, no ARM machine needed)
clang --target=aarch64-linux-gnu -O1 -c examples/factor.c -o factor.o

# macOS on Apple Silicon (native arm64 Mach-O)
clang -O1 -c examples/factor.c -o factor.o

# GCC cross toolchain
aarch64-linux-gnu-gcc -O1 -c examples/factor.c -o factor.o
```

Run it on the QPU (`&0` = pointer to data-memory cell 0, where the factors are written):

```bash
pip install -r requirements.txt
python3 arm_qpu.py factor.o --entry factorize --args 84 '&0'
```

```
MATCH: the QPU produced the same result as the CPU
return value X0: CPU = 4, QPU = 4
quantum machine: 26903 qubits, 4616376 gates (2564408 Toffoli), 92 steps
report: factor.factorize.report.md
```

The report shows data memory `[2, 2, 3, 7, ...]` on both machines, identical registers,
flags and step-by-step PC trace, the disassembly with every instruction marked supported or
not, and the circuit's resources.

Options: `--entry FUNC` (default `main`, else the first function), `--args` for X0, X1, ...
(`&k` = pointer to data cell k), `--mem=1,2,3` to initialise data memory (32-bit cells),
`--config config.json`, `--report PREFIX`.

## config.json

```json
{
  "backend": "simulator",
  "register_width": "auto",
  "registers": "auto",
  "memory_words": "auto",
  "max_steps": "auto",
  "isa": "full",
  "shots": 1024,
  "aer": {"method": "matrix_product_state"},
  "ibm": {"channel": "ibm_quantum_platform", "token": "env:IBM_QUANTUM_TOKEN",
          "instance": null, "backend": "least_busy", "optimization_level": 1}
}
```

| key | meaning |
|---|---|
| `backend` | `simulator`: exact simulation of the circuit on its basis-state input (fast, any size). `aer`: Qiskit Aer, sampled with `shots`. `ibm`: IBM Quantum hardware through Qiskit Runtime (`token` may be `env:VAR`). |
| `register_width` | W, bits per register (8 to 16). `auto` = smallest W that holds the code addresses. |
| `registers` | `auto` = only registers the code uses; `all` = X0..X30; or a list. |
| `memory_words` | data memory in 4-byte cells; `auto` = 2^(W-4) if the code touches memory. |
| `max_steps` | machine cycles in the circuit; `auto` = what the CPU reference needed. |
| `isa` | `full` = decoder implements every supported class; `auto` = only the classes the program uses (smaller circuit). |

Before submitting to hardware the runner checks the circuit's width against the device. A run
that does not fit is reported as not submitted, with the reason.

## What is implemented

| group | instructions |
|---|---|
| move | MOVZ, MOVN, MOVK, MOV (all aliases) |
| arithmetic | ADD, ADDS, SUB, SUBS (immediate, shifted register, extended register), CMP, CMN, NEG |
| logic | AND, ORR, EOR, ANDS, BIC, ORN, EON, BICS (register and bitmask immediate), TST, MVN |
| shifts / bitfields | LSL, LSR, ASR (immediate and register), UBFM, SBFM, UBFX, SBFX, UBFIZ, SBFIZ, UXTB/H, SXTB/H/W |
| multiply / divide | MUL, MADD, MSUB, MNEG, SMULL, UMULL, SMADDL, UMADDL, SDIV, UDIV |
| conditional | CSEL, CSINC, CSINV, CSNEG, CSET, CSETM, CINC, CNEG, CCMP, CCMN |
| branches | B, B.cond, CBZ, CBNZ, TBZ, TBNZ, BL, BLR, BR, RET |
| memory | LDR, STR, LDRSW (unsigned offset, unscaled LDUR/STUR, pre-index, post-index, register offset with LSL/UXTW/SXTW), LDP, STP (offset, pre-, post-index) |
| other | NOP and hints; HLT ends the run |

Anything else (byte/halfword loads, ROR, BFI/BFXIL, CLZ/REV, ADR/ADRP, floating point, SIMD,
system instructions) is listed in the report's "Unsupported instructions" table. A run that
reaches one stops with a trap; the CPU reference reports it first.

## The W-bit model, and when results are exact

The quantum registers are W bits wide. A W-bit register stands for the 64-bit (or 32-bit)
value you get by sign-extending it. When every value of a run has that form, the quantum
machine reproduces the AArch64 result exactly: the low W bits of every register and memory
cell, the NZCV flags, and the control flow.

The CPU reference checks every value of the run and lists any that does not fit in the
report's "Model check" section. Example: at `-O1`, clang compiles `n / 10` as a multiply by
`0xCCCCCCCD` and a 35-bit shift. Those values cannot fit in W ≤ 16, so the report flags them.
The same function at `-O0` (a real `sdiv`) matches.

Code addresses are `4 × slot` and data pointers are offsets into data memory. Both must be
non-negative W-bit values, which is why `register_width: auto` grows W with program size.

## Tests

```bash
python3 -m tests.test_c_programs    # 16 C cases x -O0/-O1/-O2 through arm_qpu.py (examples/*.c)
python3 -m tests.test_fuzz 500      # random A64 programs: one circuit, CPU vs QPU, regs/flags/memory/trace
```

`test_c_programs` covers factorization, gcd, Fibonacci, primality, popcount, Collatz, integer
square root, modular exponentiation, max3, function calls, bubble sort (in memory) and binary
search. Every case matches the CPU, except the two flagged `digit_sum` cases described above.

## How the quantum machine works

One machine cycle is a reversible block:

1. **Fetch.** IR ^= MEM[PC], with each program slot selected by a comparator on the PC qubits.
2. **Decode.** One-hot class flags from IR bit patterns, all gated by a `running` qubit.
3. **Execute.** Register-file reads are multiplexers on the Rn/Rm/Rt fields. Then the ALU:
   ripple adder with flags, barrel shifter, shift-add multiplier, restoring divider, logical
   bitmask decoder, condition evaluation, and address generation.
4. **Copy out, then uncompute.** The cycle's results are copied into fresh per-step
   registers, and the whole compute block runs backwards, so every scratch qubit returns to |0⟩.
5. **Commit.** Controlled-SWAPs move the results into registers, flags, memory and PC. The
   displaced old values stay behind as history, which makes overwrites and jumps unitary
   (Landauer/Bennett embedding). The PC history doubles as an execution trace.

After `HLT` (the return address the entry function starts with), the remaining cycles are
no-ops. That is the synchronisation the Quantum Control Machine paper requires.

Code: `qcpu/machine.py` (circuit), `qcpu/a64.py` (instruction classes and static check),
`qcpu/reference.py` (CPU reference and model check), `qcpu/loader.py` (ELF/Mach-O with BL
relocations), `qcpu/bitsim.py` (exact simulator), `arm_qpu.py` (CLI and reports).

## Honest status

* Simulation: verified as above.
* Hardware: the backend is implemented, but the circuits are far larger than today's devices.
  The smallest real program (`subs; cneg; ret`, `isa: auto`) needs 666 qubits and about 9 000
  Toffoli gates; factorization needs about 27 000 qubits. Running on a QPU means a much smaller
  machine profile, or fault-tolerant hardware.
* There is no speed-up: a classical program on a QPU is a very expensive reversible computer.
  The value is a verified bridge from ordinary binaries to quantum circuits: reversible oracles,
  resource estimation, and a quantum control-flow test bed. See `docs/prior_work.md` and the
  QA64 roadmap there.

## Prior work

* Mariantoni et al., *Implementing the quantum von Neumann architecture with superconducting circuits*, Science 2011: quantum CPU and memory, instructions classical.
* Fitzjohn et al., Qx86 (Intel 8080/Z80 on IBM Q), IEEE TQE 2022 / QIP 2024: the PC and fetch/decode are classical; each instruction runs as a separate quantum job.
* Yuan, Villanyi, Carbin, *Quantum Control Machine*, OOPSLA 2024: limits of control flow in superposition (injectivity, synchronisation).
* Zhang, Ying, *Quantum Register Machine*, PLDI 2025: an ISA with a quantum PC, qif/fiq and recursion; no public implementation.
