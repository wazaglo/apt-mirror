# Runbook: ingress routing

**Symptom:** a `*.azubisuccess.space` URL returns 404, 502, or the wrong site.

Hostnames: `debian-mirror` and `ubuntu-mirror` (the package mirrors),
`grafana` (observability). The ALB has a single host-less rule, so all of them
reach the same edge nginx and `server_name` picks the backend.

## Before you start: is it 502 because it is the night?

Between **17:58 and 10:00 UTC** the node group is deliberately terminated and
every endpoint answers 502. That is not a fault. Check the clock before
debugging anything — see [cost-scheduler.md](cost-scheduler.md).

## 404 is often correct

`/` on a mirror hostname returns **404 on purpose**; the spool root is sealed so
its layout is not published. And during a first sync, `dists/` 404s because
apt-mirror stages indexes in `skel/` until the archive finishes:

```bash
# pool serves immediately, dists only appears when the sync completes
curl -sSI https://debian-mirror.azubisuccess.space/debian/pool/        # 200
kubectl -n mirrors logs deploy/debian12-mirror-sync --tail=3          # still running?
```

Do not change the nginx alias in response to a `dists/` 404 without first
confirming no sync is in flight.

The chain is: DNS → ALB → nginx (`server_name`) → app Service. Find the broken link:

```bash
# 1. DNS
dig +short debian-mirror.azubisuccess.space
dig +short ubuntu-mirror.azubisuccess.space
#   expect: k8s-nginxdem-nginx-….us-west-1.elb.amazonaws.com

# 2. ALB has a listener + rule
kubectl -n nginx-demo get ingress nginx -o yaml
aws elbv2 describe-listeners --region us-west-1 \
  --load-balancer-arn "$(kubectl -n nginx-demo get ingress nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' | { read h; aws elbv2 describe-load-balancers --region us-west-1 --query "LoadBalancers[?DNSName=='$h'].LoadBalancerArn" --output text; })"

# 3. nginx has the right config
kubectl -n nginx-demo get cm nginx-sites-<hash> -o jsonpath='{.data}' | grep -A3 server_name

# 4. app reachable from inside the cluster
kubectl -n monitoring exec deploy/nginx -- wget -q -O- --header='Host: grafana.azubisuccess.space' http://grafana.monitoring.svc.cluster.local:3000/login | head -c 80
```

## 404 from the ALB

The Ingress backend Service doesn't exist, or the Ingress is pointing at the
wrong name. In this repo the Ingress backend is `nginx` in `nginx-demo`; a
404 here usually means the Ingress was applied while the Service was missing
(it was once exactly this: `services "nginx" not found`).

```bash
kubectl -n nginx-demo describe ingress nginx | sed -n '1,20p'
kubectl -n nginx-demo get svc nginx
```

## 502 from the ALB

Targets unhealthy. With `target-type: ip`, the ALB targets pod IPs directly:

```bash
kubectl -n nginx-demo get endpoints nginx        # must list pod IPs
kubectl -n nginx-demo get pods -l app=nginx
kubectl -n nginx-demo logs deploy/nginx --tail=20
```

Health checks hit `/` on the default server block. If you change
`sites/_default.conf`, you can break every target at once.

## Wrong site / default page shown

`server_name` didn't match, so the default block answered. Either the new
site file isn't in the ConfigMap, or nginx hasn't reloaded:

```bash
kubectl -n nginx-demo get cm | grep nginx-sites
kubectl -n nginx-demo rollout restart deploy/nginx    # ConfigMap changes need a restart
```

A new site also needs (a) the file added to the `configMapGenerator` list in
`apps/nginx/base/kustomization.yaml`, and (b) a DNS record pointing at the
ALB. Adding only the file is the classic miss.

## HTTP not redirecting to HTTPS

`alb.ingress.kubernetes.io/ssl-redirect: '443'` plus the 443 listener must both
be present, and the certificate must be `ISSUED`:

```bash
aws acm describe-certificate --region us-west-1 \
  --certificate-arn arn:aws:acm:us-west-1:195675606509:certificate/cbf8d3ed-0f1f-4eeb-bba1-7093cdaf4fc6 \
  --query 'Certificate.Status'
```
