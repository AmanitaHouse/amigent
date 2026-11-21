# Lessons from the successful U-DAE exclusive session

1. **Stage before QUIT** — Uploading and hashing the candidate while production TLS still works avoided a blind transfer after AmiGent was down.  
2. **Physical Shell is mandatory** — Launch and restore were typed at the V4; AmiGent cannot recover itself after `QUIT`.  
3. **TLS is PORT+1** — With `TLSONLY` and a pinned cert, the PC dials **6802**, not 6801.  
4. **Protect with a real path** — Use `Protect "Programs:…/file" +e` (FAQ/setup form), not a placeholder.  
5. **ARexx QUIT via `rx`** — Writing a tiny Rexx script and `rx` it (as in `amiga_arexx` / update) works; expect the TCP session to drop.  
6. **`self` ≠ staging leaf** — Uncommon extensions (`.udae`) may not appear in SYSINFO `self`; trust the hash-verified path (`docs/APOLLO_V4_SELF_PATH_NOTE.md`). Prefer conventional names for future staging if `self` matters.  
7. **Exclusive beats second PORT** for this smoke test — No hooks/AUDIO/monitor conflicts to untangle.  
8. **Narrow scope kept restore simple** — No Update swap, no reboot, production `C:amigentd` untouched.  
9. **U-DAE ≠ F-DAE** — Different binaries and hashes; fork daemon still needs its own authorised session.  
10. **Do not over-claim** — `audio=1` / `poke=0` / `probe=1` are advertisements, not live feature tests.
