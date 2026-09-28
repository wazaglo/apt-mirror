# 0006 — Hardlink snapshots of the mirror spool

**Status:** accepted

## Context

A mirror that syncs nightly is only useful for patch management if clients can
be pinned to a *known-good* package set — a state that is later known-good and
whose files then change underneath them. That needs a point-in-time copy of the
archive, retained for a while, served over the same endpoint.

## Decision

Snapshot with `cp -al` (archive + hardlink) into `snapshots/<timestamp>/` on
the same EFS volume, prune to the newest 3, and serve under
`/snapshots/<name>/…`. A `flock` serialises snapshots against running syncs.

## Why hardlinks and not a copy

EFS supports hardlinks over NFSv4, so `cp -al` costs **no additional bytes** —
a 127 GB apparent snapshot added 0 bytes to the filesystem. Verified by inode,
not by inference: a file in both trees reports the same inode with `links=2`.

It is not free, though. `cp -al` walks ~67k inodes and EFS metadata operations
are single-digit milliseconds, so a snapshot takes **~22 minutes**. The data
transfer is not the cost; the metadata is.

A real copy at 127 GB would also have doubled a bill that is already the
largest line item on this cluster.

## Consequences

- **Snapshots pin space permanently.** Deleting one only decrements link
  counts; the bytes are freed only once *both* the snapshot and the live mirror
  have moved past that file. Each retained snapshot therefore pins whatever
  subsequent syncs replaced. Bounded, not free — hence pruning to 3.
- **Layout is deliberately flattened** to `<name>/{debian,debian-security}`
  rather than mirroring the spool's `mirror/<host>/<root>/`. Copying the spool
  layout would force client URLs to
  `/snapshots/<name>/deb.debian.org/debian/…`; flattening gives
  `/snapshots/<name>/debian/…` and lets the whole tree be served by a single
  nginx `alias` with no regex and no rewrite.
- **Pruning is guarded by a name pattern.** Only `^[0-9]{8}-[0-9]{6}Z$` may ever
  be deleted. That is the rail preventing a bug here from removing `LATEST`, or
  the live mirror.
- **A snapshot can capture a torn tree** if `cp -al` walks the pool while
  apt-mirror is writing. The `flock` is what prevents that; a cron time alone
  would only reduce the window. A snapshot that cannot get the lock within its
  wait **skips** and exits non-zero rather than proceeding.
- The lock is shared with the sync, which is why the sync's lock is scoped to a
  subshell around `apt-mirror` only — see [the mirror guide](../mirror.md).
- Snapshots currently cover Debian only. Ubuntu's spool is a separate
  filesystem, and one nginx `alias` cannot span two roots, so serving both
  under a single `/snapshots/` prefix needs a different URL scheme. Doing it
  with a regex location would risk the location-precedence trap documented in
  the mirror guide, so it is deferred until that is designed.
