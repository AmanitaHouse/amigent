/* Types for compiling note_reset_chord on the host. No Amiga library is linked. */

#include <stdint.h>

typedef uint32_t ULONG;
typedef int32_t LONG;
typedef uint8_t UBYTE;
typedef int BOOL;

struct Library {
    struct {
        unsigned short lib_Version;
    } LibNode;
};

static struct Library sysbase;
static struct Library *SysBase = &sysbase;
static ULONG clock_ms;
static int reboots;

static ULONG now_ms(void)
{
    return clock_ms;
}

/* Counts. This is not the Amiga reset, and nothing here calls one. */
static void ColdReboot(void)
{
    reboots++;
}
