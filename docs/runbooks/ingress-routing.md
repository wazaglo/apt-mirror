# Runbook: ingress routing

**Symptom:** a `*.azubisuccess.space` URL returns 404, 502, or the wrong site.

The chain is: DNS → ALB → nginx (`server_name`) → app Service. Find the broken link:

```bash
# 1. DNS
dig +short grafana.azubisuccess.space
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
