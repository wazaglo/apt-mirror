#!/bin/bash
# Runs from apt-mirror after a successful sync (run_postmirror 1).
# Prune translation bloat only. dep11/CNF are kept on purpose: Debian apt
# clients expect them and their absence is a visible regression.
set -e
find /var/spool/apt-mirror/mirror -name "Translation-*" -delete 2>/dev/null || true
