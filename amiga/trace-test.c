/* A test program for tracepoints: calls tick() for a while and says where tick() is.
 * Needs no NDK: vc +aos68k -cpu=68000 -O1 -o trace-test trace-test.c */
#include <stdio.h>


long ticks;

long tick(long n)
{
    ticks += n;
    return ticks;
}

int main(void)
{
    long i;
    volatile long k;

    printf("tick at %p\n", (void *)tick);
    fflush(stdout);
    for (i = 1; i <= 60; i++) {
        tick(i);
        for (k = 0; k < 100000; k++)  /* a while on a 68000; no clock() needed */
            ;
    }
    printf("ticks %ld\n", ticks);
    return 0;
}
