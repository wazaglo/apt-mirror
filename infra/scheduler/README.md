# Node group scheduler — AWS setup

Everything here is created **manually** (no Terraform state for this account yet).
Re-apply with the commands below after `terraform import`.

Two IAM roles, deliberately separate:

| Role | File | Trusts | Purpose |
|---|---|---|---|
| `eks-node-scheduler-role` | `iam-policy.json` | `lambda.amazonaws.com` | the function's own permissions: resize the node group |
| `eks-node-scheduler-invoke` | `invoke-policy.json` + `invoke-trust-policy.json` | `events.amazonaws.com` | lets EventBridge invoke the function, nothing else |

**Why the split matters.** An EventBridge target invokes a Lambda by assuming the
role named in its `RoleArn`. If you point that at the execution role, EventBridge
needs to be able to assume a role that can resize the node group — so a
misconfigured rule could do far more than fire a schedule. The invoke role holds
`lambda:InvokeFunction` on one function and nothing else.

**The failure mode this exists to prevent:** if the invoke role's trust policy
omits `events.amazonaws.com`, the rule still fires, the invocation is rejected,
and the only symptom is `FailedInvocations > 0` with no Lambda logs. That
happened on 2026-09-27 and left the nodes running all night. See
[docs/mirror.md](../../docs/mirror.md) → scheduling.

## Apply

```bash
# 1. Function execution role
aws iam create-role --role-name eks-node-scheduler-role \
  --assume-role-policy-document file://infra/scheduler/trust-policy.json \
  --description "EKS nightly node scheduler (created by infra/scheduler)"
aws iam put-role-policy --role-name eks-node-scheduler-role \
  --policy-name eks-node-scheduler \
  --policy-document file://infra/scheduler/iam-policy.json
aws iam attach-role-policy --role-name eks-node-scheduler-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 2. EventBridge invoke role (trusts events.amazonaws.com — this is the fix)
aws iam create-role --role-name eks-node-scheduler-invoke \
  --assume-role-policy-document file://infra/scheduler/invoke-trust-policy.json \
  --description "Lets EventBridge invoke the node scheduler Lambda"
aws iam put-role-policy --role-name eks-node-scheduler-invoke \
  --policy-name invoke-scheduler \
  --policy-document file://infra/scheduler/invoke-policy.json

# 3. Package + create the function
cd infra/scheduler && zip scheduler.zip scheduler.py && cd -
aws lambda create-function \
  --function-name eks-node-scheduler \
  --runtime python3.12 \
  --role arn:aws:iam::195675606509:role/eks-node-scheduler-role \
  --handler scheduler.handler \
  --zip-file fileb://infra/scheduler/scheduler.zip \
  --timeout 900 \
  --environment 'Variables={CLUSTER_NAME:eks-lab,NODEGROUP_NAME:ng-eks,DESIRED_CAPACITY:5}'

# 4. Rules, pointing at the INVOKE role
aws events put-rule --name eks-nodes-off \
  --schedule-expression "cron(58 17 * * ? *)" --state ENABLED \
  --description "Terminate EKS nodes at 17:58 UTC"
aws events put-rule --name eks-nodes-on \
  --schedule-expression "cron(0 10 * * ? *)" --state ENABLED \
  --description "Launch EKS nodes at 10:00 UTC"

for pair in "eks-nodes-off:off" "eks-nodes-on:on"; do
  rule="${pair%%:*}"; action="${pair##*:}"
  aws events put-targets --rule "$rule" --targets \
    "Id=scheduler,Arn=arn:aws:lambda:us-west-1:195675606509:function:eks-node-scheduler,RoleArn=arn:aws:iam::195675606509:role/eks-node-scheduler-invoke,Input={\"detail\":{\"action\":\"$action\"}}"
done
```

## Verify

```bash
# Both rules enabled, on the right schedule, using the INVOKE role
aws events list-rules --name-prefix eks-nodes \
  --query 'Rules[].[Name,ScheduleExpression,State]'
aws events list-targets-by-rule --rule eks-nodes-off \
  --query 'Targets[].[Arn,RoleArn,Input]'

# The invoke role trusts events.amazonaws.com (not just lambda.amazonaws.com)
aws iam get-role --role-name eks-node-scheduler-invoke \
  --query 'Role.AssumeRolePolicyDocument.Statement[].Principal'
```

Then prove the whole path end-to-end — see "Did it actually fire?" in
[docs/mirror.md](../../docs/mirror.md) for the schedule and the resume behaviour.
