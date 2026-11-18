    .text
    .global _start
_start:
    movz x0, #5
    add  x1, x0, #3
    eor  x2, x0, x1
