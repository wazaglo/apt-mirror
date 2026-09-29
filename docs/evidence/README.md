# Evidence

Captured against the live endpoints on 2026-09-29T12:58:28Z with a headless
Chrome driven as an unauthenticated client, so this shows what an `apt` client
on the internet actually receives, not what `curl` from inside the cluster
returns. [cluster-state.md](cluster-state.md) is the matching view from inside
the cluster.

| Page | Status | HTTPS | Screenshot |
| --- | --- | --- | --- |
| `debian-mirror.azubisuccess.space/debian/dists/` | 200 | valid | [screens/debian-mirror-dists.png](screens/debian-mirror-dists.png) |
| `ubuntu-mirror.azubisuccess.space/ubuntu/dists/` | 200 | valid | [screens/ubuntu-mirror-dists.png](screens/ubuntu-mirror-dists.png) |
| `debian-mirror.azubisuccess.space/debian/` | 200 | valid | [screens/debian-mirror-root.png](screens/debian-mirror-root.png) |
| `grafana.azubisuccess.space/login` | 200 | valid | [screens/grafana-login.png](screens/grafana-login.png) |

`secureContext: true` on every page is the browser's own verdict on the
wildcard certificate, read from the page after the connection was established.
It is a stronger claim than a `200` because the TLS handshake had to succeed
first.

## Console

`console.json` holds every console message, page error, failed request and
non-2xx response per page, plus the capture timestamp. The current capture has
zero console errors and zero failed requests on all four pages.

One 404 is present and expected: browsers request `/favicon.ico` unprompted, and
a package mirror has no reason to serve one. The script records it in
`nonOkResponses` but does not treat it as a failure, so a genuine missing asset
would still fail the run.

## What this does not prove

Screenshots are cheap to fake and easy to leave stale. This capture is
regenerable and exits nonzero on any real error, which is the part that makes it
worth more than a picture — but it still only covers page load. It does not
verify that a package installs, that GPG signature verification passes, or that
every file in the pool is intact. Those are separate claims and they need
`apt-get` against the mirror to check.
