# Security

## Scope

The Debian and Ubuntu mirrors, the nginx edge that fronts them, and the EFS
archive they serve. The repository is **private**; access is by AWS IAM.

## Rules

1. **No secrets in git.** Credentials live in SSM Parameter Store and reach the
   cluster through External Secrets. See [architecture.md](docs/architecture.md).
2. **Least privilege for CI.** The GitHub deploy role (`apt-mirror-github-actions`)
   is assumed via OIDC and maps through an EKS access entry to the Kubernetes
   group `apt-mirror-deployers`. That group holds only namespaced verbs via
   `platform/bootstrap-rbac.yaml` and **cannot** create ClusterRoles,
   StorageClasses, PersistentVolumes or webhook configurations.
3. **Cluster-scoped and Helm-managed objects are applied by a human.** A
   compromised workflow cannot escalate itself. See
   [ADR-0004](docs/adr/0004-push-gitops-least-privilege.md).
4. **Pinned supply chain.** Images are pinned by digest. `pr-validate` rejects
   `:latest`; dependabot watches GitHub Actions and Docker.

## The OIDC trust boundary

The deploy role's trust policy is scoped to this repository:

```
repo:wazaglo/apt-mirror:*
repo:wazaglo@*/apt-mirror@*
```

The second form allows any user of the org to assume the role from a fork-like
subject. It was carried over during the rename from the previous policy. Tighten
it to the first form if you do not need the second.

The chain, end to end:

```
GitHub Actions  --OIDC-->  apt-mirror-github-actions   (trust: repo subject)
                            |
                      EKS access entry (STANDARD)
                            |
                      group  apt-mirror-deployers
                            |
                  ClusterRoleBinding  ->  ClusterRole  apt-mirror-deployer
```

The same chain was rebuilt during the repository rename and verified through
CloudTrail in both directions — the chain is documented end to end in
[mirror.md](docs/mirror.md#snapshots).

## The trigger service account

`mirror-sync-trigger` can `get` and `patch` exactly two objects — the Debian and
Ubuntu sync Deployments — by name, in one namespace. It cannot list, cannot
delete, and cannot read secrets. Verified by impersonation: `delete deployment`
and `list secrets` are both denied.

## Snapshots and tamper evidence

A mirror is only trustworthy if clients can detect modification. Both distros
publish GPG-signed `Release` files and the sync images carry the archive
keyring, so a client running stock apt verifies the index against Debian's and
Canonical's keys and **not** merely against this mirror. That is the control
that matters: compromising the mirror host does not let an attacker serve
modified packages to a verifying client.

Do not set `trusted=yes` in client `sources.list`. The end-to-end client test in
[mirror.md](docs/mirror.md) does the opposite deliberately.

## Reporting

Open a private security advisory on the repository. Do not open a public issue.
