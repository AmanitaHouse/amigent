# Packaged Apollo daemon = hardware-validated stream-safe build

**Branch:** `review/fork-audio-stream-packaging` (based on `065c112`)  
**Packaged path:** `src/amigent/amiga/bin/amigentd.apollo`  
**SHA-256:** `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c`  
**Size:** 129944  
**Source:** `contrib/fork-audio-stream-safety` @ `496f142` / review `065c112`  
**Hardware:** Stage 3B Phase 4 oneshot + Phase 5 supervised stream PASS  
**Evidence:** `~/amigent-evidence/stage3b-fork-stream/20261121T034526Z`  
**Preserved prior F-DAE:** `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` (131292 B) under  
`~/amigent-evidence/fdae-preserved-before-stream-safe-packaging/`

## Why source-only still shipped F-DAE

setuptools packages **prebuilt** bytes from `src/amigent/amiga/bin/*`
(`package-data`). Changing `src/native/.../apollo.c` does **not** rebuild
or replace that file. The wheel therefore kept F-DAE until this packaging
commit copied the verified candidate into the package-data path.

## Update path

Both binaries report `$VER: amigentd 1.4.0`. After the bytes change,
`identify()` no longer matches the installed F-DAE, which would trip the
unknown-Apollo same-version guard. `SUPERSEDED_APOLLO_SHA256` allows
replacement of that known prior packaged digest only.
