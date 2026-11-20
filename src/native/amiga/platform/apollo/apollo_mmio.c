/* Windows PEEK and POKE must not touch. Each pair is [start, end).
 * A request that shares any byte is refused, including one that starts
 * outside a window and finishes inside it.
 *
 * The addresses are the ones this tree already names, not a guessed map:
 * - apollo.c: BPLHMOD $DFF1E6 (word), BPLHPT $DFF1EC (32-bit), GFXMODE
 *   $DFF1F4 (word), TEXDPT $DFF254 (32-bit), PIP $DFF3D0 through PipDMARowLen
 *   $DFF3E2 (word, so the window ends at $DFF3E4), and ARNE at AUD7L $DFF470
 *   across the $DFF4xx channel page. A read of a write-only custom register
 *   writes the idle data bus. GFXMODE 0 switches chunky DMA off. A PIP
 *   register read clears the overlay.
 * - PIP 2 is the same block $20 lower, $DFF3B0 through $DFF3C2 (sagadoc).
 * - ARNE channel n is $DFF400 + n * $10 for n = 0..15, so $DFF400–$DFF500.
 * - apollo_detect.c names VREG_BOARD $DFF3FC. The system window around it is
 *   $DFF3EA–$DFF3FC (CORE REVISION through VAMPIRE VERSION). $DFF3EC is
 *   write-only.
 */
#include <exec/types.h>

BOOL apollo_mmio_hit(ULONG at, ULONG n)
{
    static const ULONG win[][2] = {
        {0x00DFF1E6UL, 0x00DFF1E8UL},
        {0x00DFF1ECUL, 0x00DFF1F0UL},
        {0x00DFF1F4UL, 0x00DFF1F6UL},
        {0x00DFF254UL, 0x00DFF258UL},
        {0x00DFF3B0UL, 0x00DFF3C4UL},
        {0x00DFF3D0UL, 0x00DFF3E4UL},
        {0x00DFF3EAUL, 0x00DFF3FEUL},
        {0x00DFF400UL, 0x00DFF500UL},
    };
    ULONG end, i;

    if (!n || at + n < at)
        return TRUE;
    end = at + n;
    for (i = 0; i < sizeof(win) / sizeof(win[0]); i++)
        if (at < win[i][1] && end > win[i][0])
            return TRUE;
    return FALSE;
}
