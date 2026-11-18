/* Types for compiling the daemon's input path on the host.
 * No Amiga library is linked, and ColdReboot only counts.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef uint32_t ULONG;
typedef int32_t LONG;
typedef uint16_t UWORD;
typedef int16_t WORD;
typedef uint8_t UBYTE;
typedef int BOOL;

struct Library {
    struct {
        unsigned short lib_Version;
    } LibNode;
};

struct InputEvent {
    unsigned char ie_Class;
    unsigned short ie_Code;
    unsigned short ie_Qualifier;
    struct {
        struct {
            unsigned char ie_prev1DownCode;
            unsigned char ie_prev1DownQual;
            unsigned char ie_prev2DownCode;
            unsigned char ie_prev2DownQual;
        } ie_dead;
    } ie_position;
};

#define IECLASS_RAWKEY 0x01
#define IECODE_UP_PREFIX 0x80

static struct Library sysbase;
static struct Library *SysBase = &sysbase;
static ULONG clock_ms;
static int reboots;
static int events;
static UBYTE prev_code[2], prev_qual[2];
static ULONG input_ms;

static ULONG now_ms(void)
{
    return clock_ms;
}

/* Counts. This is not the Amiga reset, and nothing here calls one. */
static void ColdReboot(void)
{
    reboots++;
}

static void write_event(struct InputEvent *ev)
{
    (void)ev;
    events++;
}

static void move_to(WORD x, WORD y)
{
    (void)x;
    (void)y;
}

static void move_by(WORD x, WORD y)
{
    (void)x;
    (void)y;
}

static void set_buttons(UWORD mask)
{
    (void)mask;
}

static void mon_say(UBYTE kind, const char *what, const char *arg)
{
    (void)kind;
    (void)what;
    (void)arg;
}

static void mon_xy(char *out, LONG x, LONG y)
{
    (void)x;
    (void)y;
    if (out)
        out[0] = 0;
}

static BOOL type_char(UWORD ch, UWORD extra)
{
    (void)ch;
    (void)extra;
    return 0;
}
