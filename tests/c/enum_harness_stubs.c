/* Answers from the extracted walk. Counts a send that happens while forbidden. */

static LONG fault_code;
static int sends, send_forbidden;
static char *sent_buf;
static unsigned sent_len;

static BOOL c_fault(struct link *l, LONG code)
{
    (void)l;
    if (forbid_depth)
        send_forbidden++;
    fault_code = code;
    sends++;
    return FALSE;
}

static BOOL c_text(struct link *l, struct text *t)
{
    (void)l;
    if (forbid_depth)
        send_forbidden++;
    free(sent_buf);
    sent_buf = NULL;
    sent_len = 0;
    if (t->buf && t->len) {
        sent_buf = malloc((size_t)t->len + 1);
        if (sent_buf) {
            memcpy(sent_buf, t->buf, t->len);
            sent_buf[t->len] = 0;
            sent_len = t->len;
        }
    }
    FreeVec(t->buf);
    t->buf = NULL;
    sends++;
    return TRUE;
}
