/*
 * amigent-levels: the output level of an AmiGUS card, left and right, as a
 * series. amiga_audio_levels copies it to T: and runs it.
 *
 *   amigent-levels [SECONDS <n>] [HZ <n>] [PEAK]
 *
 * It reads the mixer's SCOPE registers of the card's main (PCM) part, as the
 * AmiGUS Mixer does for its level bars (public register map): a write to the
 * level reset strobe $4A, then the signed left and right levels at $4C and $4E.
 * PEAK sets bit 0 of the SCOPE mode register $48 (maximum instead of average)
 * for the measurement and puts it back afterwards. Nothing else is written,
 * one strobe per sample, and no part of the card is reserved, so it runs next
 * to the AHI driver and other players. Ctrl-C stops it.
 *
 * The card comes from amigus.library if that is loaded already (it is not
 * loaded here), else from the Zorro II board list (manufacturer 2782, product 16).
 *
 * Output, one line each: CARD <name> <base>, MODE <text>, S <left> <right> per
 * sample, TICKS <50ths of a second taken>; or ERROR <text>.
 *
 * Build (vbcc, OS 2.04 and up):
 *   vc +aos68k -c99 -O2 -cpu=68000 -I<NDK>/Include_H -o amigent-levels src/native/amiga/tools/amigent-levels.c -lamiga
 *
 * MIT licence, see LICENSE.
 */

#include <exec/types.h>
#include <exec/execbase.h>
#include <dos/dos.h>
#include <libraries/configvars.h>
#include <libraries/expansionbase.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/expansion.h>

const char version[] = "$VER: amigent-levels 1.0 (21.11.2026)";

#define AMIGUS_MANUFACTURER 2782
#define AMIGUS_MAIN_PRODUCT 16
#define SCOPE_MODE  0x48
#define SCOPE_RESET 0x4a
#define SCOPE_LEFT  0x4c
#define SCOPE_RIGHT 0x4e

/* The public start of struct AmiGUS (amigus/amigus.h) */
struct AmiGUSCard {
    APTR pcm, wavetable, codec;
    ULONG fpga[2];
    ULONG hardware, firmware;
    STRPTR type_name;
    UWORD type_id;
};

/* amigus.library/AmiGUS_FindCard, the first function */
struct AmiGUSCard *FindCard(__reg("a6") struct Library *base, __reg("a0") struct AmiGUSCard *card)
    = "\tjsr\t-30(a6)";

struct ExpansionBase *ExpansionBase;

static void say(const char *fmt, LONG a, LONG b, LONG c)
{
    LONG args[3];

    args[0] = a;
    args[1] = b;
    args[2] = c;
    VPrintf((STRPTR)fmt, args);
}

static LONG ticks(const struct DateStamp *d)
{
    return (d->ds_Days * 1440 + d->ds_Minute) * 3000 + d->ds_Tick;
}

int main(void)
{
    LONG opts[3] = {0, 0, 0};
    struct RDArgs *rd = ReadArgs("SECONDS/N,HZ/N,PEAK/S", opts, NULL);
    LONG seconds = 2, hz = 10, n, i, every;
    BOOL peak = FALSE, loaded;
    struct Library *amigus = NULL;
    struct AmiGUSCard *card;
    volatile UWORD *base = NULL;
    const char *name = "AmiGUS";
    UWORD mode = 0, want;
    struct DateStamp t0, t1;

    if (!rd) {
        PutStr("ERROR\tusage: amigent-levels [SECONDS <n>] [HZ <n>] [PEAK]\n");
        return RETURN_ERROR;
    }
    if (opts[0])
        seconds = *(LONG *)opts[0];
    if (opts[1])
        hz = *(LONG *)opts[1];
    peak = opts[2] != 0;
    FreeArgs(rd);
    if (seconds < 1)
        seconds = 1;
    if (seconds > 60)
        seconds = 60;
    if (hz < 1)
        hz = 1;
    if (hz > 50)
        hz = 50;
    every = 50 / hz;
    n = seconds * hz;

    Forbid();
    loaded = FindName(&SysBase->LibList, "amigus.library") != NULL;
    Permit();
    if (loaded && (amigus = OpenLibrary("amigus.library", 1)) != NULL) {
        card = FindCard(amigus, NULL);
        if (card && card->pcm) {
            base = (volatile UWORD *)card->pcm;
            if (card->type_name)
                name = (const char *)card->type_name;
        }
    }
    if (!base && (ExpansionBase = (struct ExpansionBase *)OpenLibrary("expansion.library", 34)) != NULL) {
        struct ConfigDev *cd = FindConfigDev(NULL, AMIGUS_MANUFACTURER, AMIGUS_MAIN_PRODUCT);

        if (cd)
            base = (volatile UWORD *)cd->cd_BoardAddr;
        CloseLibrary((struct Library *)ExpansionBase);
    }
    if (!base) {
        if (amigus)
            CloseLibrary(amigus);
        PutStr(loaded ? "ERROR\tNo AmiGUS: amigus.library is loaded but found no card.\n"
                      : "ERROR\tNo AmiGUS found: no Zorro board from manufacturer 2782, and "
                        "amigus.library is not loaded (an AmiGUS mini shows only through it).\n");
        return RETURN_WARN;
    }
    say("CARD\t%s\t%08lx\n", (LONG)name, (LONG)base, 0);

    mode = base[SCOPE_MODE / 2];
    want = (mode & ~3) | (peak ? 1 : 0);  /* bit 1 clear: signed levels */
    if (want != mode)
        base[SCOPE_MODE / 2] = want;

    DateStamp(&t0);
    base[SCOPE_RESET / 2] = 0;  /* a fresh first interval */
    for (i = 0; i < n; i++) {
        if (SetSignal(0, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
            break;
        Delay(every);
        base[SCOPE_RESET / 2] = 0;
        say("S\t%ld\t%ld\n", (LONG)(WORD)base[SCOPE_LEFT / 2], (LONG)(WORD)base[SCOPE_RIGHT / 2], 0);
    }
    DateStamp(&t1);

    if (want != mode)
        base[SCOPE_MODE / 2] = (base[SCOPE_MODE / 2] & ~3) | (mode & 3);
    say("MODE\tSCOPE mode $%04lx, measured with $%04lx%s\n", mode, want,
        (LONG)(want != mode ? ", put back" : ""));
    say("TICKS\t%ld\n", ticks(&t1) - ticks(&t0), 0, 0);
    if (amigus)
        CloseLibrary(amigus);
    return i < n ? RETURN_WARN : RETURN_OK;
}
