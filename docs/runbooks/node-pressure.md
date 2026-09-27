# Runbook: pods Pending with "Too many pods"

**Symptom**

```
0/N nodes are available: M Too many pods, K node(s) didn't satisfy plugin(s) [NodeAffinity].
```

**Cause:** each node is at its pod ceiling. `t3.small` allows 11. The usual
culprits are DaemonSets (Alloy, EFS CSI) plus the workloads themselves.

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
