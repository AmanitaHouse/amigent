/* ApolloOS-only pieces of amigentd. The 68000 and 68020 builds do not include them. */
#ifndef AMIGENT_APOLLO_H
#define AMIGENT_APOLLO_H

#include <exec/types.h>

struct Screen;

BOOL apollo_os_here(void);
UWORD apollo_board(void);
const char *apollo_board_name(UWORD board);
BOOL apollo_showing(struct Screen *scr);
BOOL apollo_size(struct Screen *scr, UWORD *w, UWORD *h);
BOOL apollo_read(struct Screen *scr, LONG x, LONG y, LONG w, LONG h, UBYTE *out);
LONG apollo_audio(UBYTE *dst, LONG cap, ULONG *rate, ULONG ms);
/* A stream owns the mix until release. pump copies each finished half into
 * the FIFO once, in the order the DAC played it. The audio interrupt is not hooked. */
BOOL apollo_audio_claim(void);
void apollo_audio_release(void);
BOOL apollo_audio_pump(ULONG *rate);
/* 1 when the mix buffer changed since the last call. The rewrite is the
 * time to send: the next stable window has not started. */
UBYTE apollo_mix_stir(void);
ULONG apollo_audio_seq(void);
ULONG apollo_audio_bytes(void);
ULONG apollo_audio_span(void);
void apollo_audio_sustain(ULONG n);
ULONG apollo_audio_pending(void);
LONG apollo_audio_take(UBYTE *dst, LONG cap);
void apollo_audio_breathe(void);
/* Let another task of this priority fill the next half. Does not drop
 * under the screen reader. */
void apollo_audio_nudge(void);
/* Pointer of each mix pass this tone, so a skipped pass can be told from a
 * second buffer. Written once, when the tone goes quiet. */
void apollo_mix_ptrs(void);
LONG apollo_pip(UBYTE *dst, LONG cap, UWORD *x, UWORD *y, UWORD *w, UWORD *h);
/* TRUE when [at, at+n) shares a byte with a SAGA, PIP or VREG window whose
 * read can change hardware state. A request that only crosses the edge counts. */
BOOL apollo_mmio_hit(ULONG at, ULONG n);
LONG ammx_differs(const UBYTE *a, const UBYTE *b, LONG n);
void ammx_rgb332(const UBYTE *rgb, UBYTE *dst, LONG pixels);

#endif
