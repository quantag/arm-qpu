"""Exact sparse state-vector simulator for circuits made of X, CX, CCX, CSWAP (permutations of basis
states) plus a few H, Z gates.

The quantum ARM machine is a permutation circuit: it maps each basis state to one basis state. A
superposition over k input qubits therefore stays a superposition of at most 2^k basis states however
many qubits the machine has, and H/Z gates on a few qubits keep it small. The simulator stores exactly
those basis states and their complex amplitudes, so it computes the full quantum state -- including
interference between branches -- without approximation. Qiskit Aer's matrix-product-state method gives
the same results (tests/test_sparsesim.py) but is much slower when several input qubits are superposed.
"""
import numpy as np


class SparseState:
    def __init__(self, n, ones=()):
        self.n = n
        self.bits = np.zeros((1, n), dtype=np.uint8)      # one row per basis state with nonzero amplitude
        self.bits[0, list(ones)] = 1
        self.amp = np.ones(1, dtype=complex)

    # --- permutation gates: act on every stored basis state at once
    def x(self, t): self.bits[:, t] ^= 1
    def cx(self, c, t): self.bits[:, t] ^= self.bits[:, c]
    def ccx(self, a, b, t): self.bits[:, t] ^= self.bits[:, a] & self.bits[:, b]

    def cswap(self, c, a, b):
        m = self.bits[:, c] == 1
        ta = self.bits[m, a].copy()
        self.bits[m, a] = self.bits[m, b]
        self.bits[m, b] = ta

    def z(self, t):
        self.amp = np.where(self.bits[:, t] == 1, -self.amp, self.amp)

    def mcz(self, qubits):
        """Phase -1 on the basis states where all `qubits` are 1."""
        self.amp = np.where(np.all(self.bits[:, qubits] == 1, axis=1), -self.amp, self.amp)

    def h(self, t):
        b0 = self.bits.copy(); b0[:, t] = 0
        b1 = self.bits.copy(); b1[:, t] = 1
        s = 1 / np.sqrt(2)
        sign = np.where(self.bits[:, t] == 1, -1.0, 1.0)
        self._merge(np.vstack([b0, b1]), np.concatenate([self.amp * s, self.amp * s * sign]))

    def _merge(self, bits, amp):
        """Add the amplitudes of equal basis states (interference) and drop the ones that cancel."""
        packed = np.packbits(bits, axis=1)
        uniq, inv = np.unique(packed, axis=0, return_inverse=True)
        acc = np.zeros(len(uniq), dtype=complex)
        np.add.at(acc, inv.ravel(), amp)
        keep = np.abs(acc) > 1e-12
        self.bits = np.unpackbits(uniq[keep], axis=1, count=self.n).astype(np.uint8)
        self.amp = acc[keep]

    def apply(self, gates, inverse=False):
        """gates: list of (name, qubits...) as in QuantumARM.g. All of them are self-inverse."""
        for g in (reversed(gates) if inverse else gates):
            getattr(self, g[0])(*g[1:])

    def probabilities(self, qubits):
        """Exact distribution of the integer read from `qubits` (qubits[0] = bit 0)."""
        w = 1 << np.arange(len(qubits))
        vals = self.bits[:, qubits].astype(np.int64) @ w
        p = {}
        for v, a in zip(vals.tolist(), np.abs(self.amp) ** 2):
            p[v] = p.get(v, 0.0) + float(a)
        return p

    def sample(self, qubits, shots, seed=None):
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(self.amp), size=shots, p=np.abs(self.amp) ** 2 / np.sum(np.abs(self.amp) ** 2))
        w = 1 << np.arange(len(qubits))
        vals = self.bits[idx][:, qubits].astype(np.int64) @ w
        u, c = np.unique(vals, return_counts=True)
        return dict(zip(u.tolist(), c.tolist()))
