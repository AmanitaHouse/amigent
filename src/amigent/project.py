"""A new Amiga program in C, built on the Amiga with vbcc.

amiga_create_project writes a starting point into a folder on the Amiga:
main.c (a Shell program or one with a window), a `build` script for vbcc with
the NDK, and a short ReadMe. amiga_build runs the script as a job and reports
the compiler's messages; amiga_run then starts the program with its debug
output. vbcc and the NDK come from a developer package such as AmiKit's
DevPack; `devpack` names its folder (with vbcc/ and SDK/NDK 3.9/ inside), or
an existing VBCC: assign is used.
"""

from __future__ import annotations

import re

SHELL = r'''/* {name}: a Shell program. Build with "Execute build", run with "{name}". */
#include <exec/types.h>
#include <proto/exec.h>
#include <proto/dos.h>

static const char version[] = "$VER: {name} 0.1 ({date})";

int main(void)
{{
    PutStr("Hello from {name}\n");
    return RETURN_OK;
}}
'''

WINDOW = r'''/* {name}: a window on the Workbench, closed by its close gadget. */
#include <exec/types.h>
#include <intuition/intuition.h>
#include <proto/exec.h>
#include <proto/intuition.h>
#include <proto/graphics.h>

static const char version[] = "$VER: {name} 0.1 ({date})";
struct IntuitionBase *IntuitionBase;
struct GfxBase *GfxBase;

int main(void)
{{
    struct Window *win;
    BOOL done = FALSE;

    IntuitionBase = (struct IntuitionBase *)OpenLibrary("intuition.library", 37);
    GfxBase = (struct GfxBase *)OpenLibrary("graphics.library", 37);
    if (!IntuitionBase || !GfxBase)
        return RETURN_FAIL;
    win = OpenWindowTags(NULL, WA_Title, (ULONG)"{name}", WA_Width, 320, WA_Height, 120,
                         WA_DragBar, TRUE, WA_DepthGadget, TRUE, WA_CloseGadget, TRUE,
                         WA_Activate, TRUE, WA_IDCMP, IDCMP_CLOSEWINDOW, TAG_END);
    if (win) {{
        Move(win->RPort, 20, 40);
        Text(win->RPort, "Hello from {name}", {length});
        while (!done) {{
            struct IntuiMessage *msg;
            WaitPort(win->UserPort);
            while ((msg = (struct IntuiMessage *)GetMsg(win->UserPort))) {{
                if (msg->Class == IDCMP_CLOSEWINDOW)
                    done = TRUE;
                ReplyMsg((struct Message *)msg);
            }}
        }}
        CloseWindow(win);
    }}
    CloseLibrary((struct Library *)GfxBase);
    CloseLibrary((struct Library *)IntuitionBase);
    return win ? RETURN_OK : RETURN_FAIL;
}}
'''

BUILD = r'''.KEY CPU/K,DEVPACK/K
.DEF CPU {cpu}
.DEF DEVPACK {devpack}
; Builds {name} with vbcc. DEVPACK is the folder with vbcc/ and SDK/NDK 3.9/.
FailAt 21
Stack 65536
If NOT EXISTS VBCC:
  Assign VBCC: <DEVPACK>/vbcc
EndIf
Assign vincludeos3: VBCC:targets/m68k-amigaos/include
Assign vincludeos3: "<DEVPACK>/SDK/NDK 3.9/Include/include_h" ADD
Assign vlibos3: VBCC:targets/m68k-amigaos/lib
Path VBCC:bin ADD
VBCC:bin/vc +VBCC:config/aos68k -c99 -O1 -g -cpu=<CPU> -o {name} main.c -lamiga
If WARN
  Echo "build failed"
  Quit 10
EndIf
Echo "built {name}"
'''

README = '''{name}

main.c   the program
build    Execute build [CPU 68000] [DEVPACK path]: compiles with vbcc
'''


def name_ok(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,29}", name or ""):
        raise ValueError("a project name: letters, digits, - and _, up to 30, starting with a letter")
    return name


def files(name: str, kind: str = "shell", cpu: str = "68000", devpack: str = "SYS:DevPack",
          date: str = "1.1.2026") -> dict[str, str]:
    name = name_ok(name)
    if kind not in ("shell", "window"):
        raise ValueError("kind: shell or window")
    text = f"Hello from {name}"
    main = (SHELL if kind == "shell" else WINDOW).format(name=name, date=date, length=len(text))
    return {"main.c": main, "build": BUILD.format(name=name, cpu=cpu, devpack=devpack),
            "ReadMe": README.format(name=name)}
