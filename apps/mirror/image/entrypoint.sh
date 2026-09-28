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
apt-mirror
echo "=== apt-mirror sync done  $(date -u) ==="

du -sh "$BASE" 2>/dev/null || true

echo "Sync complete. Idling until the 10:00 UTC trigger rolls this pod."
exec sleep infinity
