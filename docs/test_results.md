# Test results

Generated 2026-11-20 20:01 CET by `tools/test_report.py`.

**Overall: all tests passed.**

- code: commit `75717a197515f4ee85c98c23af600d1189ff1495`
- Python 3.13.18 on Linux-6.18.44-fc-v726-x86_64-with-glibc2.39
- qiskit 2.6.2, qiskit-aer 0.18.4, unicorn 2.1.4, lief 1.0.0, capstone 5.0.9
- Ubuntu clang version 18.1.3 (1ubuntu1)
- aarch64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0

Outcome classes: **match** (QPU = CPU after every cycle, model check clean); **match-flagged** (equal, but the model check reported values outside the W-bit model); **flagged** (different, and the model check reported it); **UNFLAGGED** (different, model check silent: a bug; required to be 0); **discarded** (the CPU run did not halt normally, the program did not assemble, or it is too long).

## Differential fuzzing

`-m tests.test_fuzz 300 7 8,12,16` exit code 0, 109 s

```
W=8 seed=15: {"generated": 300, "rejected by assembler": 36, "too long": 0, "discarded (CPU did not halt)": 0, "match": 91, "match-flagged": 127, "flagged": 46, "UNFLAGGED": 0}
W=12 seed=19: {"generated": 300, "rejected by assembler": 37, "too long": 0, "discarded (CPU did not halt)": 0, "match": 150, "match-flagged": 77, "flagged": 36, "UNFLAGGED": 0}
W=16 seed=23: {"generated": 300, "rejected by assembler": 35, "too long": 0, "discarded (CPU did not halt)": 0, "match": 162, "match-flagged": 71, "flagged": 32, "UNFLAGGED": 0}
```

## Boundary cases

`-m tests.test_edges 8,12,16` exit code 0, 591 s

```
W=8: {"extend": {"match-flagged": 162, "flagged": 122, "match": 184}, "flags": {"flagged": 154, "match-flagged": 18, "match": 88}, "shift": {"match-flagged": 238, "flagged": 78, "match": 87}, "w/x": {"flagged": 3, "match": 5, "match-flagged": 5}, "memory": {"flagged": 14, "match-flagged": 4, "match": 8}, "mul/div": {"match-flagged": 71, "flagged": 13, "match": 46}, "bitfield": {"match-flagged": 7, "match": 6}, "pointer": {"flagged": 13, "match": 26, "match-flagged": 5}, "constants": {"flagged": 19, "match-flagged": 2, "match": 14}}
W=12: {"extend": {"match-flagged": 120, "match": 401, "flagged": 91}, "flags": {"flagged": 160, "match-flagged": 8, "match": 172}, "shift": {"match-flagged": 262, "flagged": 36, "match": 229}, "w/x": {"flagged": 5, "match": 10, "match-flagged": 2}, "memory": {"flagged": 17, "match-flagged": 4, "match": 13}, "mul/div": {"match-flagged": 74, "flagged": 7, "match": 89}, "bitfield": {"match-flagged": 6, "match": 11}, "pointer": {"flagged": 13, "match": 26, "match-flagged": 5}, "constants": {"flagged": 19, "match-flagged": 2, "match": 14}}
W=16: {"extend": {"match-flagged": 93, "match": 454, "flagged": 65}, "flags": {"flagged": 160, "match-flagged": 8, "match": 172}, "shift": {"match-flagged": 236, "flagged": 34, "match": 240}, "w/x": {"flagged": 5, "match": 10, "match-flagged": 2}, "memory": {"flagged": 17, "match-flagged": 4, "match": 13}, "mul/div": {"match-flagged": 74, "flagged": 7, "match": 89}, "bitfield": {"match-flagged": 6, "match": 11}, "pointer": {"flagged": 13, "match": 26, "match-flagged": 5}, "constants": {"flagged": 19, "match-flagged": 2, "match": 14}}
no unflagged mismatch
```

## Fast simulator vs full circuit vs Aer

`-m tests.test_simulators 100 5` exit code 0, 63 s

```
full circuit vs fast replay: 100/100 identical (seed 5); full: 5691 qubits 644920 gates, fast reports 5691 qubits 644920 gates
Aer vs fast, program starting 'movz w0, #5': 1101 qubits, fast [8, 0, 253], Aer [8, 0, 253], equal
Aer vs fast, program starting 'mov w1, #3': 1101 qubits, fast [7, 0, 3], Aer [7, 0, 3], equal
Aer vs fast, program starting 'cmp w0, #4': 1101 qubits, fast [7, 7, 0], Aer [7, 7, 0], equal
PASS
```

## Coherence: superposition of two programs

`-m tests.test_coherence` exit code 0, 7 s

```
machine: 418 qubits, 7448 gates (4880 Toffoli)
1) superposed program -> X0: {7: 993, 8: 1007}
2) interference without phase: {'1': 2000}  with phase on X0[0]: {'0': 2000}
PASS: the machine executes a superposition of two ARM programs coherently
```

## Quantum branching

`-m tests.test_branching` exit code 0, 72 s

```
machine: 868 qubits, 42198 gates (27612 Toffoli), 13 cycles
A) (x, X2, running after cycle 3): {(0, 0, 0): 974, (1, 6, 1): 1026}
B) after uncompute, without phase: {'0': 2000}  with phase on X2[1]: {'1': 2000}
C) without uncompute: {'1': 967, '0': 1033}
PASS: superposed input, two paths of different length, coherent after uncompute
```

## Grover search with compiled C oracles

`-m tests.test_grover` exit code 0, 9 s

```
basis check: the quantum machine computes f(x) correctly for all 4 inputs
simulator: exact sparse state vector; optimal number of iterations for M/N = 1/4: 1
k = 1: P(solution) exact 1.0000, theory 1.0000; measured 1000/1000 = 1.000 [95% CI 0.996..1.000]; workspace restored with probability 1.0000 (0.0 s)
PASS: amplitudes amplified as Grover's algorithm predicts, workspace restored in every shot
compiled: /usr/bin/clang --target=aarch64-linux-gnu -O1 -fno-stack-protector -I/home/claude/arm-qpu/include -c /home/claude/arm-qpu/examples/grover_tiny.c -o /tmp/arm_qpu_mfompjra/grover_tiny.o
predicate is_two: 3 instructions, solutions over 0..3: [2] (M = 1 of N = 4); cycles per input 4..4, common bound T = 4
machine: W = 8, 4 instruction classes, 4 program slots, 4 cycles: 410 qubits, 7960 gates (5128 Toffoli) per run of U
basis check: the quantum machine computes f(x) correctly for all 4 inputs
simulator: Qiskit Aer, matrix product state; optimal number of iterations for M/N = 1/4: 1
k = 1: P(solution) theory 1.0000; measured 200/200 = 1.000 [95% CI 0.981..1.000]; workspace restored with probability 1.0000 (2.8 s)
PASS: amplitudes amplified as Grover's algorithm predicts, workspace restored in every shot
2) grover_tiny: exact and Aer agree (P = 1)
compiled: /usr/bin/clang --target=aarch64-linux-gnu -O1 -fno-stack-protector -I/home/claude/arm-qpu/include -c /home/claude/arm-qpu/examples/grover_divisor.c -o /tmp/arm_qpu_hl2jdov5/grover_divisor.o
predicate divides91: 10 instructions, solutions over 0..15: [7, 13] (M = 2 of N = 16); cycles per input 5..9, common bound T = 9
machine: W = 8, 9 instruction classes, 16 program slots, 9 cycles: 1762 qubits, 85374 gates (49680 Toffoli) per run of U
basis check: the quantum machine computes f(x) correctly for all 16 inputs
simulator: exact sparse state vector; optimal number of iterations for M/N = 2/16: 2
k = 0: P(solution) exact 0.1250, theory 0.1250; measured 142/1000 = 0.142 [95% CI 0.122..0.165]; workspace restored with probability 1.0000 (0.0 s)
k = 1: P(solution) exact 0.7812, theory 0.7813; measured 796/1000 = 0.796 [95% CI 0.770..0.820]; workspace restored with probability 1.0000 (0.0 s)
k = 2: P(solution) exact 0.9453, theory 0.9453; measured 950/1000 = 0.950 [95% CI 0.935..0.962]; workspace restored with probability 1.0000 (0.1 s)
k = 3: P(solution) exact 0.3301, theory 0.3301; measured 344/1000 = 0.344 [95% CI 0.315..0.374]; workspace restored with probability 1.0000 (0.1 s)
PASS: amplitudes amplified as Grover's algorithm predicts, workspace restored in every shot
3) grover_divisor: P(k) = sin^2((2k+1) theta) for k = 0..3, workspace restored
compiled: /usr/bin/clang --target=aarch64-linux-gnu -O1 -fno-stack-protector -I/home/claude/arm-qpu/include -c /home/claude/arm-qpu/examples/grover_square.c -o /tmp/arm_qpu_6kq8khyi/grover_square.o
predicate is_root: 6 instructions, solutions over 0..15: [3, 5, 11, 13] (M = 4 of N = 16); cycles per input 7..7, common bound T = 7
machine: W = 9, 7 instruction classes, 8 program slots, 7 cycles: 1228 qubits, 50302 gates (29582 Toffoli) per run of U
basis check: the quantum machine computes f(x) correctly for all 16 inputs
simulator: exact sparse state vector; optimal number of iterations for M/N = 4/16: 1
k = 1: P(solution) exact 1.0000, theory 1.0000; measured 1000/1000 = 1.000 [95% CI 0.996..1.000]; workspace restored with probability 1.0000 (0.0 s)
PASS: amplitudes amplified as Grover's algorithm predicts, workspace restored in every shot
4) grover_square: one iteration, P = 1
compiled: /usr/bin/clang --target=aarch64-linux-gnu -O1 -fno-stack-protector -I/home/claude/arm-qpu/include -c /home/claude/arm-qpu/examples/grover_divisor.c -o /tmp/arm_qpu_v290fh0h/grover_divisor.o
predicate divides91: 10 instructions, solutions over 0..15: [7, 13] (M = 2 of N = 16); cycles per input 5..9, common bound T = 9
machine: W = 8, 9 instruction classes, 16 program slots, 9 cycles: 1762 qubits, 85374 gates (49680 Toffoli) per run of U
basis check: the quantum machine computes f(x) correctly for all 16 inputs
simulator: exact sparse state vector; optimal number of iterations for M/N = 2/16: 2
k = 2: P(solution) exact 0.0547, theory 0.9453; measured 57/1000 = 0.057 [95% CI 0.044..0.073]; workspace restored with probability 0.0000 (0.9 s)
without U^-1 the oracle is not clean: the input stays entangled with result and history
5) without U^-1: no amplification
PASS
```

## Shor's algorithm with modexp compiled from C

`-m tests.test_shor` exit code 0, 63 s

```
9) N = 21, a = 5: order found, base gives no factor
    modexp: 18 instructions; a = 2, N = 33; exponent register: t = 11 qubits (x = 0..2047)
    CPU check: a^x mod N correct for all 2048 exponents, 4..137 machine cycles, all inside the 12-bit model (10.1 s)
    machine: W = 12, 12 instruction classes, 32 program slots, 137 cycles: 9412 qubits, 4487024 gates (2065960 Toffoli) per run of U
    circuit: H on x, U, copy, U^-1, inverse QFT: 9418 qubits, 8974146 gates
    after U: X0 = a^x mod N in all 2048 branches, every branch halted, no trap
    after U^-1: exponent register restored: True; all 9401 work and history qubits back in their initial state: True
    measurement of x, exact probabilities (3.0 s; textbook value in brackets):
    largest difference from the textbook distribution: 3.7e-16
    1000 shots (seed 2026): 681 gave the order r = 10, 0 gave the factors = 0.000 [95% CI 0.000..0.004]
    exact probability per shot: order 0.6792, factors 0.0000; a uniformly random y would give the factors with probability 0.0000
    order r = 10 found correctly, but 2^(r/2) = -1 mod 33: this base gives no factor (the classical part of Shor's algorithm then picks another base)
    trying the next base
    
    modexp: 18 instructions; a = 4, N = 33; exponent register: t = 11 qubits (x = 0..2047)
    CPU check: a^x mod N correct for all 2048 exponents, 4..137 machine cycles, all inside the 12-bit model (9.6 s)
    machine: W = 12, 12 instruction classes, 32 program slots, 137 cycles: 9412 qubits, 4487024 gates (2065960 Toffoli) per run of U
    circuit: H on x, U, copy, U^-1, inverse QFT: 9418 qubits, 8974146 gates
    after U: X0 = a^x mod N in all 2048 branches, every branch halted, no trap
    after U^-1: exponent register restored: True; all 9401 work and history qubits back in their initial state: True
    measurement of x, exact probabilities (2.9 s; textbook value in brackets):
    largest difference from the textbook distribution: 7.2e-16
    1000 shots (seed 2026): 592 gave the order r = 5, 0 gave the factors = 0.000 [95% CI 0.000..0.004]
    exact probability per shot: order 0.5792, factors 0.0000; a uniformly random y would give the factors with probability 0.0000
    order r = 5 found correctly, but r is odd: this base gives no factor (the classical part of Shor's algorithm then picks another base)
    trying the next base
    
    modexp: 18 instructions; a = 5, N = 33; exponent register: t = 11 qubits (x = 0..2047)
    CPU check: a^x mod N correct for all 2048 exponents, 4..137 machine cycles, all inside the 12-bit model (9.6 s)
    machine: W = 12, 12 instruction classes, 32 program slots, 137 cycles: 9412 qubits, 4487024 gates (2065960 Toffoli) per run of U
    circuit: H on x, U, copy, U^-1, inverse QFT: 9418 qubits, 8974146 gates
    after U: X0 = a^x mod N in all 2048 branches, every branch halted, no trap
    after U^-1: exponent register restored: True; all 9401 work and history qubits back in their initial state: True
    measurement of x, exact probabilities (3.0 s; textbook value in brackets):
    largest difference from the textbook distribution: 3.7e-16
    1000 shots (seed 2026): 681 gave the order r = 10, 681 gave the factors = 0.681 [95% CI 0.651..0.709]
    exact probability per shot: order 0.6792, factors 0.6792; a uniformly random y would give the factors with probability 0.0181
    RESULT: 33 = 3 x 11   (order of 5 modulo 33: r = 10)
10) N = 33, no base given: bases 2 and 4 give no factor, base 5 gives 3 x 11
PASS
```

## Interpreter vs specialised circuit

`tools/compare_specialized.py` exit code 0, 6 s

```
f(a, b) = (a + b) * (a ^ b) mod 2^8, W = 8, 4 instructions, 5 machine cycles
interpreter, full decoder (22 classes), with cleanup         2020    220758     95220
interpreter, full decoder (22 classes), no cleanup           2012    110375     47610
interpreter, reduced decoder (5 classes), with cleanup       1055     61798     36180
interpreter, reduced decoder (5 classes), no cleanup         1047     30895     18090
specialised circuit, with cleanup                             290       722       340
ratio interpreter, full decoder (22 classes), with cleanup / specialised: 306x gates, 7.0x qubits
ratio interpreter, reduced decoder (5 classes), with cleanup / specialised: 86x gates, 3.6x qubits
```

## C programs, clang

`-m tests.test_c_programs clang` exit code 0, 226 s

```
54 passed (2 of them are the expected, flagged model-limit cases), 0 failed
```

## C programs, gcc

`-m tests.test_c_programs gcc` exit code 0, 209 s

```
54 passed (3 of them are the expected, flagged model-limit cases), 0 failed
```

