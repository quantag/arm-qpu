"""Generate a C program that executes the exact instruction words of a .bin on a real AArch64 CPU
(Apple Silicon Mac, Raspberry Pi, AWS Graviton...) and prints X0..X3.
Usage: python3 tools/make_harness.py arm/prog1.bin > harness.c && cc harness.c -o h && ./h"""
import sys
code = open(sys.argv[1], "rb").read()
words = [int.from_bytes(code[i:i + 4], "little") for i in range(0, len(code), 4)]
inst = "\n".join(f'        ".inst 0x{w:08x}\\n"' for w in words)
print(f"""#include <stdio.h>
#include <stdint.h>
int main(void) {{
    uint64_t r0, r1, r2, r3;
    __asm__ volatile(
        "mov x0, xzr\\n mov x1, xzr\\n mov x2, xzr\\n mov x3, xzr\\n"
{inst}
        "mov %0, x0\\n mov %1, x1\\n mov %2, x2\\n mov %3, x3\\n"
        : "=r"(r0), "=r"(r1), "=r"(r2), "=r"(r3) :: "x0", "x1", "x2", "x3");
    printf("X0 = %llu\\nX1 = %llu\\nX2 = %llu\\nX3 = %llu\\n",
           (unsigned long long)r0, (unsigned long long)r1, (unsigned long long)r2, (unsigned long long)r3);
    return 0;
}}""")
