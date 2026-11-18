    .text
    .global _start
_start:
    movz x2, #9
    eor  x1, x2, x2
    add  x2, x2, #4
