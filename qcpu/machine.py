"""
Quantum stored-program interpreter for a subset of AArch64 (A64).

The interpreter is ONE fixed quantum circuit. A program is not compiled into it:
the raw 32-bit A64 instruction words are loaded as the initial computational-basis
state of the program-memory qubits (see `load_program`). Every step the circuit
  1. fetches MEM[PC] into the instruction register IR, coherently controlled by PC,
  2. decodes IR into one-hot flags (MOVZ / ADD-imm / EOR-reg),
  3. selects operands from the register file by the Rn / Rm fields,
  4. computes the result with a reversible ALU,
  5. writes it to X[Rd] by controlled-SWAP (the old value of X[Rd] goes into a
     per-step history register -> exact overwrite semantics, fully reversible),
  6. uncomputes decode/IR (all scratch qubits return to |0>), and increments PC.
No measurement and no classical control happens inside the interpreter.

Registers are W bits wide. For MOVZ (hw=0), ADD (imm, sh=0) and EOR (shift 0)
the low W bits of the 64-bit ARM result depend only on the low W bits of the
operands, so the machine computes *exactly* bits [W-1:0] of the AArch64 result.

Supported encodings (64-bit forms, registers X0..X{NREG-1}):
  MOVZ Xd, #imm16            1 10 100101 00 imm16 Rd          0xD2800000
  ADD  Xd, Xn, #imm12        1 0 0 100010 0 imm12 Rn Rd       0x91000000
  EOR  Xd, Xn, Xm            1 10 01010 00 0 Rm 000000 Rn Rd  0xCA000000
"""
from dataclasses import dataclass, field
from qiskit import QuantumCircuit, QuantumRegister

# (name, value, mask) for the *full* decoder: every fixed bit is checked,
# plus "register number < NREG" (upper register-field bits must be 0).
ENCODINGS = {
    "movz": (0xD2800000, 0xFFE00000),
    "add":  (0x91000000, 0xFFC00000),
    "eor":  (0xCA000000, 0xFFE0FC00),
}
# Minimal decoder: bits 30 and 28 alone distinguish the three supported encodings
# (D2=1101_0010, 91=1001_0001, CA=1100_1010). Valid only if the classical loader
# has already checked that every word is one of the supported encodings.
MIN_DECODE = {"movz": {30: 1, 28: 1}, "add": {30: 0, 28: 1}, "eor": {30: 1, 28: 0}}

RD, RN, RM = 0, 5, 16          # register field positions
IMM16, IMM12 = 5, 10           # immediate field positions


@dataclass
class Config:
    W: int = 4                  # register width
    NREG: int = 4               # X0..X{NREG-1}; must be a power of two
    STEPS: int = 3              # instructions executed
    SLOTS: int = 4              # program-memory words (power of two)
    decoder: str = "full"       # "full" or "min"
    ops: tuple = ("movz", "add", "eor")
    mem_bits: list = field(default=None)  # stored IR bit positions (None = all 32)

    def __post_init__(self):
        self.rbits = (self.NREG - 1).bit_length()
        self.pbits = max(1, (self.SLOTS - 1).bit_length())
        if self.mem_bits is None:
            if self.decoder == "full":
                self.mem_bits = list(range(32))
            else:
                self.mem_bits = sorted(self.needed_bits())

    def needed_bits(self):
        b = set(range(RD, RD + self.rbits))
        if "add" in self.ops or "eor" in self.ops:
            b |= set(range(RN, RN + self.rbits))
        if "eor" in self.ops:
            b |= set(range(RM, RM + self.rbits))
        if "movz" in self.ops:
            b |= set(range(IMM16, IMM16 + self.W))
        if "add" in self.ops:
            b |= set(range(IMM12, IMM12 + self.W))
        for op in self.ops:
            b |= set(MIN_DECODE[op])
        return b


class QuantumARM:
    def __init__(self, cfg: Config):
        self.cfg = c = cfg
        self.mem = [QuantumRegister(len(c.mem_bits), f"mem{s}") for s in range(c.SLOTS)]
        self.pc = QuantumRegister(c.pbits, "pc")
        self.ir = QuantumRegister(len(c.mem_bits), "ir")
        self.X = [QuantumRegister(c.W, f"x{k}") for k in range(c.NREG)]
        self.flag = {op: QuantumRegister(1, f"f_{op}") for op in c.ops}
        self.A = QuantumRegister(c.W, "a")
        self.B = QuantumRegister(c.W, "b")
        self.C = QuantumRegister(max(1, c.W - 1), "carry")
        self.anc = QuantumRegister(3, "anc")   # f_any / slot-select / reg-select scratch
        self.hist = [QuantumRegister(c.W, f"t{s}") for s in range(c.STEPS)]
        regs = [*self.mem, self.pc, self.ir, *self.X, *self.flag.values(),
                self.A, self.B, self.C, self.anc, *self.hist]
        self.qc = QuantumCircuit(*regs, name="arm_qpu")
        self.bitpos = {b: i for i, b in enumerate(c.mem_bits)}
        self.scratch = [self.ir, *self.flag.values(), self.A, self.B, self.C, self.anc]
        for s in range(c.STEPS):
            self._step(s)

    # --- helpers -----------------------------------------------------------
    def irb(self, bit):
        return self.ir[self.bitpos[bit]]

    def _match(self, ctrls_vals, target):
        """target ^= AND_i (ctrl_i == val_i), using X-conjugation for zeros."""
        qc = self.qc
        zeros = [q for q, v in ctrls_vals if v == 0]
        for q in zeros: qc.x(q)
        qc.mcx([q for q, _ in ctrls_vals], target)
        for q in zeros: qc.x(q)

    def _field_eq(self, pos, k, extra=()):
        return [(self.irb(pos + j), (k >> j) & 1) for j in range(self.cfg.rbits)] + list(extra)

    # --- pipeline stages -------------------------------------------------
    def _fetch(self):
        c, qc, sel = self.cfg, self.qc, self.anc[1]
        for s in range(c.SLOTS):
            self._match([(self.pc[j], (s >> j) & 1) for j in range(c.pbits)], sel)
            for i in range(len(c.mem_bits)):
                qc.ccx(sel, self.mem[s][i], self.ir[i])
            self._match([(self.pc[j], (s >> j) & 1) for j in range(c.pbits)], sel)

    def _decode(self):
        c = self.cfg
        for op in c.ops:
            if c.decoder == "full":
                val, mask = ENCODINGS[op]
                fixed = [b for b in range(32) if (mask >> b) & 1]
                # register numbers must be < NREG
                for base in ([RD, RN] + ([RM] if op == "eor" else []) if op != "movz" else [RD]):
                    fixed += list(range(base + c.rbits, base + 5))
                cv = [(self.irb(b), (val >> b) & 1) for b in sorted(set(fixed))]
            else:
                cv = [(self.irb(b), v) for b, v in MIN_DECODE[op].items()]
            self._match(cv, self.flag[op][0])

    def _select_into(self, pos, flag_q, dst):
        """dst ^= X[field@pos] if flag."""
        qc, sel = self.qc, self.anc[2]
        for k in range(self.cfg.NREG):
            self._match(self._field_eq(pos, k, [(flag_q, 1)]), sel)
            for i in range(self.cfg.W):
                qc.ccx(sel, self.X[k][i], dst[i])
            self._match(self._field_eq(pos, k, [(flag_q, 1)]), sel)

    def _operands(self):
        c, qc, f = self.cfg, self.qc, self.flag
        for op in ("add", "eor"):
            if op in f:
                self._select_into(RN, f[op][0], self.A)
        if "movz" in f:
            for i in range(c.W):
                qc.ccx(f["movz"][0], self.irb(IMM16 + i), self.B[i])
        if "add" in f:
            for i in range(c.W):
                qc.ccx(f["add"][0], self.irb(IMM12 + i), self.B[i])
        if "eor" in f:
            self._select_into(RM, f["eor"][0], self.B)

    def _carries(self):
        qc, A, B, C, W = self.qc, self.A, self.B, self.C, self.cfg.W
        if W < 2: return
        qc.ccx(A[0], B[0], C[0])                       # c1 = a0 & b0
        for i in range(1, W - 1):                      # c_{i+1} = maj(a_i, b_i, c_i)
            qc.ccx(A[i], B[i], C[i]); qc.ccx(A[i], C[i - 1], C[i]); qc.ccx(B[i], C[i - 1], C[i])

    def _step(self, s):
        c, qc, T = self.cfg, self.qc, self.hist[s]
        self._fetch()
        self._decode()
        self._operands()
        # ALU: T = A ^ B, and for ADD add the carry vector: (A+B) = (A^B) ^ (carries<<1)
        for i in range(c.W):
            qc.cx(self.A[i], T[i]); qc.cx(self.B[i], T[i])
        if "add" in self.flag:
            self._carries()
            for i in range(1, c.W):
                qc.ccx(self.flag["add"][0], self.C[i - 1], T[i])
            self._carries_inverse()
        self._operands_inverse()
        # write-back: swap T <-> X[Rd]; T now holds the old X[Rd] (history)
        fany = self.anc[0]
        for op in c.ops: qc.cx(self.flag[op][0], fany)
        sel = self.anc[2]
        for k in range(c.NREG):
            self._match(self._field_eq(RD, k, [(fany, 1)]), sel)
            for i in range(c.W):
                qc.cswap(sel, self.X[k][i], T[i])
            self._match(self._field_eq(RD, k, [(fany, 1)]), sel)
        for op in c.ops: qc.cx(self.flag[op][0], fany)
        self._decode()          # uncompute flags (self-inverse)
        self._fetch()           # un-fetch IR (self-inverse)
        # PC += 1 (reversible incrementer)
        for j in reversed(range(c.pbits)):
            if j == 0: qc.x(self.pc[0])
            else: qc.mcx(list(self.pc[:j]), self.pc[j])

    def _carries_inverse(self):
        qc, A, B, C, W = self.qc, self.A, self.B, self.C, self.cfg.W
        if W < 2: return
        for i in reversed(range(1, W - 1)):
            qc.ccx(B[i], C[i - 1], C[i]); qc.ccx(A[i], C[i - 1], C[i]); qc.ccx(A[i], B[i], C[i])
        qc.ccx(A[0], B[0], C[0])

    def _operands_inverse(self):
        self._operands()        # every operand gate is a self-inverse XOR-into; order commutes

    # --- program loading (state preparation, not part of the interpreter) ---
    def load_program(self, words):
        c = self.cfg
        assert len(words) <= c.SLOTS
        prep = QuantumCircuit(*self.qc.qregs, name="load")
        for s, w in enumerate(words):
            for i, b in enumerate(c.mem_bits):
                if (w >> b) & 1:
                    prep.x(self.mem[s][i])
        return prep


def words_from_bytes(code: bytes):
    assert len(code) % 4 == 0
    return [int.from_bytes(code[i:i + 4], "little") for i in range(0, len(code), 4)]


def validate(words, cfg: Config):
    """Classical loader check: each word must be a supported encoding with registers < NREG."""
    for w in words:
        ok = False
        for op in cfg.ops:
            val, mask = ENCODINGS[op]
            if (w & mask) == val:
                fields = [RD] + ([RN] if op != "movz" else []) + ([RM] if op == "eor" else [])
                ok = all(((w >> f) & 0x1F) < cfg.NREG for f in fields)
        if not ok:
            raise ValueError(f"unsupported instruction word 0x{w:08x}")
