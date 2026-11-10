/* A test program for tracepoints: calls tick() once a second for 30 seconds
 * and says where tick() is. Build: build-amigentd SOURCE trace-test.c TO trace-test */
#include <proto/exec.h>
#include <proto/dos.h>
#include <stdio.h>

LONG ticks;

LONG tick(LONG n)
{
    ticks += n;
    return ticks;
}

int main(void)
{
    LONG i;

    printf("tick at %p\n", (void *)tick);
    fflush(stdout);
    for (i = 1; i <= 30; i++) {
        tick(i);
        Delay(50);
    }
    printf("ticks %ld\n", ticks);
    return 0;
}
