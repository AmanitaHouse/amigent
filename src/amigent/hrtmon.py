"""What amiga_hrtmon says. HRTmon is the debugger from Aminet (dev/debug/HRTmon).

Running the HRTmon command only loads the monitor into memory. It is entered
by its hotkey or by an NMI, and then it halts the operating system: no network,
no amigentd, until someone at the Amiga's own keyboard leaves it. Amigent never
enters it.
"""

MISSING = ("HRTmon is not installed: Which HRTmon found nothing on the command path. It comes "
           "from Aminet (dev/debug/HRTmon), not with the OS; copy the HRTmon program to C: "
           "and ask again.")
LOADED = ("HRTmon is loaded and waits in memory. Do not enter it from here: its hotkey or an "
          "NMI halts the whole system, and Amigent loses this Amiga until someone at the "
          "Amiga's own keyboard leaves the monitor.")
