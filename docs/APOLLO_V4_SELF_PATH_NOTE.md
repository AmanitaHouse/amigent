# SYSINFO `self` vs staged filename (offline analysis)

**Observed (Stage 2B U-DAE, physical V4):**

| Role | Path |
|------|------|
| Staged / hash-verified file | `Programs:AmiGent-Stage2B/amigentd.udae` |
| SYSINFO `self` | `Programs:AmiGent-Stage2B/amigentd` |

No further V4 contact was used for this note.

## Source construction

From `src/native/amiga/daemon/amigentd.c`:

```c
/* PROGDIR: and the program's name, as a path the Shell can run */
static void find_self(int argc, char **argv)
{
    BPTR dir = GetProgramDir();
    char name[108];
    const char *file = NULL;

    if (argc == 0) {
        /* Workbench: wa_Name */
        ...
    } else if (GetProgramName(name, sizeof(name)))
        file = (const char *)FilePart(name);
    if (!dir || !file || !NameFromLock(dir, self_path, sizeof(self_path)) ||
        !AddPart(self_path, file, sizeof(self_path)))
        self_path[0] = 0;
}
```

SYSINFO emits `self=` from `self_path` when non-empty (`c_sysinfo`).  
`PROTOCOL.md` (protocol 6): `self` is where this amigentd lives (`PROGDIR:` and its name), for job `FOLLOW` re-invoke.

## What this is / is not

| Hypothesis | Verdict from source + observation |
|------------|-----------------------------------|
| Path-buffer truncation in `self_path[256]` | **Rejected** — directory component is complete; `amigentd.udae` fits easily |
| amigentd strips extensions in `find_self` | **Rejected** — no strip logic; uses `GetProgramName` / `FilePart` / WB `wa_Name` as-is |
| CLI / `GetProgramName` program-name reporting | **Supported** — file component of `self` is whatever dos.library returns as the process program name; here that name lacked `.udae` |
| Staging API wrote wrong name | **Rejected** — PC read-back hash matched U-DAE at `…/amigentd.udae` |

## Remaining uncertainty

We did not dump raw `GetProgramName` / `cli_CommandName` on the live V4. Whether ApolloOS/dos.library omits uncommon suffixes such as `.udae` from the CLI program name is therefore an **OS/CLI naming behaviour**, not fully instrumented here.

## Severity

- **Not** treated as a confirmed amigentd defect requiring a change to protected contribution history.  
- **Caveat:** `self` may be an imperfect re-invoke path for `FOLLOW` when the on-disk name uses a nonstandard extension; hash-verified staging path remains authoritative for identity.  
- Prefer staging names that match normal Amiga program naming (e.g. `amigentd` or `amigentd.apollo`) in future sessions if `self` fidelity matters.

No code change in this task.
