# Demo: scan, fix, rescan

A reproducible fix-and-rescan loop against OWASP Juice Shop, run entirely on your
own machine so it does not depend on anyone's uptime.

Juice Shop is deliberately vulnerable and we do not patch it. The fix goes in
front of it, which is the remediation SentinelAI recommends whenever a finding
cannot be fixed in the application itself.

## 1 - Start the target, unprotected

```bash
docker run -d --name juiceshop -p 8080:3000 bkimminich/juice-shop
```

Port **8080** matters: `url_guard` only permits 80, 443, 8080 and 8443.

## 2 - Scan it

Set `ALLOW_PRIVATE_TARGETS=true` in `backend/.env`, then scan `http://localhost:8080/`.

```
[HIGH  ] Site served over plain HTTP - all traffic is unencrypted
[HIGH  ] Missing security header: Content-Security-Policy
[HIGH  ] Directory listing exposed: /ftp
[MEDIUM] Prometheus metrics exposed publicly (internal telemetry): /metrics
[LOW   ] Missing security header: Referrer-Policy
[LOW   ] Missing security header: Permissions-Policy
[LOW   ] Wildcard CORS policy on public content

Risk score: 74/100 HIGH
```

Open `http://localhost:8080/ftp` in a browser. `acquisitions.md` inside it opens
with *"This document is confidential"*. The finding is real.

## 3 - Fix it at the edge

Move Juice Shop off the host port and put nginx in front of it:

```bash
docker rm -f juiceshop
docker network create juicenet
docker run -d --name juiceshop --network juicenet bkimminich/juice-shop
docker build -t juice-edge demo/juice-shop
docker run -d --name juice-edge --network juicenet -p 8080:8080 juice-edge
```

`nginx.conf` adds the three missing headers, drops the wildcard CORS header, and
returns 403 for `/ftp` and `/metrics`.

## 4 - Rescan

```
[HIGH  ] Site served over plain HTTP - all traffic is unencrypted

Risk score: 40/100 MEDIUM
```

Seven findings to one. Same scan, same scoring, nothing edited in the report.

**The interesting part happened between passes.** The first hardening attempt
scored 40/100 but reported a *new* finding - `Server information disclosed via
'server': nginx/1.31.3` - because the proxy advertised its own version. The fix
introduced it and the rescan caught it. `server_tokens off` closes it.

The remaining HIGH is honest: the site really is served over plain HTTP. In
production you terminate TLS at this same edge with a real certificate. A
self-signed certificate would trade this finding for a CRITICAL one, which is
the scanner behaving correctly.

## Clean up

```bash
docker rm -f juiceshop juice-edge
docker network rm juicenet
```
