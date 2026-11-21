# Hardware validation fixtures

`apollo_v4_matrix.json` is a machine-readable index of the Apollo V4 plan in
`docs/APOLLO_V4_HARDWARE_TEST_PLAN.md`.

It is **not** executed by ordinary CI. Do not add pytest collectors here that
contact an Amiga or mutate a V4 installation.
