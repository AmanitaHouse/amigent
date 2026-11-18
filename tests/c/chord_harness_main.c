/* Host driver. Keys go through do_input, the daemon's input dispatch.
 * The reset stub only counts.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned qual_bits;

static void raw_packet(unsigned code, int down, unsigned qual)
{
    unsigned char packet[10];

    memset(packet, 0, sizeof packet);
    packet[0] = (unsigned char)CMD_RAWKEY;
    packet[1] = down ? 1 : 0;
    packet[2] = (unsigned char)((code >> 8) & 0xFF);
    packet[3] = (unsigned char)(code & 0xFF);
    packet[4] = (unsigned char)((qual >> 8) & 0xFF);
    packet[5] = (unsigned char)(qual & 0xFF);
    (void)do_input(packet);
}

static int hex_byte(const char *text)
{
    int hi, lo;

    hi = text[0];
    lo = text[1];
    if (hi >= '0' && hi <= '9')
        hi -= '0';
    else if (hi >= 'a' && hi <= 'f')
        hi = hi - 'a' + 10;
    else if (hi >= 'A' && hi <= 'F')
        hi = hi - 'A' + 10;
    else
        return -1;
    if (lo >= '0' && lo <= '9')
        lo -= '0';
    else if (lo >= 'a' && lo <= 'f')
        lo = lo - 'a' + 10;
    else if (lo >= 'A' && lo <= 'F')
        lo = lo - 'A' + 10;
    else
        return -1;
    return (hi << 4) | lo;
}

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
        } else if (strcmp(word, "qual") == 0) {
            if (scanf("%lx", &value) != 1)
                return 2;
            qual_bits = (unsigned)value;
        } else if (strcmp(word, "down") == 0 || strcmp(word, "up") == 0) {
            if (scanf("%lx", &value) != 1)
                return 2;
            raw_packet((unsigned)value, word[0] == 'd', qual_bits);
        } else if (strcmp(word, "packet") == 0) {
            char hex[21];
            unsigned char packet[10];
            int i, byte;

            if (scanf("%20s", hex) != 1 || strlen(hex) != 20)
                return 2;
            for (i = 0; i < 10; i++) {
                byte = hex_byte(hex + 2 * i);
                if (byte < 0)
                    return 2;
                packet[i] = (unsigned char)byte;
            }
            (void)do_input(packet);
        } else if (strcmp(word, "count") == 0) {
            printf("%d\n", reboots);
            fflush(stdout);
        } else if (strcmp(word, "events") == 0) {
            printf("%d\n", events);
            fflush(stdout);
        } else {
            return 2;
        }
    }
    return 0;
}
