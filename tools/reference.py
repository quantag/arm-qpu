"""Conventional reference: run raw A64 bytes on an AArch64 CPU emulator (Unicorn = QEMU CPU core)."""
import sys
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3

BASE = 0x10000
REGS = [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3]


def run_reference(code: bytes, nregs: int = 4):
    mu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    mu.mem_map(BASE, 0x1000)
    mu.mem_write(BASE, code)
    for r in REGS:
        mu.reg_write(r, 0)  # same initial state as the quantum machine
    mu.emu_start(BASE, BASE + len(code))
    return [mu.reg_read(r) for r in REGS[:nregs]]


if __name__ == "__main__":
    code = open(sys.argv[1], "rb").read()
    for i, v in enumerate(run_reference(code)):
        print(f"X{i} = {v}")
