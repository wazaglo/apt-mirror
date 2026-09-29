# Cluster state

Captured from the live cluster at **2026-09-29T13:05:37Z**, verbatim from the
API server. A point-in-time record; regenerate rather than edit.

Server: `v1.36.4-eks-cfb47f5`

## Nodes

```
NAME                                        STATUS   ROLES    AGE    VERSION               INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                        KERNEL-VERSION                            CONTAINER-RUNTIME
ip-10-0-11-117.us-west-1.compute.internal   Ready    <none>   3h4m   v1.36.4-eks-f4fc4f1   10.0.11.117   <none>        Amazon Linux 2023.12.20260918   6.18.48-109.150.amzn2023.x86_64 (amd64)   containerd://2.2.7+unknown
ip-10-0-11-150.us-west-1.compute.internal   Ready    <none>   3h4m   v1.36.4-eks-f4fc4f1   10.0.11.150   <none>        Amazon Linux 2023.12.20260918   6.18.48-109.150.amzn2023.x86_64 (amd64)   containerd://2.2.7+unknown
ip-10-0-11-59.us-west-1.compute.internal    Ready    <none>   3h4m   v1.36.4-eks-f4fc4f1   10.0.11.59    <none>        Amazon Linux 2023.12.20260918   6.18.48-109.150.amzn2023.x86_64 (amd64)   containerd://2.2.7+unknown
ip-10-0-12-137.us-west-1.compute.internal   Ready    <none>   3h4m   v1.36.4-eks-f4fc4f1   10.0.12.137   <none>        Amazon Linux 2023.12.20260918   6.18.48-109.150.amzn2023.x86_64 (amd64)   containerd://2.2.7+unknown
ip-10-0-12-204.us-west-1.compute.internal   Ready    <none>   3h4m   v1.36.4-eks-f4fc4f1   10.0.12.204   <none>        Amazon Linux 2023.12.20260918   6.18.48-109.150.amzn2023.x86_64 (amd64)   containerd://2.2.7+unknown
```

## Namespaces and pod ceilings

```
ip-10-0-11-117.us-west-1.compute.internal allocatable=11
ip-10-0-11-150.us-west-1.compute.internal allocatable=11
ip-10-0-11-59.us-west-1.compute.internal allocatable=11
ip-10-0-12-137.us-west-1.compute.internal allocatable=11
ip-10-0-12-204.us-west-1.compute.internal allocatable=11
```

## Workloads

```
NAMESPACE          NAME                                               READY   UP-TO-DATE   AVAILABLE   AGE    CONTAINERS                                  IMAGES                                                                                                                                                                                          SELECTOR
external-dns       deployment.apps/external-dns                       1/1     1            1           2d4h   external-dns                                602401143452.dkr.ecr.us-west-1.amazonaws.com/eks/external-dns:v0.23.0-eksbuild.1                                                                                                                app.kubernetes.io/instance=external-dns,app.kubernetes.io/name=external-dns
external-secrets   deployment.apps/external-secrets                   1/1     1            1           46h    external-secrets                            ghcr.io/external-secrets/external-secrets:v2.11.0                                                                                                                                               app.kubernetes.io/instance=external-secrets,app.kubernetes.io/name=external-secrets
external-secrets   deployment.apps/external-secrets-cert-controller   1/1     1            1           46h    cert-controller                             ghcr.io/external-secrets/external-secrets:v2.11.0                                                                                                                                               app.kubernetes.io/instance=external-secrets,app.kubernetes.io/name=external-secrets-cert-controller
external-secrets   deployment.apps/external-secrets-webhook           1/1     1            1           46h    webhook                                     ghcr.io/external-secrets/external-secrets:v2.11.0                                                                                                                                               app.kubernetes.io/instance=external-secrets,app.kubernetes.io/name=external-secrets-webhook
keda               deployment.apps/keda-admission-webhooks            1/1     1            1           46h    keda-admission-webhooks                     ghcr.io/kedacore/keda-admission-webhooks:2.21.0                                                                                                                                                 app=keda-admission-webhooks
keda               deployment.apps/keda-operator                      1/1     1            1           46h    keda-operator                               ghcr.io/kedacore/keda:2.21.0                                                                                                                                                                    app=keda-operator
keda               deployment.apps/keda-operator-metrics-apiserver    1/1     1            1           46h    keda-operator-metrics-apiserver             ghcr.io/kedacore/keda-metrics-apiserver:2.21.0                                                                                                                                                  app=keda-operator-metrics-apiserver
kube-system        deployment.apps/aws-load-balancer-controller       2/2     2            2           2d2h   aws-load-balancer-controller                public.ecr.aws/eks/aws-load-balancer-controller:v3.5.0                                                                                                                                          app.kubernetes.io/instance=aws-load-balancer-controller,app.kubernetes.io/name=aws-load-balancer-controller
kube-system        deployment.apps/coredns                            2/2     2            2           2d4h   coredns                                     602401143452.dkr.ecr.us-west-1.amazonaws.com/eks/coredns:v1.14.3-eksbuild.23                                                                                                                    eks.amazonaws.com/component=coredns,k8s-app=kube-dns
kube-system        deployment.apps/efs-csi-controller                 2/2     2            2           2d1h   efs-plugin,csi-provisioner,liveness-probe   public.ecr.aws/efs-csi-driver/amazon/aws-efs-csi-driver:v3.5.0,public.ecr.aws/csi-components/csi-provisioner:v6.3.0-eksbuild.7,public.ecr.aws/csi-components/livenessprobe:v2.19.0-eksbuild.7   app=efs-csi-controller,app.kubernetes.io/instance=aws-efs-csi-driver,app.kubernetes.io/name=aws-efs-csi-driver
kube-system        deployment.apps/metrics-server                     2/2     2            2           2d4h   metrics-server                              602401143452.dkr.ecr.us-west-1.amazonaws.com/eks/metrics-server:v0.9.0-eksbuild.11                                                                                                              app.kubernetes.io/instance=metrics-server,app.kubernetes.io/name=metrics-server
mirrors            deployment.apps/debian12-mirror-nginx              1/1     1            1           25h    nginx                                       nginx:1.27-alpine                                                                                                                                                                               app=debian12-mirror-nginx
mirrors            deployment.apps/debian12-mirror-sync               1/1     1            1           25h    debian12-sync                               wazaglo/debian12-mirror@sha256:c512bae3d99d92453bb99034c4436bbd6e0c6699176fb530862cf33dea9632a1                                                                                                 app=debian12-mirror-sync
mirrors            deployment.apps/ubuntu24-mirror-sync               1/1     1            1           20h    ubuntu24-sync                               wazaglo/ubuntu24-mirror@sha256:5accc1ac9f56d1bbbe8c13af201697629920faba0c35b45cb4f25052f241ba83                                                                                                 app=ubuntu24-mirror-sync
monitoring         deployment.apps/blackbox                           1/1     1            1           2d     blackbox                                    prom/blackbox-exporter@sha256:e753ff9f3fc458d02cca5eddab5a77e1c175eee484a8925ac7d524f04366c2fc                                                                                                  app=blackbox
monitoring         deployment.apps/grafana                            1/1     1            1           2d1h   grafana                                     grafana/grafana@sha256:ac461fb352abc50da10a51c7d02462e9c05488f11f53f14b3ad79a8145f638a0                                                                                                         app=grafana
monitoring         deployment.apps/loki                               1/1     1            1           2d     loki                                        grafana/loki@sha256:4c431d2e6b9b38718694b31c5d56be7c80dc69c513215fde1aeb5b02cd4e2665                                                                                                            app=loki
monitoring         deployment.apps/prometheus                         1/1     1            1           2d     prometheus                                  prom/prometheus@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e                                                                                                         app=prometheus
nginx-demo         deployment.apps/nginx                              2/2     2            2           2d1h   nginx                                       nginx@sha256:abe47724e466aeab9a345d8e46a221c2fa8953c7848bb4a3bd9976a7199f8cf2                                                                                                                   app=nginx

NAMESPACE   NAME                                         SCHEDULE      TIMEZONE   SUSPEND   ACTIVE   LAST SCHEDULE   AGE   CONTAINERS   IMAGES                                                                                            SELECTOR
mirrors     cronjob.batch/debian12-mirror-snapshot       30 12 * * *   Etc/UTC    True      0        <none>          23h   snapshot     wazaglo/debian12-mirror@sha256:c512bae3d99d92453bb99034c4436bbd6e0c6699176fb530862cf33dea9632a1   <none>
mirrors     cronjob.batch/debian12-mirror-sync-trigger   0 10 * * *    Etc/UTC    False     0        3h5m            25h   trigger      alpine/k8s@sha256:a51aa37f0a34ff827c7f2f9cb7f6fbb8f0e290fa625341be14c2fcc4b1880f60                <none>
mirrors     cronjob.batch/ubuntu24-mirror-sync-trigger   30 12 * * *   Etc/UTC    True      0        <none>          20h   trigger      alpine/k8s@sha256:a51aa37f0a34ff827c7f2f9cb7f6fbb8f0e290fa625341be14c2fcc4b1880f60                <none>

NAMESPACE          NAME                                        TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                  AGE    SELECTOR
default            service/kubernetes                          ClusterIP   172.20.0.1       <none>        443/TCP                  2d4h   <none>
external-dns       service/external-dns                        ClusterIP   172.20.142.50    <none>        7979/TCP                 2d4h   app.kubernetes.io/instance=external-dns,app.kubernetes.io/name=external-dns
external-secrets   service/external-secrets-webhook            ClusterIP   172.20.51.47     <none>        443/TCP                  46h    app.kubernetes.io/instance=external-secrets,app.kubernetes.io/name=external-secrets-webhook
keda               service/keda-admission-webhooks             ClusterIP   172.20.193.185   <none>        443/TCP                  46h    app=keda-admission-webhooks
keda               service/keda-operator                       ClusterIP   172.20.148.216   <none>        9666/TCP                 46h    app=keda-operator
keda               service/keda-operator-metrics-apiserver     ClusterIP   172.20.124.199   <none>        443/TCP,8080/TCP         46h    app=keda-operator-metrics-apiserver
kube-system        service/aws-load-balancer-webhook-service   ClusterIP   172.20.111.127   <none>        443/TCP                  2d2h   app.kubernetes.io/instance=aws-load-balancer-controller,app.kubernetes.io/name=aws-load-balancer-controller
kube-system        service/eks-extension-metrics-api           ClusterIP   172.20.190.110   <none>        443/TCP                  2d4h   <none>
kube-system        service/kube-dns                            ClusterIP   172.20.0.10      <none>        53/UDP,53/TCP,9153/TCP   2d4h   k8s-app=kube-dns
kube-system        service/metrics-server                      ClusterIP   172.20.50.235    <none>        443/TCP                  2d4h   app.kubernetes.io/instance=metrics-server,app.kubernetes.io/name=metrics-server
mirrors            service/debian12-mirror-service             ClusterIP   172.20.123.86    <none>        80/TCP                   25h    app=debian12-mirror-nginx
monitoring         service/blackbox                            ClusterIP   172.20.163.176   <none>        9115/TCP                 2d     app=blackbox
monitoring         service/grafana                             ClusterIP   172.20.25.243    <none>        3000/TCP                 2d1h   app=grafana
monitoring         service/loki                                ClusterIP   172.20.148.246   <none>        3100/TCP                 2d     app=loki
monitoring         service/prometheus                          ClusterIP   172.20.238.32    <none>        9090/TCP                 2d     app=prometheus
nginx-demo         service/nginx                               ClusterIP   172.20.82.40     <none>        80/TCP                   2d1h   app=nginx

NAMESPACE    NAME                                        STATUS   VOLUME                CAPACITY   ACCESS MODES   STORAGECLASS    VOLUMEATTRIBUTESCLASS   AGE    VOLUMEMODE
mirrors      persistentvolumeclaim/debian12-mirror-pvc   Bound    debian12-mirror-efs   100Gi      RWX            efs-mirror-sc   <unset>                 26h    Filesystem
mirrors      persistentvolumeclaim/ubuntu24-mirror-pvc   Bound    ubuntu24-mirror-efs   300Gi      RWX            efs-mirror-sc   <unset>                 20h    Filesystem
monitoring   persistentvolumeclaim/grafana-data          Bound    grafana-efs           5Gi        RWX            efs-sc          <unset>                 2d1h   Filesystem
monitoring   persistentvolumeclaim/prometheus-data       Bound    prometheus-efs        10Gi       RWX            efs-sc          <unset>                 46h    Filesystem

NAMESPACE    NAME                              CLASS   HOSTS   ADDRESS                                                               PORTS   AGE
nginx-demo   ingress.networking.k8s.io/nginx   alb     *       k8s-nginxdem-nginx-98f1f39520-324967465.us-west-1.elb.amazonaws.com   80      2d1h
```

## Mirror EFS volumes

```
NAME                  ACCESS_POINT                                   ACCESS_MODE     STATUS
debian12-mirror-efs   fs-0b0491ead2bac1c8c::fsap-020b79f4588c2d482   ReadWriteMany   Bound
grafana-efs           fs-0ddb254be08c6267a::fsap-088c8c16707025698   ReadWriteMany   Bound
prometheus-efs        fs-0ddb254be08c6267a::fsap-012a38be930c8a207   ReadWriteMany   Bound
ubuntu24-mirror-efs   fs-0b0491ead2bac1c8c::fsap-02586212ea002c468   ReadWriteMany   Bound
```

## Mirror pods

```
NAME                                     READY   STATUS    RESTARTS   AGE    IP            NODE                                        NOMINATED NODE   READINESS GATES
debian12-mirror-nginx-68cdf86c6c-bfbr8   1/1     Running   0          100m   10.0.12.251   ip-10-0-12-204.us-west-1.compute.internal   <none>           <none>
debian12-mirror-sync-bfdd44d75-f7s9z     1/1     Running   0          19m    10.0.11.229   ip-10-0-11-117.us-west-1.compute.internal   <none>           <none>
ubuntu24-mirror-sync-d74d4b94-79jfx      1/1     Running   0          19h    10.0.11.248   ip-10-0-11-59.us-west-1.compute.internal    <none>           <none>
```

## Observability pods

```
NAME                         READY   STATUS    RESTARTS   AGE    IP            NODE                                        NOMINATED NODE   READINESS GATES
alloy-72jfm                  1/1     Running   0          3h4m   10.0.12.180   ip-10-0-12-137.us-west-1.compute.internal   <none>           <none>
alloy-bdplc                  1/1     Running   0          3h4m   10.0.11.169   ip-10-0-11-150.us-west-1.compute.internal   <none>           <none>
alloy-ndfb7                  1/1     Running   0          3h4m   10.0.12.8     ip-10-0-12-204.us-west-1.compute.internal   <none>           <none>
alloy-q77px                  1/1     Running   0          3h4m   10.0.11.52    ip-10-0-11-59.us-west-1.compute.internal    <none>           <none>
alloy-sg9zm                  1/1     Running   0          3h4m   10.0.11.213   ip-10-0-11-117.us-west-1.compute.internal   <none>           <none>
blackbox-64cf67d555-mdfw8    1/1     Running   0          3h     10.0.12.7     ip-10-0-12-137.us-west-1.compute.internal   <none>           <none>
grafana-575876b658-wlmtm     1/1     Running   0          3h     10.0.12.136   ip-10-0-12-137.us-west-1.compute.internal   <none>           <none>
loki-5b64797c8-sl4lv         1/1     Running   0          3h     10.0.12.247   ip-10-0-12-137.us-west-1.compute.internal   <none>           <none>
prometheus-5b8d59487-x2tlh   1/1     Running   0          27m    10.0.12.217   ip-10-0-12-137.us-west-1.compute.internal   <none>           <none>
```

## Blackbox probe targets

```
Error from server (NotFound): configmaps "prometheus-config-*" not found
(command failed)
```

## Live in-cluster config hashes

```
NAME                           CREATED
mirror-nginx-conf              2026-09-28T11:45:56Z
mirror-nginx-conf-27f767f8hd   2026-09-29T11:25:54Z
```

