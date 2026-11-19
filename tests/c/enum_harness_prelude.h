/* Host stand-in for the exec types LOADED and TASKS use.
 * Nothing here is an Amiga library. Forbid and Permit only count.
 * BADDR is the real BCPL shift. Hunks and residents are placed below
 * 2 GiB so that shift and the resident link bit still round-trip.
 * A node cap in the daemon does not make a bad pointer safe to read;
 * this harness never feeds it one.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t ULONG;
typedef int32_t LONG;
typedef uint16_t UWORD;
typedef int16_t WORD;
typedef uint8_t UBYTE;
typedef int8_t BYTE;
typedef int BOOL;
typedef void *APTR;
typedef uint32_t BPTR;

#define TRUE 1
#define FALSE 0
#define MEMF_ANY 0
#define ERROR_NO_FREE_STORE 103

#define NT_TASK 1
#define NT_DEVICE 3
#define NT_RESOURCE 8
#define NT_LIBRARY 9
#define NT_PROCESS 13

#define BADDR(x) ((void *)((uintptr_t)(uint32_t)(x) << 2))

struct Node {
    struct Node *ln_Succ;
    struct Node *ln_Pred;
    UBYTE ln_Type;
    BYTE ln_Pri;
    char *ln_Name;
};

struct List {
    struct Node *lh_Head;
    struct Node *lh_Tail;
    struct Node *lh_TailPred;
    UBYTE lh_Type;
    UBYTE l_pad;
};

struct Library {
    struct Node lib_Node;
    UBYTE lib_Flags;
    UBYTE lib_pad;
    UWORD lib_NegSize;
    UWORD lib_PosSize;
    UWORD lib_Version;
    UWORD lib_Revision;
    APTR lib_IdString;
    ULONG lib_Sum;
    UWORD lib_OpenCnt;
};

struct Task {
    struct Node tc_Node;
    ULONG tc_SigWait;
    ULONG tc_SigRecvd;
    APTR tc_SPReg;
    APTR tc_SPLower;
    APTR tc_SPUpper;
};

struct Process {
    struct Task pr_Task;
    BPTR pr_SegList;
    BPTR pr_CLI;
};

struct CommandLineInterface {
    BPTR cli_CommandName;
    BPTR cli_Module;
};

struct Resident {
    APTR rt_MatchTag;
    APTR rt_EndSkip;
    UBYTE rt_Version;
    char *rt_Name;
};

struct ExecBase {
    struct List LibList;
    struct List DeviceList;
    struct List ResourceList;
    struct List TaskReady;
    struct List TaskWait;
    struct Task *ThisTask;
    APTR ResModules;
};

struct link {
    int fd;
};

static struct ExecBase sysbase_store;
static struct ExecBase *SysBase = &sysbase_store;

static int forbid_depth, forbid_calls, permit_calls;
static int allocs_forbidden, alloc_fail;

static void Forbid(void)
{
    forbid_depth++;
    forbid_calls++;
}

static void Permit(void)
{
    permit_calls++;
    if (forbid_depth > 0)
        forbid_depth--;
}

static void *AllocVec(ULONG size, ULONG flags)
{
    (void)flags;
    if (forbid_depth)
        allocs_forbidden++;
    if (alloc_fail || !size)
        return NULL;
    return calloc(1, size);
}

static void FreeVec(void *p)
{
    free(p);
}

static void CopyMem(const void *src, void *dst, ULONG n)
{
    if (src && dst && n)
        memcpy(dst, src, n);
}

static ULONG TypeOfMem(const void *p)
{
    return p ? 1 : 0;
}

#define LOW_SIZE (1u << 20)

static unsigned char *low_base;
static size_t low_used;

#ifdef _WIN32
void *VirtualAlloc(void *addr, size_t size, uint32_t type, uint32_t protect);
int VirtualFree(void *addr, size_t size, uint32_t type);
#else
#include <sys/mman.h>
#endif

static int reserve_low(void)
{
    static const uintptr_t bases[] = {
        0x20000000u, 0x30000000u, 0x40000000u, 0x50000000u
    };
    size_t i;

    for (i = 0; i < sizeof bases / sizeof bases[0]; i++) {
        void *p;
#ifdef _WIN32
        p = VirtualAlloc((void *)bases[i], LOW_SIZE, 0x1000u | 0x2000u, 0x04u);
#else
        p = mmap((void *)bases[i], LOW_SIZE, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        if (p == MAP_FAILED)
            p = NULL;
#endif
        if (!p)
            continue;
        if ((uintptr_t)p != bases[i] || (uintptr_t)p + LOW_SIZE >= 0x80000000u) {
#ifdef _WIN32
            VirtualFree(p, 0, 0x8000u);
#else
            munmap(p, LOW_SIZE);
#endif
            continue;
        }
        low_base = p;
        low_used = 0;
        return 1;
    }
    return 0;
}

static void *low_alloc(size_t n)
{
    void *p;
    n = (n + 3u) & ~(size_t)3u;
    if (!low_base && !reserve_low())
        return NULL;
    if (low_used + n > LOW_SIZE)
        return NULL;
    p = low_base + low_used;
    low_used += n;
    memset(p, 0, n);
    return p;
}

static uint32_t bptr_of(const void *p)
{
    uintptr_t a = (uintptr_t)p;
    if (!p || (a & 3u) || a >= 0x80000000u)
        return 0;
    return (uint32_t)(a >> 2);
}
