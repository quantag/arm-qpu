# Test results

Generated 2026-11-18 19:08 CET by `tools/test_report.py`.

**Overall: all tests passed.**

- code: commit `5505a53878be4215200d47bb949b13575c816bf7`
- Python 3.13.18 on Linux-6.18.44-fc-v595-x86_64-with-glibc2.39
- qiskit 2.6.2, qiskit-aer 0.18.4, unicorn 2.1.4, lief 1.0.0, capstone 5.0.9
- Ubuntu clang version 18.1.3 (1ubuntu1)
- aarch64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0

Outcome classes: **match** (QPU = CPU after every cycle, model check clean); **match-flagged** (equal, but the model check reported values outside the W-bit model); **flagged** (different, and the model check reported it); **UNFLAGGED** (different, model check silent: a bug; required to be 0); **discarded** (the CPU run did not halt normally, the program did not assemble, or it is too long).

## Differential fuzzing

`-m tests.test_fuzz 300 7 8,12,16` exit code 0, 91 s

```
W=8 seed=15: {"generated": 300, "rejected by assembler": 36, "too long": 0, "discarded (CPU did not halt)": 0, "match": 91, "match-flagged": 127, "flagged": 46, "UNFLAGGED": 0}
W=12 seed=19: {"generated": 300, "rejected by assembler": 37, "too long": 0, "discarded (CPU did not halt)": 0, "match": 150, "match-flagged": 77, "flagged": 36, "UNFLAGGED": 0}
W=16 seed=23: {"generated": 300, "rejected by assembler": 35, "too long": 0, "discarded (CPU did not halt)": 0, "match": 162, "match-flagged": 71, "flagged": 32, "UNFLAGGED": 0}
```

## Boundary cases

`-m tests.test_edges 8,12,16` exit code 0, 473 s

```
W=8: {"extend": {"match-flagged": 162, "flagged": 122, "match": 184}, "flags": {"flagged": 154, "match-flagged": 18, "match": 88}, "shift": {"match-flagged": 238, "flagged": 78, "match": 87}, "w/x": {"flagged": 3, "match": 5, "match-flagged": 5}, "memory": {"flagged": 14, "match-flagged": 4, "match": 8}, "mul/div": {"match-flagged": 71, "flagged": 13, "match": 46}, "bitfield": {"match-flagged": 7, "match": 6}, "pointer": {"flagged": 13, "match": 26, "match-flagged": 5}, "constants": {"flagged": 19, "match-flagged": 2, "match": 14}}
W=12: {"extend": {"match-flagged": 120, "match": 401, "flagged": 91}, "flags": {"flagged": 160, "match-flagged": 8, "match": 172}, "shift": {"match-flagged": 262, "flagged": 36, "match": 229}, "w/x": {"flagged": 5, "match": 10, "match-flagged": 2}, "memory": {"flagged": 17, "match-flagged": 4, "match": 13}, "mul/div": {"match-flagged": 74, "flagged": 7, "match": 89}, "bitfield": {"match-flagged": 6, "match": 11}, "pointer": {"flagged": 13, "match": 26, "match-flagged": 5}, "constants": {"flagged": 19, "match-flagged": 2, "match": 14}}
W=16: {"extend": {"match-flagged": 93, "match": 454, "flagged": 65}, "flags": {"flagged": 160, "match-flagged": 8, "match": 172}, "shift": {"match-flagged": 236, "flagged": 34, "match": 240}, "w/x": {"flagged": 5, "match": 10, "match-flagged": 2}, "memory": {"flagged": 17, "match-flagged": 4, "match": 13}, "mul/div": {"match-flagged": 74, "flagged": 7, "match": 89}, "bitfield": {"match-flagged": 6, "match": 11}, "pointer": {"flagged": 13, "match": 26, "match-flagged": 5}, "constants": {"flagged": 19, "match-flagged": 2, "match": 14}}
no unflagged mismatch
```

## Fast simulator vs full circuit vs Aer

`-m tests.test_simulators 100 5` exit code 0, 53 s

```
full circuit vs fast replay: 100/100 identical (seed 5); full: 5691 qubits 644920 gates, fast reports 5691 qubits 644920 gates
Aer vs fast, program starting 'movz w0, #5': 1101 qubits, fast [8, 0, 253], Aer [8, 0, 253], equal
Aer vs fast, program starting 'mov w1, #3': 1101 qubits, fast [7, 0, 3], Aer [7, 0, 3], equal
Aer vs fast, program starting 'cmp w0, #4': 1101 qubits, fast [7, 7, 0], Aer [7, 7, 0], equal
PASS
```

## Coherence: superposition of two programs

`-m tests.test_coherence` exit code 0, 6 s

```
machine: 418 qubits, 7448 gates (4880 Toffoli)
1) superposed program -> X0: {7: 993, 8: 1007}
2) interference without phase: {'1': 2000}  with phase on X0[0]: {'0': 2000}
PASS: the machine executes a superposition of two ARM programs coherently
```

## Quantum branching

`-m tests.test_branching` exit code 0, 61 s

```
machine: 868 qubits, 42198 gates (27612 Toffoli), 13 cycles
A) (x, X2, running after cycle 3): {(0, 0, 0): 974, (1, 6, 1): 1026}
B) after uncompute, without phase: {'0': 2000}  with phase on X2[1]: {'1': 2000}
C) without uncompute: {'1': 967, '0': 1033}
PASS: superposed input, two paths of different length, coherent after uncompute
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

`-m tests.test_c_programs clang` exit code 0, 187 s

```
54 passed (2 of them are the expected, flagged model-limit cases), 0 failed
```

## C programs, gcc

`-m tests.test_c_programs gcc` exit code 0, 177 s

```
54 passed (3 of them are the expected, flagged model-limit cases), 0 failed
```

