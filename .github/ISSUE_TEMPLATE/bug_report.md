---
name: Bug report
about: Something in the cluster or pipeline is broken
title: "fix: "
labels: bug
---

## Symptom

## Expected

## Context (paste)

```text
# commit deployed from:
git rev-parse --short HEAD
# relevant state:
kubectl -n <ns> get deploy,pod,svc -o wide
```

## Suspected cause (optional)
