# Draft comments for Apollo contributions (DO NOT POST without authorisation)

Public-safe drafts only. Adjust PR numbers/links when posting.

---

## A — Upstream #31 (ApolloOS identification)

> Hardware context note (Apollo V4-SA, ApolloOS, Kickstart 51.51): a separate exclusive session ran the protected Apollo contribution daemon (SHA-256 `456fce2632…`, 129844 bytes) and negotiated AmiGent protocol 6 over TLS. SYSINFO reported `os=ApolloOS`, `cpu=68080`, `board_name=V4-SA`, and `attn_flags` including the AFF_FPGA bit. This supports the real-world ApolloOS/V4 environment assumed by the identification work; it is **not** a substitute for executing the Apollo probe binary’s stdout/exit checks on hardware, which were not part of that session.

---

## B — Fork review #4 (Apollo daemon foundation) / protected stack packaging

> Hardware smoke test (exclusive session, production left untouched): the protected upstream Apollo daemon build (`456fce2632…`) launched from a non-`C:` staging path with `TLSONLY`, completed a protocol-6 TLS handshake, returned SYSINFO/volumes/`Version`, exited cleanly via ARexx `QUIT`, and allowed restoration of the pre-existing protocol-5 production daemon without reboot.  
>  
> **Not claimed by this test:** AUDIO/Hear, monitor, HRTmon, live MMIO/ALLOWPOKE, probe execution, installer selection, or update/fallback. SYSINFO `poke=0` was observed but is not a live MMIO refusal trial.  
>  
> Note: SYSINFO `self` reported the staging drawer with program name `amigentd` while the staged file was named `amigentd.udae`. Offline source review shows `self` comes from `GetProgramDir` + `GetProgramName`/`FilePart`, not from a truncation bug in the `self` buffer; treat the hash-verified staging path as authoritative.

---

## C — What not to say on #5 / #6 / #8 / #10 / F-DAE

Do **not** post “hardware validated” for MMIO, AUDIO, Hear, probe AFF_FPGA exit codes, or the fork’s larger daemon (`1e0e3f65…`) based on the U-DAE smoke session alone.
