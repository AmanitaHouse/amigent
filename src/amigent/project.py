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

BUILD = r'''.KEY CPU/K,DEVPACK/K,FPU/K,TARGET/K
.DEF CPU {cpu}
.DEF DEVPACK {devpack}
.DEF FPU NONE
.DEF TARGET 68K
; Builds {name} with vbcc. DEVPACK is the folder with vbcc/ and SDK/NDK 3.9/.
; FPU 68881 makes FPU code with m881.lib (68020 or better with a 68881/68882 or a
; 68040/060 with its library), FPU 68040 with m040.lib (68040/060 FPU only).
; Without FPU no FPU instruction is made and the program runs on every Amiga.
; TARGET WARPOS makes a PowerPC program for WarpOS with vbcc's ppc-warpos target
; (Aminet dev/c/vbcc_target_ppc-warpos); it runs only on a PowerPC board with WarpOS.
; A program that calls powerpc.library itself also needs the WarpOS includes in vincludewos:.
FailAt 21
Stack 65536
If NOT EXISTS VBCC:
  Assign VBCC: <DEVPACK>/vbcc
EndIf
Assign vincludeos3: VBCC:targets/m68k-amigaos/include
Assign vincludeos3: "<DEVPACK>/SDK/NDK 3.9/Include/include_h" ADD
Assign vlibos3: VBCC:targets/m68k-amigaos/lib
Path VBCC:bin ADD
If "<TARGET>" EQ "WARPOS"
  If NOT EXISTS VBCC:config/warpos
    Echo "build failed: vbcc has no WarpOS target here (VBCC:config/warpos); install vbcc_target_ppc-warpos"
    Quit 10
  EndIf
  If NOT EXISTS VBCC:bin/vbccppc
    Echo "build failed: vbcc's PowerPC compiler VBCC:bin/vbccppc is missing"
    Quit 10
  EndIf
  Assign vincludewos: VBCC:targets/ppc-warpos/include
  Assign vincludewos: "<DEVPACK>/SDK/NDK 3.9/Include/include_h" ADD
  Assign vlibwos: VBCC:targets/ppc-warpos/lib
  VBCC:bin/vc +VBCC:config/warpos -c99 -O1 -o {name} main.c -lamiga
  If WARN
    Echo "build failed"
    Quit 10
  EndIf
  Echo "built {name} for WarpOS"
  Quit 0
EndIf
If "<FPU>" EQ "NONE"
  VBCC:bin/vc +VBCC:config/aos68k -c99 -O1 -g -cpu=<CPU> -o {name} main.c -lamiga
  If WARN
    Echo "build failed"
    Quit 10
  EndIf
Else
  If "<FPU>" EQ "68040"
    VBCC:bin/vc +VBCC:config/aos68k -c99 -O1 -g -cpu=<CPU> -fpu=68040 -o {name} main.c -lm040 -lamiga
    If WARN
      Echo "build failed"
      Quit 10
    EndIf
  Else
    VBCC:bin/vc +VBCC:config/aos68k -c99 -O1 -g -cpu=<CPU> -fpu=68881 -o {name} main.c -lm881 -lamiga
    If WARN
      Echo "build failed"
      Quit 10
    EndIf
  EndIf
EndIf
Echo "built {name}"
'''

README = '''{name}

main.c   the program
build    Execute build [CPU 68000] [DEVPACK path] [FPU 68881|68040] [TARGET WARPOS]: compiles with vbcc
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
