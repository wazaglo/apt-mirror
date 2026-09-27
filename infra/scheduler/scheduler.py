"""
EKS node-group scheduler — turns the compute off at night.

Triggered by two EventBridge rules (UTC):
    17:58 daily -> off  (apps already drained by KEDA at 17:54)
    10:00 daily -> on   (KEDA scales apps at 10:05, once nodes can host them)

App scaling is NOT done here. KEDA's cron ScaledObjects own that, which is why
this function needs no Kubernetes credentials — only EKS/ASG control-plane
calls. See docs/runbooks/cost-scheduler.md.

Instances are TERMINATED, not stopped, so pods must already be gone. The KEDA
work window ends at 17:54 and this fires at 17:58, leaving 4 minutes for the
drain and the Prometheus WAL flush over EFS. A terminated node is replaced by a
fresh launch, so node names change every morning; nothing here addresses nodes
by name.
"""
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

CLUSTER_NAME = os.environ["CLUSTER_NAME"]
NODEGROUP_NAME = os.environ["NODEGROUP_NAME"]
# Daytime capacity. Keep in sync with the node group's maxSize.
DESIRED = int(os.environ.get("DESIRED_CAPACITY", "5"))
# EKS names the backing ASG "eks-<nodegroup>-<uuid>".
ASG_NAME_PREFIX = f"eks-{NODEGROUP_NAME}-"

# Instance launch is ~2-3 min; EKS applies the config change asynchronously.
SETTLE_TIMEOUT_S = 900
POLL_INTERVAL_S = 15

# AccessDenied: IAM policy propagation after a change. ResourceInUseException: a
# previous node group update has not finished settling. Throttling: standard.
RETRYABLE_ERRORS = {
    "AccessDeniedException",
    "ResourceInUseException",
    "ThrottlingException",
    "TooManyUpdatesException",
}

logger = logging.getLogger()
logger.setLevel(logging.INFO)

eks = boto3.client("eks")
asg = boto3.client("autoscaling")


def find_asg():
    """Locate the managed node group's backing Auto Scaling Group.

    EKS has no first-class API for this, and the ASG name prefix is the only
    stable handle (the UUID suffix changes if the node group is recreated).
    """
    groups = asg.describe_auto_scaling_groups()["AutoScalingGroups"]
    matches = [g for g in groups
               if g["AutoScalingGroupName"].startswith(ASG_NAME_PREFIX)]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly 1 ASG matching {ASG_NAME_PREFIX!r}, "
            f"found {len(matches)}: {[g['AutoScalingGroupName'] for g in matches]}"
        )
    return matches[0]


def update_nodegroup(min_size, desired, action):
    """Call UpdateNodegroupConfig, retrying transient IAM/control-plane errors.

    This job is unattended and runs once a day, so a single denied call would
    silently leave the cluster up (or down) until the next run. In this account
    the first call after an IAM policy change is intermittently denied while the
    policy propagates, and EKS returns ResourceInUseException if a previous
    update is still settling. Both are safe to retry: the operation is idempotent
    (it sets absolute sizes, not deltas), so read-modify-write is not a concern.
    """
    delays = [0, 5, 15, 30, 60, 120]
    last_error = None
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            logger.warning("%s: retrying in %ss (attempt %d/%d) after %s",
                           action, delay, attempt, len(delays), last_error)
            time.sleep(delay)
        try:
            eks.update_nodegroup_config(
                clusterName=CLUSTER_NAME,
                nodegroupName=NODEGROUP_NAME,
                scalingConfig={"minSize": min_size, "desiredSize": desired},
            )
            return
        except ClientError as exc:
            last_error = f"{exc.response['Error']['Code']}: {exc.response['Error']['Message'][:200]}"
            if exc.response["Error"]["Code"] not in RETRYABLE_ERRORS:
                raise
    raise RuntimeError(
        f"{action}: UpdateNodegroupConfig failed after {len(delays)} attempts "
        f"({last_error})"
    )


def set_capacity(action, min_size, desired):
    logger.info("%s: %s/%s -> min=%d desired=%d",
                action, CLUSTER_NAME, NODEGROUP_NAME, min_size, desired)
    update_nodegroup(min_size, desired, action)

    deadline = time.monotonic() + SETTLE_TIMEOUT_S
    while True:
        group = find_asg()
        instances = group.get("Instances", [])
        in_service = sum(1 for i in instances
                         if i["LifecycleState"] == "InService")
        logger.info("ASG %s: min=%s desired=%s instances=%d in-service=%d",
                    group["AutoScalingGroupName"], group["MinSize"],
                    group["DesiredCapacity"], len(instances), in_service)

        # Settle on InService count, not on the number of instance *records*.
        # A terminated instance lingers in the ASG for minutes in
        # Terminating:Wait/Proceed, so "no records" is not a reachable state
        # right after a scale-to-zero and would poll until the timeout.
        settled = (int(group["DesiredCapacity"]) == desired
                   and int(group["MinSize"]) == min_size
                   and in_service == desired)
        if settled:
            logger.info("%s complete: %d instance(s) in service", action, in_service)
            return {"asg": group["AutoScalingGroupName"], "inService": in_service}

        if time.monotonic() > deadline:
            # Not fatal: the next scheduled event re-reads real state and
            # converges. Raising here would just produce a noisy alarm.
            logger.warning("%s: ASG did not settle within %ss (last: desired=%s "
                           "instances=%d). Next run will reconcile.",
                           action, SETTLE_TIMEOUT_S,
                           group["DesiredCapacity"], len(instances))
            return {"asg": group["AutoScalingGroupName"], "settled": False}

        time.sleep(POLL_INTERVAL_S)


def handler(event, context):
    logger.info("event: %s", event)
    action = (event.get("detail") or {}).get("action") or event.get("action")
    if action not in ("on", "off"):
        raise ValueError(f"expected action 'on' or 'off', got {action!r}")

    if action == "off":
        return {"action": action, **set_capacity(action, 0, 0)}
    return {"action": action, **set_capacity(action, DESIRED, DESIRED)}
