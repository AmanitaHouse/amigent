#!/bin/sh
# Shared checks for the AmiGent identity guard.
# Fail closed. Never rewrite an identity.

guard_fail() {
    printf '%s\n' "amigent identity guard: $*" >&2
    exit 1
}

load_expected() {
    top=$(git rev-parse --show-toplevel 2>/dev/null) || guard_fail "cannot locate this repository. Fail closed."
    file="$top/.githooks/identity"
    [ -f "$file" ] || guard_fail "identity file is missing ($file). Fail closed."
    expected_name=$(sed -n '1s/\r$//;1p' "$file")
    expected_email=$(sed -n '2s/\r$//;2p' "$file")
    [ -n "$expected_name" ] || guard_fail "identity file has no name. Fail closed."
    [ -n "$expected_email" ] || guard_fail "identity file has no email. Fail closed."
    case "$expected_email" in
        *@*) ;;
        *) guard_fail "identity file email is unusable. Fail closed." ;;
    esac
}

parse_name() {
    printf '%s\n' "$1" | sed -n 's/ <[^<>]*> [0-9][0-9]* [+-][0-9][0-9]*$//p'
}

parse_email() {
    printf '%s\n' "$1" | sed -n 's/.* <\([^<>]*\)> [0-9][0-9]* [+-][0-9][0-9]*$/\1/p'
}

check_var_ident() {
    role=$1
    raw=$2
    name=$(parse_name "$raw")
    email=$(parse_email "$raw")
    if [ -z "$name" ] || [ -z "$email" ]; then
        guard_fail "$role identity cannot be parsed. Fail closed."
    fi
    if [ "$name" != "$expected_name" ] || [ "$email" != "$expected_email" ]; then
        printf '%s\n' "amigent identity guard: $role is $name <$email>" >&2
        printf '%s\n' "  required: $expected_name <$expected_email>" >&2
        printf '%s\n' "  The commit was rejected. This hook does not rewrite the identity." >&2
        printf '%s\n' "  Repository-local user.name and user.email must be the required identity." >&2
        printf '%s\n' "  GIT_AUTHOR_* and GIT_COMMITTER_* override that configuration and are rejected here." >&2
        exit 1
    fi
}

check_commit_ident() {
    c=$1
    an=$(git log -1 --format='%an' "$c" 2>/dev/null) || guard_fail "cannot read the author of $c. Fail closed."
    ae=$(git log -1 --format='%ae' "$c" 2>/dev/null) || guard_fail "cannot read the author email of $c. Fail closed."
    cn=$(git log -1 --format='%cn' "$c" 2>/dev/null) || guard_fail "cannot read the committer of $c. Fail closed."
    ce=$(git log -1 --format='%ce' "$c" 2>/dev/null) || guard_fail "cannot read the committer email of $c. Fail closed."
    if [ -z "$an" ] || [ -z "$ae" ] || [ -z "$cn" ] || [ -z "$ce" ]; then
        guard_fail "commit $c has an empty author or committer. Fail closed."
    fi
    if [ "$an" != "$expected_name" ] || [ "$ae" != "$expected_email" ] || [ "$cn" != "$expected_name" ] || [ "$ce" != "$expected_email" ]; then
        printf '%s\n' "amigent identity guard: push rejected for $c" >&2
        printf '%s\n' "  author:    $an <$ae>" >&2
        printf '%s\n' "  committer: $cn <$ce>" >&2
        printf '%s\n' "  required:  $expected_name <$expected_email> for both" >&2
        printf '%s\n' "  This commit is not on origin and is not upstream history." >&2
        printf '%s\n' "  The hook does not rewrite it." >&2
        return 1
    fi
    return 0
}
