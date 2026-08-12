# Deployment

> **Read this first.** recsys-lite is a demonstration project. It has **no
> authentication, no authorisation, no rate limiting and no multi-tenancy**.
> Every endpoint is public to anyone who can reach the port. Deploy it on a
> private network or behind an authenticating proxy, never naked on the public
> internet. See [../SECURITY.md](../SECURITY.md).

- [Docker (recommended)](#docker-recommended)
- [Bare process](#bare-process)
- [Behind a reverse proxy](#behind-a-reverse-proxy)
- [Persistence and backup](#persistence-and-backup)
- [Observability](#observability)
- [Resource sizing](#resource-sizing)
- [Upgrades](#upgrades)
- [Production gaps](#production-gaps)

---

## Docker (recommended)

```bash
docker build -t recsys-lite .

docker run -d --name recsys-lite -p 8000:8000 \
  -v recsys-lite-data:/app/data \
  -v recsys-lite-models:/app/models \
  recsys-lite
```

On first start with an empty model volume, `scripts/docker-entrypoint.sh`
bootstraps a dataset and trains a champion before serving — `docker run` alone
is enough to get a working instance. With the volumes mounted, later restarts
skip the bootstrap.

**Verified**: built and exercised end-to-end on Docker Engine 29.7.2. Final
image **1.51 GB** on `python:3.14-slim`, container runs as `uid=1000(appuser)`, and the built-in
`HEALTHCHECK` polls `/health`.

### Bootstrap sizing

| Variable | Default |
|---|---|
| `RECSYS_LITE_GEN_ITEMS` | `800` |
| `RECSYS_LITE_GEN_USERS` | `2000` |
| `RECSYS_LITE_TRAIN_EPOCHS` | `6` |

```bash
docker run -d -p 8000:8000 \
  -e RECSYS_LITE_GEN_ITEMS=200 -e RECSYS_LITE_GEN_USERS=400 \
  -e RECSYS_LITE_TRAIN_EPOCHS=2 \
  -v recsys-lite-data:/app/data -v recsys-lite-models:/app/models \
  recsys-lite
```

### Image size

The first build of this image was **8.03 GB**. On Linux, PyPI's default
`torch` wheel bundles the whole CUDA runtime — cuBLAS, cuDNN, NCCL, Triton,
cuFFT — roughly 6.5 GB of GPU libraries a CPU-only container can never use.
The `Dockerfile` installs torch from PyTorch's CPU index *first*, so the
subsequent editable install sees the requirement satisfied and never pulls the
CUDA build:

```dockerfile
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -e . \
    ...
```

**8.03 GB → 1.51 GB**, no functional difference.

### Docker on Windows without Docker Desktop

Docker Desktop fails to install on some Windows 11 Home machines (exit code
`-5`, both silent and GUI, no installer log). Docker Engine inside WSL2 works,
and is what this image was verified against:

```powershell
wsl --install --no-distribution                                   # then reboot
wsl --install Ubuntu-24.04 --location D:\wsl\Ubuntu-24.04 --no-launch
```

Then follow <https://docs.docker.com/engine/install/ubuntu/> inside the
distro. Windows drives appear under `/mnt/`, and WSL2 forwards published ports
to Windows `localhost`.

---

## Bare process

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

python -m recsys_lite.generator
python -m recsys_lite.features
python -m recsys_lite.train

python -m uvicorn recsys_lite.serving.app:app --host 0.0.0.0 --port 8000
```

### Workers

**Run a single worker.** Multiple uvicorn workers each hold their own in-memory
online feature store and their own SQLite connection. That means inconsistent
recommendations between workers and write contention on one file. If you need
more throughput, the honest answer is to replace SQLite and the in-process
cache first — not to add workers.

### systemd

```ini
[Unit]
Description=recsys-lite
After=network.target

[Service]
Type=simple
User=recsys
WorkingDirectory=/opt/recsys-lite
Environment=RECSYS_LITE_DB_PATH=/var/lib/recsys-lite/recsys_lite.db
Environment=RECSYS_LITE_REGISTRY_DIR=/var/lib/recsys-lite/models
ExecStart=/opt/recsys-lite/.venv/bin/python -m uvicorn recsys_lite.serving.app:app \
          --host 127.0.0.1 --port 8000
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/recsys-lite

[Install]
WantedBy=multi-user.target
```

Binding to `127.0.0.1` and putting a proxy in front is the point — see below.

---

## Behind a reverse proxy

Since the app has no auth of its own, the proxy is where access control lives.

```nginx
server {
    listen 443 ssl;
    server_name kestrel.example.internal;

    ssl_certificate     /etc/ssl/certs/kestrel.pem;
    ssl_certificate_key /etc/ssl/private/kestrel.key;

    # The app authenticates nobody. Do it here.
    auth_basic           "Kestrel";
    auth_basic_user_file /etc/nginx/.htpasswd;

    # Writes are unauthenticated and unlimited in the app itself.
    limit_req_zone $binary_remote_addr zone=writes:10m rate=10r/s;

    location /api/events {
        limit_req zone=writes burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        include proxy_params;
    }

    # Keep operational internals off any public surface.
    location /metrics { allow 10.0.0.0/8; deny all; proxy_pass http://127.0.0.1:8000; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        include proxy_params;
    }
}
```

---

## Persistence and backup

| Path | Contents | Losing it means |
|---|---|---|
| `data/recsys_lite.db` | Catalog, shoppers, event log | Everything — it is the system of record |
| `data/training_examples.jsonl` | Derived training rows | Nothing; rebuild with `features` |
| `models/` | Checkpoints + `registry.json` | Retrain, or serve nothing |

SQLite is one file, so backup is a file copy — but use the online backup API
rather than `cp` on a live database:

```bash
sqlite3 data/recsys_lite.db ".backup '/backup/recsys-$(date +%F).db'"
tar czf /backup/models-$(date +%F).tar.gz models/
```

Docker volumes:

```bash
docker run --rm -v recsys-lite-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/data.tar.gz -C /data .
```

---

## Observability

`GET /metrics` emits Prometheus text exposition — scrape it directly:

```yaml
scrape_configs:
  - job_name: recsys-lite
    static_configs:
      - targets: ['recsys-lite:8000']
```

| Metric | Meaning |
|---|---|
| `recsys_lite_uptime_seconds` | Process uptime |
| `recsys_lite_recommend_requests_total` | Recommendation calls |
| `recsys_lite_recommend_variant_total{variant}` | Champion vs candidate split |
| `recsys_lite_events_total{type}` | Events by type |
| `recsys_lite_empty_recommendations_total` | Requests that returned nothing |
| `recsys_lite_recommend_latency_ms_p50` / `_p95` | Serving latency |

**Counters are in-process** and reset on restart. There is no persistence and
no pushgateway. Alert on rate, not absolute value.

Worth alerting on: `/health` not `ok`, a rising
`recsys_lite_empty_recommendations_total` rate, p95 latency, and PSI reaching
`significant` from `/api/drift`.

---

## Resource sizing

Measured on the default 800-item / 2,000-shopper dataset, CPU only:

| Phase | CPU | Memory | Time |
|---|---|---|---|
| Generate | 1 core | ~150 MB | ~2 s |
| Build features | 1 core | ~400 MB | ~5 s |
| Train (6 epochs) | 1–4 cores | ~1.2 GB | ~50–100 s |
| Serve (idle) | negligible | ~500 MB | — |
| Serve (per request) | 1 core burst | +~50 MB | ~8 ms p50 |

A container with **2 vCPU / 2 GB** runs this comfortably. Training briefly
needs the most memory, which is why the Docker bootstrap trains before it
starts serving rather than alongside.

---

## Upgrades

```bash
git pull
pip install -e ".[dev]"
pytest tests -q                  # must be green before restarting
sudo systemctl restart recsys-lite
```

The API reads the champion at **startup**, so a newly promoted model needs a
restart. The database schema is created with `CREATE TABLE IF NOT EXISTS` and
there is **no migration framework** — a schema change means regenerating, or
writing the migration yourself.

---

## Production gaps

Things a real deployment needs that this project does not have. Listed so
nobody discovers them the hard way:

| Missing | Consequence |
|---|---|
| Authentication / authorisation | Anyone who reaches the port can read and write events |
| Rate limiting | Unbounded event writes |
| Multi-writer storage | SQLite serialises writes; one process only |
| Schema migrations | Schema changes require regeneration |
| Model rollback UI | Editing `registry.json` is the only way back |
| Automatic retraining | `features` + `train` are run by hand |
| Shadow traffic / auto-rollback | A/B splits traffic but never reverts on its own |
| Secret management | None needed today — and none supported if you add any |
| Horizontal scaling | In-process cache means workers disagree |

These are consequences of the deliberate scope described in
[ARCHITECTURE.md](ARCHITECTURE.md#what-stands-in-for-what), not oversights.
