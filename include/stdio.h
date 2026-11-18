/* Minimal stdio.h for programs that run on the arm-qpu quantum machine.
 * printf / puts / putchar are bound by arm_qpu.py to a small output stub that runs on the
 * QPU and records each call in an output log in data memory; the text is formatted on the
 * host after the run (for the QPU and the CPU reference alike). Up to 6 int/pointer
 * arguments per printf call. No floating point. */
#ifndef ARM_QPU_STDIO_H
#define ARM_QPU_STDIO_H
int printf(const char *format, ...);
int puts(const char *s);
int putchar(int c);
#endif
