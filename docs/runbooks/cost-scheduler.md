# Nightly cost schedule

Compute is turned off every night and brought back in the morning. Two
independent mechanisms, deliberately separated:

| What | Mechanism | Where |
|---|---|---|
| Scale app workloads to 0 | KEDA cron ScaledObjects | `apps/*/base/scaledobjects.yaml`, `infra/keda/scaledobjects-infra.yaml` |
| Terminate / launch EC2 nodes | Lambda + EventBridge | `infra/scheduler/` |

They are separate on purpose: KEDA owns what runs on the cluster, the Lambda
owns the node group, and the Lambda needs no Kubernetes credentials at all.

## The schedule (all times UTC — GMT has no DST, so no DST bugs)

| UTC | What happens |
|---|---|
| 10:00 | Lambda sets the node group to min=5, desired=5. Nodes boot and join (~3 min). |
| 10:05 | KEDA cron windows open. Apps scale up. |
| 17:54 | KEDA cron windows close. Apps scale to 0 and drain. |
| 17:58 | Lambda sets the node group to min=0, desired=0. Nodes terminate. |
| 17:58 → 10:00 | No nodes. `grafana.azubisuccess.space` returns 502 from the ALB. |

The 4-minute gap between 17:54 and 17:58 is deliberate: pods must finish
draining, and Prometheus must close its WAL on EFS (NFS is slower than local
disk) or it replays the WAL on the next boot.

## How the KEDA pattern works

Each ScaledObject has exactly **one** cron trigger, defining the work window:

```yaml
minReplicaCount: 0
maxReplicaCount: 2
triggers:
  - type: cron
    metadata:
      timezone: Etc/UTC
      start: "5 10 * * *"
      end: "54 17 * * *"
      desiredReplicas: "2"
```

Outside the window **no trigger is active**, so KEDA scales to
`minReplicaCount` (0). That is what makes the overnight wrap work: a cron window
cannot wrap midnight (KEDA rejects `end` < `start`), but "no active trigger" has
no such limit.

**Do not add a second trigger for the off period.** It reintroduces the
midnight-wrap problem and makes the morning gap ambiguous.

## What is scheduled, and what is deliberately not

Scheduled (ScaledObject, scales to 0 overnight):

- `monitoring`: grafana, prometheus, loki, blackbox
- `nginx-demo`: nginx
- `kube-system`: aws-load-balancer-controller
- `external-secrets`: external-secrets, -cert-controller, -webhook
- `external-dns`: external-dns

**Not** scheduled, on purpose:

| Component | Why |
|---|---|
| `efs-csi-controller`, `efs-csi-node` | must be up to remount EFS when pods return |
| `alloy` (DaemonSet) | dies with the nodes, returns with them — nothing to schedule |
| `coredns`, `kube-proxy`, `aws-node`, `eks-pod-identity-agent`, `dcgm-server` | cluster plumbing |
| KEDA operator + metrics-apiserver | is the thing doing the scheduling |

## What survives the night

| State | Survives? | How |
|---|---|---|
| Grafana dashboards, users, SQLite DB | yes | EFS (`fsap-088c8c16707025698`) |
| Prometheus TSDB | yes | EFS (`fsap-012a38be930c8a207`, POSIX 1000:1000) |
| Loki logs | yes | S3 `azubi-logs` |
| ALB + ACM cert + DNS | yes | AWS-managed, independent of the cluster |
| Metrics/logs during 17:58–10:00 | no | nothing is running to collect them |
| Node identity (instance IDs) | no | nodes are terminated, not stopped — new nodes every morning |

## Verifying it works

```bash
# ScaledObjects present and Ready
kubectl get scaledobject -A

# KEDA's view of the current window
kubectl describe scaledobject -n nginx-demo nginx-schedule | tail -20

# Node group capacity
aws eks describe-nodegroup --cluster-name eks-lab --nodegroup-name ng-eks \
  --query 'nodegroup.{status:status,scaling:scalingConfig}'

# Force a scale-down without waiting for 17:54 (KEDA reconciles in ~60s)
kubectl patch scaledobject -n monitoring prometheus-schedule \
  --type merge -p '{"spec":{"minReplicaCount":0}}'
```

To test the node half (this really does terminate the nodes):

```bash
aws lambda invoke --function-name eks-node-scheduler \
  --payload '{"detail":{"action":"off"}}' --cli-binary-format raw-in-base64-out /dev/stdout
# ...then bring them back:
aws lambda invoke --function-name eks-node-scheduler \
  --payload '{"detail":{"action":"on"}}' --cli-binary-format raw-in-base64-out /dev/stdout
```

## Manual override

Work outside 10:00–17:54? Bring the cluster up:

```bash
aws lambda invoke --function-name eks-node-scheduler \
  --payload '{"detail":{"action":"on"}}' --cli-binary-format raw-in-base64-out /dev/stdout
```

KEDA will still hold the apps at 0 until 10:05, because the cron window is
closed. To force the apps up too, patch `minReplicaCount` and the trigger:

```bash
kubectl patch scaledobject -n monitoring grafana-schedule --type merge \
  -p '{"spec":{"minReplicaCount":2}}'
```

Doing this **overrides the schedule for that day** — KEDA will scale back to 0
at the next window boundary it evaluates. To make the override stick, edit the
ScaledObjects in git and merge (which is the better answer anyway).

## Did it actually fire?

**Check this first whenever the schedule seems not to have run.** The node half
fails *silently* — a misconfigured EventBridge target produces no Lambda logs at
all, and nothing alerts on it. The KEDA half is independent, so apps scale to 0
while the nodes keep billing, which looks like a partial success.

```bash
# 1. Did the rule fire, and did it succeed?
aws cloudwatch get-metric-statistics --namespace AWS/Events \
  --metric-name Invocations --dimensions Name=RuleName,Value=eks-nodes-off \
  --start-time "$(date -u -d '1 hour ago' +%FT%TZ)" --end-time "$(date -u +%FT%TZ)" \
  --period 3600 --statistics Sum
aws cloudwatch get-metric-statistics --namespace AWS/Events \
  --metric-name FailedInvocations --dimensions Name=RuleName,Value=eks-nodes-off \
  --start-time "$(date -u -d '1 hour ago' +%FT%TZ)" --end-time "$(date -u +%FT%TZ)" \
  --period 3600 --statistics Sum

# 2. Did the function actually run? (empty logs = never invoked)
aws logs tail /aws/lambda/eks-node-scheduler --since 12h --format short

# 3. Ground truth
aws eks describe-nodegroup --cluster-name eks-lab --nodegroup-name ng-eks \
  --query 'nodegroup.scalingConfig'
```

Reading the result:

| Invocations | FailedInvocations | Lambda logs | Meaning |
|---|---|---|---|
| 0 | 0 | empty | rule never fired (disabled, or schedule not reached) |
| ≥1 | ≥1 | empty | **EventBridge could not invoke the function** |
| ≥1 | 0 | present | it ran |

### IAM: two roles, on purpose

EventBridge targets a Lambda through a role, and **that role's trust policy
needs `events.amazonaws.com`** — not just `lambda.amazonaws.com`. Getting this
wrong is silent: the rule fires, the invocation is rejected, and the only
evidence is `FailedInvocations`.

| Role | Trusts | Grants |
|---|---|---|
| `eks-node-scheduler-role` | `lambda.amazonaws.com` | the function's own permissions (EKS nodegroup resize) |
| `eks-node-scheduler-invoke` | `events.amazonaws.com` | `lambda:InvokeFunction` on the scheduler function only |

EventBridge must never be able to assume the execution role — that role can
resize the node group, and the scheduler service has no reason to hold that.

Verify the wiring is still intact after any change here:

```bash
aws events list-targets-by-rule --rule eks-nodes-off \
  --query 'Targets[].[Arn,RoleArn,Input]'
aws iam get-role --role-name eks-node-scheduler-invoke \
  --query 'Role.AssumeRolePolicyDocument.Statement[].Principal'
```

If you ever need to prove the EventBridge→Lambda path without disturbing the
real schedule, temporarily re-arm the rule a few minutes out and watch the logs:

```bash
# harmless: "on" while the nodes are already up is a no-op
aws events put-rule --name eks-nodes-on \
  --schedule-expression "cron(<min> <hour> <day> <month> ? *)"
aws logs tail /aws/lambda/eks-node-scheduler --follow
# then restore
aws events put-rule --name eks-nodes-on --schedule-expression "cron(0 10 * * ? *)"
```


## Deploying during off-hours

`deploy.yml` detects the window and **still applies** the manifests, because the
EKS control plane is AWS-managed and stays up — skipping the apply would let git
and the cluster silently diverge. It skips only the rollout wait, which would
otherwise hang with no nodes to schedule onto. You'll see a warning annotation
on the run; workloads come up on their own at 10:05.

## Troubleshooting

**Apps at 0 during work hours.**
Check the window, not the cluster: `kubectl describe scaledobject -n monitoring
grafana-schedule`. Confirm `timezone: Etc/UTC` and that the current UTC time is
inside `start`..`end`. Note `date -u` vs local time — a laptop in CET is one hour
off and will make this look broken when it isn't.

**KEDA not scaling at all.**
`kubectl get pods -n keda` — if the operator is crashlooping, nothing is
evaluated. `kubectl logs -n keda deploy/keda-operator --tail=50`.

**`AccessDeniedException` from the scheduler Lambda.**
This account intermittently denies the first `eks:UpdateNodegroupConfig` after
an IAM policy change, while the policy propagates. The function retries with
backoff (0/5/15/30/60/120s) and only fails after all attempts. If it persists,
the role's policy is wrong — check with
`iam simulate-principal-policy --policy-source-arn <role-arn> --action-names eks:UpdateNodegroupConfig`.
New IAM changes can take a couple of minutes to take effect at all; wait before
concluding it is broken.

**Nothing happened at 17:58 and there are no Lambda logs.**
Not a KEDA or EKS problem — EventBridge could not invoke the function. Work
through "Did it actually fire?" above; in practice this is the target's
`RoleArn` trust policy missing `events.amazonaws.com`.

**The Lambda logs `did not settle within 900s` after a scale-off.**
Instances linger in `Terminating:Wait/Proceed` for minutes after being removed
from the target capacity, so the function waits for them to disappear from the
ASG before reporting success. The resize itself already succeeded — check
`describe-nodegroup` for the real state, and treat the warning as cosmetic.


**`ResourceInUseException`.**
A previous node group update has not settled. The function retries; manually,
wait for `nodegroup.status == ACTIVE` before retrying.

**Nodes came back but the site 502s.**
Expected for a few minutes: the ALB target group needs the ALB controller
running and the pods Ready. `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller`.

**Everything is up but Prometheus has a gap.**
Correct behaviour: nothing collects metrics while the nodes are gone. Data either
side of the window is intact on EFS.

## Changing the schedule

Edit both, or you will get a half-applied change:

1. The cron `start`/`end` in the ScaledObjects (`apps/*/base/scaledobjects.yaml`,
   `infra/keda/scaledobjects-infra.yaml`).
2. The `cron(...)` expressions on `eks-nodes-off` / `eks-nodes-on`
   (`aws events describe-rule --name eks-nodes-off`).

Then re-apply the infra ScaledObjects manually if you changed
`infra/keda/scaledobjects-infra.yaml`, and push so CI applies the app ones.
