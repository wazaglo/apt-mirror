# 0002 — Alloy replaces node-exporter

**Status:** accepted

## Context

We needed per-node container logs (→ Loki) and node hardware metrics
(→ Prometheus). The conventional pairing is Fluent Bit/Alloy for logs plus a
separate node-exporter DaemonSet for metrics — two node agents, two RBAC
bundles, two config surfaces.

## Decision

Run **one** agent: the Grafana Alloy DaemonSet, with

- `discovery.kubernetes` + `loki.source.kubernetes` → `loki.write` (logs), and
- `prometheus.exporter.unix` (the same collectors node-exporter runs) →
  `prometheus.scrape` → `prometheus.remote_write`.

The node-exporter DaemonSet was deleted.

## Consequences

- One DaemonSet, one image, one RBAC object.
- Node metrics require `--web.enable-remote-write-receiver` on Prometheus
  (they are pushed, not scraped) — a real difference from node-exporter that
  surprises anyone expecting a `node-exporter` scrape job.
- Fewer pod slots consumed on 11-pod nodes; that mattered here.
- Fargate remains impossible either way (no DaemonSets, no hostPath), so this
  is a consolidation, not a portability gain.
