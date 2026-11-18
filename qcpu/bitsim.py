"""Fast exact simulator for reversible circuits on computational-basis states.
The interpreter uses only X/CX/CCX/MCX/CSWAP, i.e. a permutation of basis states,
so a basis input maps to a single basis output and can be tracked bit by bit."""


def simulate_basis(qc, bits=None):
    idx = {q: i for i, q in enumerate(qc.qubits)}
    s = [0] * qc.num_qubits if bits is None else list(bits)
    for inst in qc.data:
        name, qs = inst.operation.name, [idx[q] for q in inst.qubits]
        if name == "x":
            s[qs[0]] ^= 1
        elif name in ("cx", "ccx", "mcx"):
            if all(s[q] for q in qs[:-1]):
                s[qs[-1]] ^= 1
        elif name == "cswap":
            if s[qs[0]]:
                s[qs[1]], s[qs[2]] = s[qs[2]], s[qs[1]]
        elif name == "barrier":
            pass
        else:
            raise ValueError(f"non-permutation gate {name}")
    return s


def read_reg(qc, bits, reg):
    idx = {q: i for i, q in enumerate(qc.qubits)}
    return sum(bits[idx[q]] << j for j, q in enumerate(reg))
