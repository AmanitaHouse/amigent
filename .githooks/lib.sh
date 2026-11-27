#!/bin/sh
# Shared checks for the AmiGent identity guard.
# Fail closed. Never rewrite an identity.
# The identity file and the upstream baseline sit beside the hook that sourced
# this script: either the private hooks directory or the tracked .githooks source.

guard_fail() {
    printf '%s\n' "amigent identity guard: $*" >&2
    exit 1
}

resolve_hook_dir() {
    script=$(printf '%s' "$0" | tr '\\' '/' | tr -d '\r')
    case "$script" in
        /*|[A-Za-z]:*) ;;
        *) script=$(pwd)/$script ;;
    esac
    dir=$(dirname "$script")
    if [ -f "$dir/identity" ] && [ -f "$dir/upstream-baseline" ]; then
        printf '%s\n' "$dir"
        return 0
    fi
    alt=$(git rev-parse --path-format=absolute --git-path hooks 2>/dev/null) \
        || alt=$(git rev-parse --git-path hooks 2>/dev/null) \
        || return 1
    if [ -f "$alt/identity" ] && [ -f "$alt/upstream-baseline" ]; then
        printf '%s\n' "$alt"
        return 0
    fi
    return 1
}

load_expected() {
    dir=$(resolve_hook_dir) || guard_fail "cannot locate the installed identity file. Fail closed."
    file="$dir/identity"
    expected_name=$(sed -n '1s/\r$//;1p' "$file")
    expected_email=$(sed -n '2s/\r$//;2p' "$file")
    [ -n "$expected_name" ] || guard_fail "identity file has no name. Fail closed."
    [ -n "$expected_email" ] || guard_fail "identity file has no email. Fail closed."
    case "$expected_email" in
        *@*) ;;
        *) guard_fail "identity file email is unusable. Fail closed." ;;
    esac
}

load_verified_upstream() {
    dir=$(resolve_hook_dir) || guard_fail "cannot locate the upstream baseline. Fail closed."
    file="$dir/upstream-baseline"
    baseline_ref=$(sed -n '1s/\r$//;1p' "$file")
    baseline_tag=$(sed -n '2s/\r$//;2p' "$file")
    baseline_commit=$(sed -n '3s/\r$//;3p' "$file")
    # These are the verified objects, not a pattern a new tag can satisfy.
    [ "$baseline_ref" = "refs/tags/upstream-v1.4.0" ] \
        || guard_fail "upstream baseline ref is not the verified tag. Fail closed."
    [ "$baseline_tag" = "3c7cec6ac6c9bacf5bc2c4d4dc70606289c2f971" ] \
        || guard_fail "upstream baseline tag id is not the verified object. Fail closed."
    [ "$baseline_commit" = "4fea38f602f84ddad2d5215fbc9d2742605d892c" ] \
        || guard_fail "upstream baseline commit is not the verified commit. Fail closed."
    actual_tag=$(git rev-parse --verify --quiet "$baseline_ref") \
        || guard_fail "verified upstream tag $baseline_ref is missing. Fail closed."
    actual_type=$(git cat-file -t "$baseline_ref" 2>/dev/null) \
        || guard_fail "cannot read verified upstream tag. Fail closed."
    actual_commit=$(git rev-parse --verify --quiet "${baseline_ref}^{commit}") \
        || guard_fail "cannot peel verified upstream tag. Fail closed."
    [ "$actual_type" = "tag" ] \
        || guard_fail "verified upstream ref is not an annotated tag. Fail closed."
    [ "$actual_tag" = "$baseline_tag" ] \
        || guard_fail "upstream tag does not match the verified tag object. Fail closed."
    [ "$actual_commit" = "$baseline_commit" ] \
        || guard_fail "upstream tag does not point at the verified commit. Fail closed."
    # The reviewed upstream main boundaries, as exact commit ids, oldest first. Each one
    # is a point on one line of upstream history that was reviewed and is already in the
    # fork. Everything reachable from a boundary is exempt; nothing else is. Never a
    # ref name, never a pattern. A later boundary (for example one that covers upstream
    # PR #50) is added only by a deliberate reconciliation: one more id here and in the file.
    #   f6aab1d4  tracked boundary before PR #22
    #   8e576ad9  boundary the installed hook trusted before PR #22
    #   dfd08619  upstream PRs #46 and #52, merged into the fork by PR #22
    trusted_boundaries="f6aab1d4953c1d83be2f71e73faef6fa5dc236ff 8e576ad94d8c936a662dfd7375c31456341f49fd dfd086194c918cd91f91626072d20ec6e605d1bf"
    line=3
    previous=$baseline_commit
    for boundary in $trusted_boundaries; do
        line=$((line + 1))
        listed=$(sed -n "${line}p" "$file" | tr -d '\r')
        [ "$listed" = "$boundary" ] \
            || guard_fail "upstream baseline line $line is not the verified boundary $boundary. Fail closed."
        resolved=$(git rev-parse --verify --quiet "${boundary}^{commit}") \
            || guard_fail "verified upstream boundary $boundary is missing. Fail closed."
        [ "$resolved" = "$boundary" ] \
            || guard_fail "verified upstream boundary $boundary does not resolve to itself. Fail closed."
        git merge-base --is-ancestor "$previous" "$boundary" \
            || guard_fail "verified upstream boundary $boundary does not descend from $previous. Fail closed."
        previous=$boundary
    done
    # Nothing beyond the verified boundaries may be listed.
    extra=$(sed -n "$((line + 1)),\$p" "$file" | tr -d '\r\n \t')
    [ -z "$extra" ] \
        || guard_fail "upstream baseline lists a commit that is not a verified boundary. Fail closed."
    verified_upstream=$baseline_commit
    verified_upstream_main=$previous
    verified_upstream_boundaries=$trusted_boundaries
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
    # Read the commit object header. git log can apply a mailmap and hide the stored identity.
    raw=$(git cat-file commit "$c" 2>/dev/null) || guard_fail "cannot read commit $c. Fail closed."
    header=$(printf '%s\n' "$raw" | awk 'NF==0 {exit} {print}')
    author_line=$(printf '%s\n' "$header" | sed -n 's/^author //p' | head -n 1)
    committer_line=$(printf '%s\n' "$header" | sed -n 's/^committer //p' | head -n 1)
    an=$(parse_name "$author_line")
    ae=$(parse_email "$author_line")
    cn=$(parse_name "$committer_line")
    ce=$(parse_email "$committer_line")
    if [ -z "$an" ] || [ -z "$ae" ] || [ -z "$cn" ] || [ -z "$ce" ]; then
        guard_fail "commit $c has an empty or unreadable author or committer. Fail closed."
    fi
    if [ "$an" != "$expected_name" ] || [ "$ae" != "$expected_email" ] || [ "$cn" != "$expected_name" ] || [ "$ce" != "$expected_email" ]; then
        printf '%s\n' "amigent identity guard: push rejected for $c" >&2
        printf '%s\n' "  author:    $an <$ae>" >&2
        printf '%s\n' "  committer: $cn <$ce>" >&2
        printf '%s\n' "  required:  $expected_name <$expected_email> for both" >&2
        printf '%s\n' "  This commit is not on origin and is not the verified upstream history." >&2
        printf '%s\n' "  The hook does not rewrite it." >&2
        return 1
    fi
    return 0
}
