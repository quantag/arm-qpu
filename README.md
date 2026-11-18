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

One command compiles it for AArch64 and runs it on the QPU and the CPU (`&0` = pointer to
data-memory cell 0, where the factors are written):

```bash
python3 arm_qpu.py examples/factor.c --entry factorize --args 84 '&0'
```

```
compiled: clang --target=aarch64-linux-gnu -O1 -ffreestanding -c examples/factor.c -o .../factor.o
MATCH: the QPU produced the same result as the CPU
return value X0: CPU = 4, QPU = 4
quantum machine: 21201 qubits, 3491712 gates (1917792 Toffoli), 72 steps
report: examples/factor.factorize.report.md
```

The report shows data memory `[2, 2, 3, 7, ...]` on both machines, identical registers,
flags and step-by-step PC trace, the disassembly with every instruction marked supported or
not, and the circuit's resources.

Options: `--entry FUNC` (default `main`, else the first function), `--args` for X0, X1, ...
(`&k` = pointer to data cell k), `--mem=1,2,3` to initialise data memory (32-bit cells),
`--cc clang|gcc` and `-O 0|1|2|s` for `.c` input, `--config config.json`, `--report PREFIX`.

## Compiling C to an ARM64 binary: clang or gcc

Both compilers are supported and tested; they produce the same results. You can pass a `.c`
file (the runner compiles it), or compile yourself and pass the object file (`.o`).

| compiler | command | output |
|---|---|---|
| clang, any OS (cross-compiles, no ARM machine needed) | `clang --target=aarch64-linux-gnu -O1 -ffreestanding -c prog.c -o prog.o` | ELF |
| clang on macOS, Apple Silicon | `clang -O1 -c prog.c -o prog.o` | Mach-O |
| gcc, Linux cross toolchain | `aarch64-linux-gnu-gcc -O1 -ffreestanding -c prog.c -o prog.o` | ELF |
| gcc, Arm GNU Toolchain (Windows, macOS, Linux) | `aarch64-none-elf-gcc -O1 -ffreestanding -c prog.c -o prog.o` | ELF |
| gcc on a native ARM64 Linux machine (Raspberry Pi, Graviton, ...) | `gcc -O1 -c prog.c -o prog.o` | ELF |

```bash
python3 arm_qpu.py prog.o --entry my_function --args 5 7
```

With `.c` input, `compiler` in `config.json` (or `--cc`) chooses the compiler. `auto` tries
`clang`, then `aarch64-linux-gnu-gcc`, `aarch64-none-linux-gnu-gcc`, `aarch64-none-elf-gcc`
and `aarch64-elf-gcc`. Write plain functions with no libc calls: there is no `printf` or
`malloc` on the quantum machine. Return results in the return value or through a pointer
argument (`&k`).

## Step-by-step: Linux (Ubuntu / Debian)

```bash
# 1. tools: Python, git, and a compiler (clang, or gcc for AArch64, or both)
sudo apt update
sudo apt install -y python3 python3-venv git clang gcc-aarch64-linux-gnu

# 2. get the code and its Python packages
git clone https://github.com/quantag/arm-qpu.git
cd arm-qpu
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. run C on the quantum machine, with either compiler
python3 arm_qpu.py examples/factor.c --entry factorize --args 84 '&0'
python3 arm_qpu.py examples/factor.c --cc gcc --entry factorize --args 84 '&0'

# 4. or compile yourself and pass the object file
aarch64-linux-gnu-gcc -O2 -c examples/algorithms.c -o algorithms.o
python3 arm_qpu.py algorithms.o --entry gcd --args 84 36

# 5. the report
less examples/factor.factorize.report.md
```

On Fedora: `sudo dnf install clang gcc-aarch64-linux-gnu python3 git`. On Arch Linux:
`sudo pacman -S clang aarch64-linux-gnu-gcc python git`.

## Step-by-step: Windows

### Option A: native Windows (PowerShell)

```powershell
# 1. Python, git and clang/LLVM (clang includes the AArch64 cross compiler)
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
winget install -e --id LLVM.LLVM
# open a NEW PowerShell window so PATH picks up python, git and clang

# 2. get the code and its Python packages
git clone https://github.com/quantag/arm-qpu.git
cd arm-qpu
py -m venv .venv
.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

# 3. run C on the quantum machine (keep '&0' in single quotes in PowerShell)
python arm_qpu.py examples\factor.c --entry factorize --args 84 '&0'
```

**gcc on Windows.** Use the Arm GNU Toolchain:

1. Download the Windows-hosted (mingw-w64) package for the target "AArch64 bare-metal
   (aarch64-none-elf)" from https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads.
2. Unzip it, for example to `C:\arm-gnu-toolchain`.
3. Add its `bin` folder to PATH, then check: `aarch64-none-elf-gcc --version`.
4. Run with gcc:

```powershell
python arm_qpu.py examples\factor.c --cc gcc --entry factorize --args 84 '&0'
# or compile yourself:
aarch64-none-elf-gcc -O1 -ffreestanding -c examples\factor.c -o factor.o
python arm_qpu.py factor.o --entry factorize --args 84 '&0'
```

In `cmd.exe` write the pointer argument as `"&0"` (double quotes).

### Option B: WSL2 (Linux inside Windows)

```powershell
wsl --install -d Ubuntu      # once, then reboot and open "Ubuntu" from the Start menu
```

Inside Ubuntu, follow the Linux steps above. This gives you both compilers through `apt`.

## Step-by-step: macOS (Apple Silicon)

```bash
xcode-select --install                 # Apple clang (native arm64)
git clone https://github.com/quantag/arm-qpu.git && cd arm-qpu
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 arm_qpu.py examples/factor.c --entry factorize --args 84 '&0'
# gcc: brew install aarch64-elf-gcc, then add --cc gcc
```

## config.json

```json
{
  "backend": "simulator",
  "register_width": "auto",
  "registers": "auto",
  "memory_words": "auto",
  "max_steps": "auto",
  "isa": "full",
  "compiler": "auto",
  "cflags": ["-O1"],
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
| `compiler` | for `.c` input: `auto`, `clang`, `gcc`, or a command name / path. |
| `cflags` | compiler flags for `.c` input, default `["-O1"]`. |

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
report's "Model check" section. Example: clang at `-O1` (and gcc at every level) compiles
`n / 10` as a multiply by `0xCCCCCCCD` and a 35-bit shift. Those values cannot fit in W ≤ 16,
so the report flags them. With clang at `-O0` the same function is a real `sdiv` and matches.

Code addresses are `4 × slot` and data pointers are offsets into data memory. Both must be
non-negative W-bit values, which is why `register_width: auto` grows W with program size.

## Tests

```bash
python3 -m tests.test_c_programs clang   # 16 C cases x -O0/-O1/-O2 through arm_qpu.py (examples/*.c)
python3 -m tests.test_c_programs gcc     # the same with aarch64-linux-gnu-gcc
python3 -m tests.test_fuzz 500      # random A64 programs: one circuit, CPU vs QPU, regs/flags/memory/trace
```

`test_c_programs` covers factorization, gcd, Fibonacci, primality, popcount, Collatz, integer
square root, modular exponentiation, max3, function calls, bubble sort (in memory) and binary
search. With both clang and gcc every case matches the CPU, except the flagged `digit_sum`
cases described above (gcc uses the multiply-by-constant trick even at `-O0`).
The largest case (`bubble_sort` at `-O0`, about 800 000 qubits and 180 million gates) needs
several GB of RAM. Run the two suites one after the other, not in parallel.

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
