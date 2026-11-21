# Draft comments for Apollo contributions (DO NOT POST without authorisation)

Public-safe drafts only. Adjust PR numbers/links when posting.

Reconciliation context: `docs/APOLLO_V4_UPSTREAM_SEVEN_PR_RECONCILIATION.md`.

---

## A — Upstream #31 (ApolloOS identification) — historical draft (superseded by A2)

> Hardware context note (Apollo V4-SA, ApolloOS, Kickstart 51.51): a separate exclusive session ran the protected Apollo contribution daemon (SHA-256 `456fce2632…`, 129844 bytes) and negotiated AmiGent protocol 6 over TLS. SYSINFO reported `os=ApolloOS`, `cpu=68080`, `board_name=V4-SA`, and `attn_flags` including the AFF_FPGA bit. This supports the real-world ApolloOS/V4 environment assumed by the identification work; it is **not** a substitute for executing the Apollo probe binary’s stdout/exit checks on hardware, which were not part of that session.

---

## A2 — Upstream #31 follow-up (READY TO REVIEW — do not post without authorisation)

**Why warranted:** our posted HW comment said probe / AUDIO / MMIO / install were not yet established. Probe HW and bounded later tests now exist for **our** builds. The private `feature/1.5.0` detect rewrite is still unverified. Do **not** duplicate the earlier daemon-smoke paragraph.

**Paste candidate:**

> **Hardware evidence follow-up (Apollo V4-SA / ApolloOS / Kickstart 51.51 / 68080)**
>
> Since the earlier protocol-6 daemon smoke note, we have completed additional physical checks that are relevant to this identification work. These results are for the executables named below. They do **not** validate an unpublished `feature/1.5.0` tree or any privately adapted detect binary.
>
> **Setup probes (production daemon left running; no install/update):**
>
> - Packaged contribution probe SHA-256 `ab454b39988bd7b88c24058d0398507456ff12ff180b638d626beac821e1aff4` (3112 bytes): stdout `ApolloOS`, exit 0.
> - Core-evidence probe SHA-256 `96ca1b389980b5a94ce0fc94c67c8eeafa7dd2455df497f52532e15409ba0265` (3224 bytes): stdout `ApolloOS` then `68080`, exit 0 (ApolloOS together with AttnFlags bit 10 — the same bit index our sources call `AFF_FPGA` / `(1<<10)`).
>
> On this board, SYSINFO also reported `os=ApolloOS`, `cpu=68080`, and AttnFlags including that bit. The positive probe path did not need the `$DFF3FC` board-register fallback.
>
> **Still not claimed here:**
>
> - Your private `feature/1.5.0` detect changes (exec 51 + `AFB_68080` only; probe gated on a packaged `amigentd.apollo`; removal of `$DFF3FC` as an OS-detect fallback; catalogue fold-in with #38). We cannot independently review that branch while it is unpublished.
> - Negative detection cases, AmigaOS-on-Vampire, AROS/AmigaOS 4 confusion cases, or installer/`--update` selection.
> - Live POKE writes, TRACE activation, or MMIO windows beyond separate bounded PEEK-refuse tests on a different daemon identity.
>
> We remain happy to re-test a public 1.5.0 snapshot on this V4-SA once it is available, and to rebase the remaining Apollo contribution stack only after that review.

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
