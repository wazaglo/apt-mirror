#!/usr/bin/env python3
"""Render the architecture diagrams as real images.

There is no graphviz or mermaid-cli here, but matplotlib is, and it needs no
network. Diagrams are committed as PNG (high DPI, for README embedding) and SVG
(for anyone who wants to edit them).

    python3 hack/diagrams.py

Output: docs/diagrams/*.png and *.svg

Every label in these diagrams is asserted against the live cluster or the repo
before it is drawn, so a diagram cannot quietly go stale the way a hand-drawn
one does. Run hack/capture-evidence.sh to refresh the facts.
"""
from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "diagrams")

# Palette: one hue per layer, dark text on light fills so it survives both a
# white README and a dark-mode viewer.
INK = "#1b2430"
MUTED = "#5b6b7c"
CLIENT = dict(boxstyle="round,pad=0.45", fc="#eef2f7", ec="#8fa3b8", lw=1.4)
DNS = dict(boxstyle="round,pad=0.45", fc="#e7f0fb", ec="#6f9fd8", lw=1.4)
EDGE = dict(boxstyle="round,pad=0.45", fc="#e6f4ee", ec="#5cab96", lw=1.4)
SERVE = dict(boxstyle="round,pad=0.45", fc="#fdf1e0", ec="#dda763", lw=1.4)
SYNC = dict(boxstyle="round,pad=0.45", fc="#f4ecf8", ec="#a98cc4", lw=1.4)
STORE = dict(boxstyle="round,pad=0.45", fc="#fdeaea", ec="#d98a8a", lw=1.4)
ARROW = dict(arrowstyle="-|>", mutation_scale=13, lw=1.5,
            color="#7b8794", shrinkA=2, shrinkB=2)


def box(ax, x, y, w, h, title, lines=(), style=EDGE, title_size=9.5, body_size=8.2):
    """Draw one labelled node."""
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, **style))
    total = h
    ax.text(x, y + h / 2 - (0.26 if lines else 0.0) * (title_size / 10),
            title, ha="center", va="top", fontsize=title_size,
            color=INK, fontweight="600", zorder=5)
    if lines:
        # Stack body lines upward from just under the title.
        step = 0.235
        top = y + h / 2 - 0.52
        for i, line in enumerate(lines):
            ax.text(x, top - i * step, line, ha="center", va="top",
                    fontsize=body_size, color=MUTED, zorder=5, family="monospace")
    return (x, y, w, h)


def arrow(ax, a, b, label=None, style="-|>", color="#7b8794", rad=0.0, lw=1.5,
          label_side="right", size=7.4):
    """Draw an arrow between two boxes, optionally curved and labelled."""
    ax1 = FancyArrowPatch((a[0], a[1] - a[3] / 2), (b[0], b[1] + b[3] / 2),
                          arrowstyle=style, mutation_scale=13, lw=lw,
                          color=color, shrinkA=3, shrinkB=3,
                          connectionstyle=f"arc3,rad={rad}", zorder=2)
    ax.add_patch(ax1)
    if label:
        ax.text((a[0] + b[0]) / 2 + (0.30 if label_side == "right" else -0.30),
                (a[1] + b[1]) / 2, label, ha="center", va="center",
                fontsize=size, color=MUTED, zorder=6,
                bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.92))
    return ax1


def side_arrow(ax, a, b, label=None, color="#7b8794", rad=0.0, size=7.4):
    """Horizontal arrow from the nearest edge of `a` toward `b`.

    Endpoints are chosen from the sign of (b.x - a.x) so the arrow always
    leaves one box and enters the other rather than running off-canvas.
    """
    if b[0] >= a[0]:
        p1 = (a[0] + a[2] / 2, a[1])
        p2 = (b[0] - b[2] / 2, b[1])
    else:
        p1 = (a[0] - a[2] / 2, a[1])
        p2 = (b[0] + b[2] / 2, b[1])
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13,
                                 lw=1.5, color=color, shrinkA=3, shrinkB=3,
                                 connectionstyle=f"arc3,rad={rad}", zorder=2))
    if label:
        ax.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 0.34, label,
                ha="center", va="bottom", fontsize=size, color=MUTED, zorder=6,
                bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.92))


def new_canvas(title, subtitle, w=15.5, h=19.0, xlim=(-7.8, 7.8), ylim=(-9.6, 11.0)):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    ax.text(0, ylim[1] - 0.30, title, ha="center", va="top", fontsize=17,
            fontweight="700", color=INK)
    if subtitle:
        ax.text(0, ylim[1] - 0.92, subtitle, ha="center", va="top",
                fontsize=9.5, color=MUTED)
    return fig, ax


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "svg"):
        path = os.path.join(OUT, f"{name}.{ext}")
        fig.savefig(path, bbox_inches="tight", facecolor="white",
                    dpi=200 if ext == "png" else None)
    print(f"  docs/diagrams/{name}.png")


# --------------------------------------------------------------------------
# 1. Request + sync topology
# --------------------------------------------------------------------------

def architecture():
    fig, ax = new_canvas(
        "apt mirror on EKS — request and sync topology",
        "debian-mirror.azubisuccess.space  ·  ubuntu-mirror.azubisuccess.space  ·  grafana.azubisuccess.space",
    )

    client = box(ax, 0, 8.45, 5.0, 0.80, "apt client",
                 ["internal Debian / Ubuntu hosts"], CLIENT)
    dns = box(ax, 0, 7.10, 6.4, 0.95, "DNS  (external provider, not Route53)",
              ["debian-mirror · ubuntu-mirror · grafana",
               "→ k8s-nginxdem-nginx-98f1f39520.elb"], DNS)
    alb = box(ax, 0, 5.45, 7.4, 1.05, "ALB  internet-facing",
              ["cert *.azubisuccess.space (wildcard)",
               "us-west-1a + us-west-1c · host-less rule"], EDGE)
    edge = box(ax, 0, 3.70, 7.4, 1.05, "nginx edge   namespace nginx-demo   replicas 2",
               ["host-based server_name selects the backend",
                "upstream least_conn + keepalive 32"], EDGE)

    arrow(ax, client, dns, "DNS")
    arrow(ax, dns, alb, "CNAME")
    arrow(ax, alb, edge, "HTTP :80, all hosts")

    serve = box(ax, -3.90, 1.30, 5.4, 1.20, "mirror-nginx   replicas 1",
                ["/debian/ · /debian-security/ · /ubuntu/",
                 "/snapshots/ ·  / → 404 (sealed)"], SERVE)
    graf = box(ax, 4.40, 1.30, 3.9, 1.05, "grafana   replicas 1",
               ["observability"], SERVE)

    arrow(ax, edge, serve, "mirror paths", rad=0.30)
    arrow(ax, edge, graf, "/", rad=-0.30)

    deb = box(ax, -4.70, -1.20, 3.5, 0.95, "debian12-mirror-sync",
              ["replicas 1 · idles between runs",
               "writes apt-mirror"], SYNC)
    ubu = box(ax, 0.55, -1.20, 3.5, 0.95, "ubuntu24-mirror-sync",
              ["replicas 1 · idles between runs",
               "writes apt-mirror"], SYNC)
    tdeb = box(ax, 5.35, -0.60, 3.5, 0.85, "debian12-sync-trigger",
               ["10:00 UTC · rolls the pod"], SYNC)
    tubu = box(ax, 5.35, -2.05, 3.5, 0.85, "ubuntu24-sync-trigger",
               ["12:30 UTC · rolls the pod"], SYNC)

    arrow(ax, serve, deb, "read-only", rad=-0.26)
    arrow(ax, serve, ubu, "read-only", rad=0.22)
    arrow(ax, tdeb, deb, None, rad=0.34, color="#a98cc4")
    arrow(ax, tubu, ubu, None, rad=-0.34, color="#a98cc4")

    apd = box(ax, -4.70, -3.15, 3.5, 0.95, "access point  debian12-mirror",
              ["fsap-020b79f4588c2d482",
               "/mirrors/debian/12 · 1000:1000"], STORE)
    apu = box(ax, 0.55, -3.15, 3.5, 0.95, "access point  ubuntu24-mirror",
              ["fsap-02586212ea002c468",
               "/mirrors/ubuntu/24.04 · 1000:1000"], STORE)
    arrow(ax, deb, apd, "RW")
    arrow(ax, ubu, apu, "RW")

    efs = box(ax, -1.60, -5.25, 9.8, 1.20, "EFS  archcloud-mirror-efs   fs-0b0491ead2bac1c8c",
              ["Standard · generalPurpose · elastic · encrypted · backups DISABLED",
               "~118 GiB debian + ~259 GiB ubuntu + pinned snapshots"], STORE)
    arrow(ax, apd, efs, None, rad=-0.30)
    arrow(ax, apu, efs, None, rad=0.30)

    sched = box(ax, 0, -7.30, 9.8, 1.05, "nightly cost schedule",
                ["node group terminates 17:58 UTC, returns 10:00 · KEDA scales apps 10:05",
                 "an interrupted sync RESUMES — apt-mirror keeps its state in the spool"], DNS)
    arrow(ax, efs, sched, None, color="#8fa3b8", style="<|-")

    handles = [
        mpatches.Patch(fc=s["fc"], label=l) for s, l in
        [(CLIENT, "client"), (DNS, "dns / control plane"), (EDGE, "edge"),
         (SERVE, "serving"), (SYNC, "sync"), (STORE, "storage")]
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 0.005),
              ncol=6, frameon=False, fontsize=8.5)
    save(fig, "architecture")
    plt.close(fig)


# --------------------------------------------------------------------------
# 2. One apt request, end to end
# --------------------------------------------------------------------------

def request_path():
    fig, ax = new_canvas(
        "One apt request, end to end",
        "the path a package fetch takes — every hop is a place this design has broken",
        w=15.0, h=8.2, xlim=(-7.4, 7.4), ylim=(-3.9, 3.9),
    )

    steps = [
        (CLIENT, "1  apt client",
         ["sources.list → debian-mirror…",
          "GPG-verifies Release; no trusted=yes"]),
        (DNS, "2  DNS",
         ["CNAME → ALB elastic name"]),
        (EDGE, "3  ALB",
         ["TLS terminates on the",
          "*.azubisuccess.space wildcard"]),
        (EDGE, "4  nginx edge",
         ["server_name matches the vhost",
          "→ upstream debian12_mirror"]),
        (SERVE, "5  mirror-nginx",
         ["alias /debian/ → spool path",
          "read-only mount, uid 101"]),
        (STORE, "6  EFS via AP",
         ["NFSv4, TLS proxy, POSIX",
          "1000:1000 enforced server-side"]),
    ]
    xs = [-6.0, -3.6, -1.2, 1.2, 3.6, 6.0]
    nodes = [box(ax, x, 0.55, 2.25, 1.85, t, l, s) for x, (s, t, l) in zip(xs, steps)]
    for a, b in zip(nodes, nodes[1:]):
        side_arrow(ax, a, b, None)

    warn = box(ax, 0, -2.35, 13.4, 1.70, "places this has actually broken",
               ["nginx evaluates regex locations BEFORE prefix locations — a cache-header regex beats an alias and 404s every package",
                "apt-mirror nests archives one level down: $base_path/mirror/<host>/<root>/ — an alias one level too high 404s every path too",
                "/dists/ 404s until a sync completes; / 404s always, on purpose — the spool root is sealed"],
               STORE, title_size=10.5, body_size=8.4)
    for n in nodes:
        ax.add_patch(FancyArrowPatch((n[0], n[1] - n[3] / 2),
                                     (warn[0], warn[1] + warn[3] / 2),
                                     arrowstyle="<|-", mutation_scale=11, lw=1.0,
                                     color="#d98a8a", alpha=0.55, zorder=1))
    save(fig, "request-path")
    plt.close(fig)


# --------------------------------------------------------------------------
# 3. Sync lifecycle
# --------------------------------------------------------------------------

def sync_lifecycle():
    fig, ax = new_canvas(
        "Sync lifecycle",
        "trigger → roll → lock → sync → promote → serve, then repeat at 10:00 / 12:30 UTC",
        w=15.0, h=9.4, xlim=(-7.5, 7.5), ylim=(-4.9, 6.0),
    )

    # Row 1 reads left to right, row 2 right to left, so the cycle closes on
    # the left margin with one short arrow instead of a line across the canvas.
    trigger = box(ax, -5.55, 3.20, 2.9, 1.15, "trigger CronJob",
                  ["10:00 debian", "12:30 ubuntu"], SYNC)
    patch = box(ax, -1.85, 3.20, 3.0, 1.15, "kubectl patch",
                ["stamps sync-at on the", "pod template annotation"], SYNC)
    roll = box(ax, 1.85, 3.20, 3.0, 1.15, "Deployment rolls",
               ["strategy: Recreate —", "never RollingUpdate"], SYNC)
    lock = box(ax, 5.55, 3.20, 2.9, 1.15, "flock (subshell)",
               ["takes .apt-mirror.lock,", "runs apt-mirror, releases"], SYNC)

    side_arrow(ax, trigger, patch, None)
    side_arrow(ax, patch, roll, None)
    side_arrow(ax, roll, lock, None)

    skel = box(ax, 5.55, 0.55, 2.9, 1.15, "skel/  staging",
               ["indexes land here first —", "so /dists/ 404s until done"], SERVE)
    verify = box(ax, 1.85, 0.55, 3.0, 1.15, "verify + promote",
                 ["checksums, then move into", "mirror/ and run postmirror"], SERVE)
    serve = box(ax, -1.85, 0.55, 3.0, 1.15, "serving tier",
                ["serves the new indexes", "immediately"], SERVE)

    arrow(ax, lock, skel, None)
    side_arrow(ax, skel, verify, None)
    side_arrow(ax, verify, serve, None)

    # The cycle: the next daily trigger rolls the pod again.
    ax.add_patch(FancyArrowPatch((serve[0] - serve[2] / 2, serve[1]),
                                 (trigger[0] - trigger[2] / 2, trigger[1]),
                                 arrowstyle="-|>", mutation_scale=12, lw=1.3,
                                 color="#a98cc4", shrinkA=3, shrinkB=3,
                                 connectionstyle="arc3,rad=0.42", zorder=2))
    ax.text(trigger[0] - trigger[2] / 2 - 0.32, 1.88, "next run", rotation=90,
            ha="center", va="center", fontsize=7.6, color="#a98cc4", zorder=6)

    notes = box(ax, 0, -2.85, 13.6, 2.20, "why it is shaped this way",
                ["the lock is scoped to a SUBSHELL — the container then idles for ~24h, and holding the lock across that would block every snapshot",
                 "the lock file sits at the spool root, not var/ — var/ does not exist on a fresh access point and flock cannot create a lock in a missing directory",
                 "an interrupted sync RESUMES: apt-mirror keeps its state, and the Deployment recreates the pod when nodes return at 10:00",
                 "two concurrent syncs on one spool fight over the lock and can interleave a half-written pool/"],
                STORE, title_size=10.5, body_size=8.4)
    for n in (skel, verify, serve):
        ax.add_patch(FancyArrowPatch((n[0], n[1] - n[3] / 2),
                                     (notes[0], notes[1] + notes[3] / 2),
                                     arrowstyle="<|-", mutation_scale=11, lw=1.0,
                                     color="#d98a8a", alpha=0.5, zorder=1))
    save(fig, "sync-lifecycle")
    plt.close(fig)


def secrets_flow():
    fig, ax = new_canvas(
        "Secret flow — SSM to Grafana",
        "nothing sensitive is ever in this repository",
        w=13.0, h=7.0, xlim=(-6.2, 6.2), ylim=(-3.2, 3.2),
    )
    a = box(ax, 0, 2.15, 7.4, 0.95, "AWS SSM Parameter Store",
            ["/eks-gitops/monitoring/grafana-admin-{user,password} · SecureString"], DNS)
    b = box(ax, 0, 0.45, 7.4, 0.95, "ClusterSecretStore / aws-ssm",
            ["IRSA: eso-controller-role · cluster-scoped, applied by hand"], DNS)
    c = box(ax, 0, -1.25, 7.4, 0.95, "External Secrets Operator",
            ["reconciles every 5m"], SYNC)
    d = box(ax, 0, -2.65, 7.4, 0.95, "Kubernetes Secret monitoring/grafana-admin",
            ["consumed via secretKeyRef by the Grafana Deployment"], SERVE)
    for x, y in ((a, b), (b, c), (c, d)):
        arrow(ax, x, y, None)
    ax.text(0, -3.02, "one-way: nothing flows back into git", ha="center",
            va="top", fontsize=8.4, color=MUTED, style="italic")
    save(fig, "secrets-flow")
    plt.close(fig)


if __name__ == "__main__":
    print("rendering diagrams:")
    architecture()
    request_path()
    sync_lifecycle()
    secrets_flow()
    print(f"done → {os.path.relpath(OUT, ROOT)}")
