/* cybergraphics.library for the Apollo gcc build. vbcc uses its own inlines.
 * Offsets match inline/cybergraphics.h: GetCyberMapAttr -96, ReadPixelArray -120. */
#include <exec/types.h>
#include <graphics/gfx.h>
#include <graphics/rastport.h>
#include <proto/exec.h>
#include <inline/macros.h>

extern struct Library *CyberGfxBase;

ULONG GetCyberMapAttr(struct BitMap *bm, ULONG attr)
{
    return LP2(0x60, ULONG, GetCyberMapAttr, struct BitMap *, bm, a0, ULONG, attr, d0,
               , CyberGfxBase);
}

void ReadPixelArray(APTR dest, ULONG destx, ULONG desty, ULONG destmod, struct RastPort *rp,
                    ULONG srcx, ULONG srcy, ULONG sizex, ULONG sizey, ULONG format)
{
    LP10NR(0x78, ReadPixelArray, APTR, dest, a0, ULONG, destx, d0, ULONG, desty, d1,
           ULONG, destmod, d2, struct RastPort *, rp, a1, ULONG, srcx, d3, ULONG, srcy, d4,
           ULONG, sizex, d5, ULONG, sizey, d6, ULONG, format, d7, , CyberGfxBase);
}
