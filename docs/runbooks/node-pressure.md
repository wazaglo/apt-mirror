# Runbook: pods Pending with "Too many pods"

**Symptom**

```
0/N nodes are available: M Too many pods, K node(s) didn't satisfy plugin(s) [NodeAffinity].
```

**Cause:** the cluster has **one free pod slot**. 5 nodes x 11 = 55 allocatable,
and 54 are in use. This is the normal state, not an accident, and it is why:

| constraint | value |
|---|---|
| mirror serving tier | `replicas: 1` — a 2nd replica has never scheduled |
| Grafana | 1 replica (also correct: one SQLite writer) |
| prometheus / loki / blackbox | `maxSurge: 0`, so a rollout needs no spare pod |
| sync containers | one per distro, and they are permanent — they idle holding the EFS mount |

**Check the number before adding any pod:**

```bash
kubectl get pods -A --no-headers | grep -vcE 'Completed|Error'   # keep under 55
```

A DaemonSet adding pods is the usual surprise: Alloy and the EFS CSI node
plugin consume one slot per node each, so the ceiling is per-node, not
cluster-wide.

**Diagnose**

```bash
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{" allocatable.pods="}{.status.allocatable.pods}{"\n"}{end}'
kubectl get pods -A -o wide --no-headers | awk '{print $8}' | sort | uniq -c
kubectl -n <ns> describe pod <pod> | tail -5
```

**Fix 1 — scale out (normal path)**

```bash
aws eks update-nodegroup-config --region us-west-1 --cluster-name eks-lab \
  --nodegroup-name ng-eks --scaling-config minSize=2,maxSize=5,desiredSize=5
```

Note: `t3.medium` will **not** launch on this account (Free Tier
restriction — the ASG reports "not eligible for Free Tier"). Node count is
the only lever.

**Fix 2 — free a pinned slot (when a DaemonSet pod is the blocker)**

A DaemonSet pod is bound to one node. If that node is full, the pod stays
`Pending` forever while other nodes have space, because its `nodeAffinity`
came from the (now terminated) old pod template. Bounce a movable replica to
shed one pod from the full node:

```bash
kubectl -n kube-system delete pod <some-replica-on-the-full-node>   # e.g. a coredns
```

The replacement may land anywhere; the stuck DaemonSet pod then schedules.

**Prevent:** install Karpenter (automatic provisioning + consolidation), or
raise the node count headroom and watch `allocatable.pods`.
