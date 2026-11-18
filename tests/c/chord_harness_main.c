/* Host driver for note_reset_chord. The reset stub only counts. */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    char word[32];
    unsigned long value;

    SysBase->LibNode.lib_Version = 37;
    while (scanf("%31s", word) == 1) {
        if (strcmp(word, "version") == 0) {
            if (scanf("%lu", &value) != 1)
                return 2;
            SysBase->LibNode.lib_Version = (unsigned short)value;
        } else if (strcmp(word, "time") == 0) {
            if (scanf("%lu", &value) != 1)
                return 2;
            clock_ms = (ULONG)value;
        } else if (strcmp(word, "down") == 0 || strcmp(word, "up") == 0) {
            if (scanf("%lx", &value) != 1)
                return 2;
            note_reset_chord((UBYTE)value, word[0] == 'd');
        } else if (strcmp(word, "count") == 0) {
            printf("%d\n", reboots);
            fflush(stdout);
        } else {
            return 2;
        }
    }
    return 0;
}
