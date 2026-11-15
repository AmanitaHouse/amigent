#include <stdio.h>

/* Calls the plain-admission functions copied out of amigentd.c.
 * TLS listening, TLS init failure and handshake failure are not arguments.
 * AUDIO and CHANNEL share each row: the socket is closed before either command. */

static int failures;

static void expect_reject(const char *name, int tls_only, int setup, int loopback, int want)
{
    int got = amigent_plain_reject(tls_only, setup, loopback);

    if (got != want) {
        fprintf(stderr, "%s: reject got %d want %d\n", name, got, want);
        failures++;
    }
}

static void expect_flag(const char *name, int tls_only, int setup, int want)
{
    int got = amigent_plain_closed_flag(tls_only, setup);

    if (got != want) {
        fprintf(stderr, "%s: flag got %d want %d\n", name, got, want);
        failures++;
    }
}

int main(void)
{
    expect_reject("tlsonly listening normal remote audio/channel", 1, 0, 0, 1);
    expect_reject("tlsonly listening normal loopback audio/channel", 1, 0, 1, 0);
    expect_reject("tlsonly unavailable normal remote audio/channel", 1, 0, 0, 1);
    expect_reject("tlsonly unavailable normal loopback audio/channel", 1, 0, 1, 0);
    expect_reject("tls init failure remote audio/channel", 1, 0, 0, 1);
    expect_reject("tls init failure loopback audio/channel", 1, 0, 1, 0);
    expect_reject("handshake failure remote audio/channel", 1, 0, 0, 1);
    expect_reject("handshake failure loopback audio/channel", 1, 0, 1, 0);
    expect_reject("explicit setup remote audio/channel", 1, 1, 0, 0);
    expect_reject("explicit setup loopback audio/channel", 1, 1, 1, 0);
    expect_reject("no tlsonly remote audio/channel", 0, 0, 0, 0);
    expect_reject("no tlsonly loopback audio/channel", 0, 0, 1, 0);
    expect_reject("no tlsonly during setup remote audio/channel", 0, 1, 0, 0);

    expect_flag("closed while tlsonly, tls up or down", 1, 0, 4);
    expect_flag("open during explicit setup", 1, 1, 0);
    expect_flag("open without tlsonly", 0, 0, 0);
    expect_flag("open without tlsonly during setup", 0, 1, 0);

    /* A dead listener must not look like SETUP and must not clear the flag. */
    if (!amigent_plain_reject(1, 0, 0) || amigent_plain_closed_flag(1, 0) != 4)
        failures++;
    if (amigent_plain_reject(1, 1, 0) || amigent_plain_closed_flag(1, 1) != 0)
        failures++;

    return failures ? 1 : 0;
}
