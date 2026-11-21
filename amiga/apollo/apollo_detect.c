/* Which machine this is. Shared by amigentd.apollo and the setup probe.
 * 68000-clean: the probe runs before the Apollo binary is chosen. */
#include <exec/types.h>
#include <exec/execbase.h>
#include <proto/exec.h>

/* exec's AttnFlags bit for the 68080, AFB_68080 10 in ApolloOS's cpu_m68k.h */
#ifndef AFF_68080
#define AFF_68080 (1L << 10)
#endif

#define VREG_BOARD 0xDFF3FC

extern struct ExecBase *SysBase;

/* The SAGA board id. Only for a report, and only once apollo_os_here() said
 * yes: on AmigaOS 4 or AROS elsewhere this address holds garbage or traps. */
UWORD apollo_board(void)
{
    return *(volatile UWORD *)VREG_BOARD;
}

const char *apollo_board_name(UWORD board)
{
    /* High byte is the model, from the ApolloOS SAGA header. Ids past this
     * list (an A6000, for one) are reported by the raw value, not guessed. */
    static const char *const names[] = {
        "unknown", "V2-V600", "V2-V500", "V4-V500", "V4-V1200",
        "V4-SA", "V2-V1200", "V4-V600", "V4-UNI", "future"
    };
    UBYTE model = board >> 8;

    if (model < sizeof(names) / sizeof(names[0]))
        return names[model];
    return "unlisted";
}

BOOL apollo_os_here(void)
{
    /* ApolloOS is exec 51 or later with the 68080 attention bit. AmigaOS on a
     * Vampire stays below 51, and nothing here touches the hardware. */
    return SysBase->LibNode.lib_Version >= 51 && (SysBase->AttnFlags & AFF_68080) != 0;
}
