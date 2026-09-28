#!/bin/bash
# One apt-mirror sync, then idle.
#
# The schedule is NOT here. It lives in the CronJob
# (apps/mirror/cronjob-debian12-sync-trigger.yaml) which rolls this pod at
# 10:00 UTC by patching the sync-at annotation on the sync Deployment, and a
# pod restart is what re-enters this script. Idling rather than exiting is
# what keeps the EFS mount warm between runs; exiting would make the Deployment
# restart the pod in a tight loop and re-pull the mount nightly for nothing.
set -euo pipefail

BASE=/var/spool/apt-mirror

# A fresh EFS access point is an empty tree, so lay down the spool skeleton.
# apt-mirror needs $base_path/var to exist because mirror.list pins
# postmirror_script to a path under it. The docker-compose version never needed
# this: it inherited a pre-populated host mount.
mkdir -p "$BASE"/{mirror,skel,var,snapshots}

# mirror.list references $base_path/var/postmirror.sh by exact path, so it must
# exist before apt-mirror starts or the postmirror step aborts the run.
install -m0755 /conf/postmirror.sh "$BASE/var/postmirror.sh"

install -m0644 /conf/mirror.list /etc/apt/mirror.list
install -m0644 /conf/apt.conf    /etc/apt/apt.conf.d/99custom

echo "=== apt-mirror sync start $(date -u) ==="

# Serialise against snapshot jobs via a shared lock on the spool.
#
# The lock is scoped to a SUBSHELL on purpose. This container then idles for
# ~24h until the 10:00 UTC trigger rolls the pod, and holding the lock across
# that idle period would block every snapshot indefinitely. A subshell takes
# the lock, runs apt-mirror, and releases on exit.
#
# The lock lives at the spool root, not in var/, because var/ does not exist on
# a fresh access point and flock cannot create a lock file in a missing
# directory. Verified working over this EFS NFSv4 mount (acquire, block,
# release) rather than assumed.
(
  flock -x 9
  apt-mirror
) 9>"$BASE/.apt-mirror.lock"

echo "=== apt-mirror sync done  $(date -u) ==="

du -sh "$BASE" 2>/dev/null || true

echo "Sync complete. Idling until the 10:00 UTC trigger rolls this pod."
exec sleep infinity
