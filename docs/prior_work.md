# Prior work and where this project sits

| work | real ISA | coherent PC / fetch / decode | code |
|---|---|---|---|
| Mariantoni et al., Science 2011 ([arXiv:1109.3743](https://arxiv.org/abs/1109.3743)) | no | no: instructions stored on a classical computer | n/a (hardware experiment) |
| D.-S. Wang, quantum von Neumann architecture (2022-2024), survey [Entropy 2023](https://doi.org/10.3390/e25081187) | no | theory | no |
| Qx86, Fitzjohn et al., [IEEE TQE 2022](https://tqe.ieee.org/2022/11/02/a-software-development-kit-and-translation-layer-for-executing-intel-8080-assembler-on-a-quantum-computer-august-2022/), [QIP 2024](https://link.springer.com/article/10.1007/s11128-024-04524-5) | Intel 8080/Z80 | no: PC classical, one IBM job per instruction | [GitHub fork](https://github.com/PaladinBIGDan2077/Qx86_2026_11) |
| Quantum Control Machine, Yuan, Villanyi, Carbin, OOPSLA 2024 ([arXiv:2304.15000](https://arxiv.org/abs/2304.15000)) | no (own ISA) | yes | research simulator (artifact) |
| Quantum Register Machine, Zhang, Ying, PLDI 2025 ([arXiv:2408.10054](https://arxiv.org/abs/2408.10054)) | no (own ISA) | yes | none published |
| **arm-qpu (this repo)** | **AArch64, unmodified binaries** | **yes** | this repository |

## Lessons from QCM and QRM that shape the design

* **No-Embedding theorem (QCM).** A non-injective transition function, such as a classical
  conditional jump, has no quantum embedding. This machine therefore uses a Landauer
  embedding: per-step history of PC and overwritten values. That is correct for basis-state
  inputs (the "same binary, same result" goal), but the history is entangled with the data,
  so programs with *superposed* inputs need a Bennett wrapper (compute, copy the output,
  uncompute). This is the planned "oracle mode".
* **Synchronisation (QCM, QRM).** All branches of a superposition must end in the same
  control state. The machine runs a fixed number of cycles, and after HLT every cycle is a
  no-op (padding).
* **Hybrid control (QRM).** Classical control never holds superposed data. QA64 (below)
  keeps the PC classical where control depends only on classical data, and coherent only
  inside quantum-control regions.

## QA64 roadmap (AArch64 + quantum extension)

1. Data in superposition: `QH Xd, #bit`, `QPHASE`, `QROT`.
2. Two kinds of control: ordinary B.cond/CBZ on classical data only; `QIF`/`QFI` for
   branching on quantum data (QCM branch register + QRM synchronisation).
3. `UNCALL` / oracle mode: run f, copy f(x), run f backwards. Any C function becomes a
   clean oracle |x>|0> -> |x>|f(x)>.
4. QRAM: LDR with a superposed address already is a QRAM read.
5. `QMEAS Xd`: measurement as an instruction; afterwards ordinary branches apply again.
6. Tiered PC: classical fetch/decode outside QIF regions. This is the road to hardware.
