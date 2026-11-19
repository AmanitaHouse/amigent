/* Drives the extracted c_loaded and c_tasks. One mode per process. */

#include <stdio.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static struct Library cap_libs[256];
static char cap_names[256][201];

static void wipe(void)
{
    forbid_depth = forbid_calls = permit_calls = 0;
    allocs_forbidden = alloc_fail = 0;
    fault_code = 0;
    sends = send_forbidden = 0;
    free(sent_buf);
    sent_buf = NULL;
    sent_len = 0;
    memset(SysBase, 0, sizeof *SysBase);
}

static void hang(struct List *list, struct Node *node)
{
    struct Node *tail = (struct Node *)&list->lh_Tail;
    struct Node *n;
    LONG guard = 0;

    node->ln_Succ = tail;
    if (!list->lh_Head || list->lh_Head == tail)
        list->lh_Head = node;
    else {
        for (n = list->lh_Head; n->ln_Succ != tail && guard < 10000; n = n->ln_Succ)
            guard++;
        n->ln_Succ = node;
    }
    list->lh_Tail = NULL;
}

static void fill_lib(struct Library *lib, char kind_type, const char *name, UWORD version)
{
    memset(lib, 0, sizeof *lib);
    lib->lib_Node.ln_Type = kind_type;
    lib->lib_Node.ln_Name = (char *)name;
    lib->lib_Version = version;
    lib->lib_Revision = 1;
    lib->lib_OpenCnt = 1;
}

static void own_task(void)
{
    static struct Task self;
    memset(&self, 0, sizeof self);
    self.tc_Node.ln_Name = "amigentd";
    self.tc_Node.ln_Type = NT_TASK;
    SysBase->ThisTask = &self;
}

static int finish(void)
{
    printf("fault=%ld sends=%d forbid_depth=%d forbid=%d permit=%d alloc_forbidden=%d send_forbidden=%d bytes=%u\n",
           (long)fault_code, sends, forbid_depth, forbid_calls, permit_calls,
           allocs_forbidden, send_forbidden, sent_len);
    if (sent_buf && sent_len)
        fwrite(sent_buf, 1, sent_len, stdout);
    fflush(stdout);
    if (forbid_depth != 0 || forbid_calls != permit_calls || allocs_forbidden || send_forbidden)
        return 1;
    return 0;
}

static int need_low(void)
{
    if (low_alloc(4))
        return 1;
    fprintf(stderr, "low memory unavailable\n");
    return 0;
}

struct hunkmem {
    uint32_t size;
    uint32_t next;
    uint8_t payload[16];
};

static struct hunkmem *make_hunks(int count, int bad_last)
{
    struct hunkmem *h = low_alloc(sizeof *h * (size_t)count);
    int i;

    if (!h)
        return NULL;
    for (i = 0; i < count; i++) {
        h[i].size = (bad_last && i + 1 == count) ? 4u : 24u;
        h[i].next = (i + 1 < count) ? bptr_of(&h[i + 1].next) : 0;
    }
    return h;
}

static int add_program(struct List *list, struct Process *proc, const char *name,
                       struct hunkmem *hunks)
{
    struct CommandLineInterface *cli = low_alloc(sizeof *cli);
    unsigned char *bstr = low_alloc(8);

    if (!cli || !bstr || !hunks)
        return 0;
    bstr[0] = 3;
    memcpy(bstr + 1, "cmd", 3);
    cli->cli_CommandName = bptr_of(bstr);
    cli->cli_Module = bptr_of(&hunks->next);
    memset(proc, 0, sizeof *proc);
    proc->pr_Task.tc_Node.ln_Type = NT_PROCESS;
    proc->pr_Task.tc_Node.ln_Name = (char *)name;
    proc->pr_CLI = bptr_of(cli);
    hang(list, &proc->pr_Task.tc_Node);
    return 1;
}

static int mode_short(void)
{
    static struct Library lib, dev, res;
    fill_lib(&lib, NT_LIBRARY, "exec.library", 47);
    fill_lib(&dev, NT_DEVICE, "trackdisk.device", 40);
    fill_lib(&res, NT_RESOURCE, "potgo.resource", 37);
    hang(&SysBase->LibList, &lib.lib_Node);
    hang(&SysBase->DeviceList, &dev.lib_Node);
    hang(&SysBase->ResourceList, &res.lib_Node);
    c_loaded(NULL);
    return finish();
}

static int mode_short_tasks(void)
{
    static struct Task ready;
    static struct Process waiting;
    own_task();
    memset(&ready, 0, sizeof ready);
    memset(&waiting, 0, sizeof waiting);
    ready.tc_Node.ln_Name = "input.device";
    ready.tc_Node.ln_Type = NT_TASK;
    ready.tc_Node.ln_Pri = 20;
    waiting.pr_Task.tc_Node.ln_Name = "shell";
    waiting.pr_Task.tc_Node.ln_Type = NT_PROCESS;
    hang(&SysBase->TaskReady, &ready.tc_Node);
    hang(&SysBase->TaskWait, &waiting.pr_Task.tc_Node);
    c_tasks(NULL);
    return finish();
}

static int mode_cycle_libs(void)
{
    static struct Library a, b;
    fill_lib(&a, NT_LIBRARY, "alpha.library", 1);
    fill_lib(&b, NT_LIBRARY, "beta.library", 1);
    a.lib_Node.ln_Succ = &b.lib_Node;
    b.lib_Node.ln_Succ = &a.lib_Node;
    SysBase->LibList.lh_Head = &a.lib_Node;
    c_loaded(NULL);
    return finish();
}

static int mode_cycle_tasks(void)
{
    static struct Task a, b;
    own_task();
    memset(&a, 0, sizeof a);
    memset(&b, 0, sizeof b);
    a.tc_Node.ln_Name = "one";
    a.tc_Node.ln_Type = NT_TASK;
    b.tc_Node.ln_Name = "two";
    b.tc_Node.ln_Type = NT_TASK;
    a.tc_Node.ln_Succ = &b.tc_Node;
    b.tc_Node.ln_Succ = &a.tc_Node;
    SysBase->TaskReady.lh_Head = &a.tc_Node;
    c_tasks(NULL);
    return finish();
}

static int mode_cycle_procs(void)
{
    static struct Process a, b;
    memset(&a, 0, sizeof a);
    memset(&b, 0, sizeof b);
    a.pr_Task.tc_Node.ln_Type = NT_PROCESS;
    b.pr_Task.tc_Node.ln_Type = NT_PROCESS;
    a.pr_Task.tc_Node.ln_Name = "a";
    b.pr_Task.tc_Node.ln_Name = "b";
    a.pr_Task.tc_Node.ln_Succ = &b.pr_Task.tc_Node;
    b.pr_Task.tc_Node.ln_Succ = &a.pr_Task.tc_Node;
    SysBase->TaskReady.lh_Head = &a.pr_Task.tc_Node;
    c_loaded(NULL);
    return finish();
}

static int mode_alloc_fail(void)
{
    alloc_fail = 1;
    c_loaded(NULL);
    c_tasks(NULL);
    return finish();
}

static int mode_reply_cap(void)
{
    int i;
    for (i = 0; i < 256; i++) {
        memset(cap_names[i], 'N', 200);
        cap_names[i][200] = 0;
        fill_lib(&cap_libs[i], NT_LIBRARY, cap_names[i], 1);
        hang(&SysBase->LibList, &cap_libs[i].lib_Node);
    }
    c_loaded(NULL);
    return finish();
}

static int mode_hunk_cap(void)
{
    static struct Process proc;
    struct hunkmem *h;
    if (!need_low())
        return 77;
    h = make_hunks(ENUM_HUNK_PER + 1, 0);
    if (!h || !add_program(&SysBase->TaskReady, &proc, "long", h))
        return 77;
    c_loaded(NULL);
    return finish();
}

static int mode_hunk_end(void)
{
    static struct Process proc;
    struct hunkmem *h;
    if (!need_low())
        return 77;
    h = make_hunks(2, 1);
    if (!h || !add_program(&SysBase->TaskReady, &proc, "short", h))
        return 77;
    c_loaded(NULL);
    return finish();
}

static int mode_hunk_ok(void)
{
    static struct Process proc;
    struct hunkmem *h;
    if (!need_low())
        return 77;
    h = make_hunks(2, 0);
    if (!h || !add_program(&SysBase->TaskReady, &proc, "ok", h))
        return 77;
    c_loaded(NULL);
    return finish();
}

static int mode_hunk_total(void)
{
    static struct Process proc[5];
    static const char *names[] = {"p0", "p1", "p2", "p3", "p4"};
    int i;
    if (!need_low())
        return 77;
    for (i = 0; i < 5; i++) {
        struct hunkmem *h = make_hunks(60, 0);
        if (!h || !add_program(&SysBase->TaskReady, &proc[i], names[i], h))
            return 77;
    }
    c_loaded(NULL);
    return finish();
}

static int mode_resident_cap(void)
{
    enum { EXTRA = 2 };
    struct Resident *rs;
    ULONG *table;
    char *name;
    int n = ENUM_RESIDENT_MAX + EXTRA, i;

    if (!need_low())
        return 77;
    rs = low_alloc(sizeof *rs * (size_t)n);
    table = low_alloc(sizeof *table * (size_t)(n + 1));
    name = low_alloc(8);
    if (!rs || !table || !name)
        return 77;
    memcpy(name, "module", 7);
    for (i = 0; i < n; i++) {
        rs[i].rt_Name = name;
        rs[i].rt_Version = 37;
        rs[i].rt_EndSkip = name;
        table[i] = (ULONG)(uintptr_t)(rs + i);
    }
    table[n] = 0;
    SysBase->ResModules = table;
    c_loaded(NULL);
    return finish();
}

static int mode_resident_cycle(void)
{
    ULONG *a, *b;
    if (!need_low())
        return 77;
    a = low_alloc(sizeof *a);
    b = low_alloc(sizeof *b);
    if (!a || !b)
        return 77;
    *a = (ULONG)(uintptr_t)b | 0x80000000UL;
    *b = (ULONG)(uintptr_t)a | 0x80000000UL;
    SysBase->ResModules = a;
    c_loaded(NULL);
    return finish();
}

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "";

#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    if (!strcmp(mode, "limits")) {
        printf("list=%d hunk_per=%d hunk_total=%d resident=%d reply=%d\n",
               ENUM_LIST_MAX, ENUM_HUNK_PER, ENUM_HUNK_TOTAL, ENUM_RESIDENT_MAX,
               ENUM_REPLY_MAX);
        return 0;
    }
    wipe();
    if (!strcmp(mode, "short"))
        return mode_short();
    if (!strcmp(mode, "short-tasks"))
        return mode_short_tasks();
    if (!strcmp(mode, "cycle-libs"))
        return mode_cycle_libs();
    if (!strcmp(mode, "cycle-tasks"))
        return mode_cycle_tasks();
    if (!strcmp(mode, "cycle-procs"))
        return mode_cycle_procs();
    if (!strcmp(mode, "alloc-fail"))
        return mode_alloc_fail();
    if (!strcmp(mode, "reply-cap"))
        return mode_reply_cap();
    if (!strcmp(mode, "hunk-cap"))
        return mode_hunk_cap();
    if (!strcmp(mode, "hunk-end"))
        return mode_hunk_end();
    if (!strcmp(mode, "hunk-ok"))
        return mode_hunk_ok();
    if (!strcmp(mode, "hunk-total"))
        return mode_hunk_total();
    if (!strcmp(mode, "resident-cap"))
        return mode_resident_cap();
    if (!strcmp(mode, "resident-cycle"))
        return mode_resident_cycle();
    fprintf(stderr, "unknown mode\n");
    return 2;
}
