"""Exact simulator for the interpreter circuit on computational-basis inputs.

The circuit uses only X / CX / CCX / CSWAP, i.e. it is a permutation of basis states, so a
basis input maps to exactly one basis output; tracking bits is an exact simulation of the
quantum circuit for such inputs (superposed inputs need Aer or hardware)."""


def simulate(gates, n, ones=()):
    s = bytearray(n)
    for q in ones:
        s[q] ^= 1
    for g in gates:
        op = g[0]
        if op == "ccx":
            if s[g[1]] and s[g[2]]:
                s[g[3]] ^= 1
        elif op == "cx":
            if s[g[1]]:
                s[g[2]] ^= 1
        elif op == "x":
            s[g[1]] ^= 1
        elif op == "cswap":
            if s[g[1]]:
                s[g[2]], s[g[3]] = s[g[3]], s[g[2]]
        else:
            raise ValueError(op)
    return s


def value(state, qubits):
    return sum(state[q] << i for i, q in enumerate(qubits))
