FROM debian:12-slim

# debian-archive-keyring carries the bookworm + bookworm-security signing keys
# apt-mirror verifies Release/InRelease against. Without it apt-mirror fails
# with "Can't check signature: No public key" on every dist.
# xz-utils: bookworm Release files are .xz — apt-mirror cannot unpack them
# without it.
RUN apt-get update && apt-get install -y --no-install-recommends \
      apt-mirror \
      debian-archive-keyring \
      ca-certificates \
      xz-utils \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Single sync then exit. The CronJob owns the schedule — an entrypoint that
# loops forever would make the Job never complete, and with
# concurrencyPolicy: Forbid that deadlocks every later run.
ENTRYPOINT ["/entrypoint.sh"]
