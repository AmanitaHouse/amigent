/* tiles pack < raw > packbits       tiles index TW TH < pixels > k colours rows (nothing: too many)
 * tiles conv < rgb888 > rgb332
 * amigentd's picture helpers, cut out of amigentd.c by tests/test_tiles_c.py. */
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static ULONG in_mem[(1 << 20) / 4];  /* long aligned, as amigentd's tile buffers */
static ULONG out_mem[(1 << 20) / 4 + 1024];

int main(int argc, char **argv)
{
    UBYTE *in = (UBYTE *)in_mem, *out = (UBYTE *)out_mem;
    size_t n;

#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    n = fread(in, 1, sizeof(in_mem), stdin);
    tables_init();
    if (argc > 1 && !strcmp(argv[1], "pack")) {
        fwrite(out, 1, packbits(in, (LONG)n, out), stdout);
        return 0;
    }
    if (argc > 3 && !strcmp(argv[1], "index")) {
        LONG head = 0, rows = index_tile(in, atoi(argv[2]), atoi(argv[3]), out, &head);
        LONG i;
        if (rows)
            fwrite(out, 1, head + rows, stdout);
        for (i = 0; i < 256; i++)  /* the lookup is left as it was found */
            if (islot[i] != 0xFF)
                return 3;
        return 0;
    }
    if (argc > 1 && !strcmp(argv[1], "conv")) {
        rgb_to_332(in, out, (LONG)(n / 3));
        fwrite(out, 1, n / 3, stdout);
        return 0;
    }
    return 2;
}
