# Deploy LinguaSearch

This MVP is a **single private workspace**. Every person with the workspace token can read, rename, upload, download, and delete every document. It has no individual user accounts. Never post the token in your portfolio or use real private documents in a shared recruiter demo.

## Recommended: one Docker container + persistent disk

Requirements: Docker Engine with Compose, outbound HTTPS to api.openai.com for AI mode, 1 GB RAM minimum. No external database or vector service is needed.

```sh
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
# Put that generated value into WORKSPACE_TOKEN in .env.
# Optionally put your model key into OPENAI_API_KEY.
docker compose up --build -d
```

Open http://localhost:8000, then Settings & connection → enter **WORKSPACE_TOKEN**. The frontend and API share one origin. The default Compose port is loopback-only. Production refuses to start with a missing/short workspace token.

The Docker image runs as user 10001, disables proxy-header trust, and uses one worker. SQLite stores document metadata, original PDF bytes, passages, and cached embeddings together under `/app/runtime/lingua.db`. The named `lingua-data` volume persists after container recreation. **Do not run `docker compose down -v` unless you intend to delete your data.**

## Public URL for your portfolio

GitHub stores the code. **GitHub Pages cannot run FastAPI or persistent SQLite.** Deploy the Docker image to a Docker-capable VM or container host that supports a persistent writable disk, then point your domain to that host.

1. Build this repository's `Dockerfile`.
2. Mount a persistent disk at `/app/runtime`, writable by UID 10001. Use a single instance; do not use an ephemeral/serverless disk.
3. Set `APP_ENV=production`, `WORKSPACE_TOKEN` (32+ random characters), `DATABASE_PATH=/app/runtime/lingua.db`, `DEMO_SEED=true`; optionally set `OPENAI_API_KEY` and model names.
4. Expose container port 8000 through the host's HTTPS reverse proxy. Keep health check `/health` public.
5. Keep the API on the same domain as the UI. Set `CORS_ORIGINS` to that HTTPS origin (no wildcard). The production CSP intentionally only permits same-origin API requests.
6. Use one worker and one replica. Apply a reverse-proxy body limit of 6 MB, request timeout around 180 seconds, plus an edge request/concurrency limit. First-time embedding of a large preexisting library can take longer: warm it privately or re-upload in small batches.
7. For an interviewer demo, use only synthetic/sample documents and share the workspace token privately. Rotate the token after the demo. A public read-only multi-user sandbox is outside this MVP's scope.

Example Caddy reverse proxy on a VM (replace the hostname):

```caddyfile
lingua.example.com {
    request_body {
        max_size 6MB
    }
    reverse_proxy 127.0.0.1:8000 {
        transport http {
            response_header_timeout 180s
        }
    }
}
```

Caddy handles TLS for a configured real domain. Set the VM firewall to expose 80/443 only. The app deliberately ignores forwarded IP headers by default, so users behind a proxy share the app's 60 requests/minute socket-IP limit; configure per-client limiting at your trusted edge. Do not enable unrestricted forwarded-header trust.

## Secrets and model configuration

| Variable | Meaning |
| --- | --- |
| `APP_ENV` | `development` locally; `production` requires a workspace token and hides API docs. |
| `WORKSPACE_TOKEN` | Shared private-workspace credential; distinct from a model key. Enter in UI Settings. |
| `OPENAI_API_KEY` | Backend-only OpenAI key. Empty enables offline keyword/excerpt mode. |
| `OPENAI_CHAT_MODEL` | Default `gpt-4.1-mini`; choose a Chat Completions model supporting JSON output, temperature, and max_tokens. |
| `OPENAI_EMBEDDING_MODEL` | Default `text-embedding-3-small`. Changing it invalidates cached vectors; next search re-embeds selected passages. |
| `DATABASE_PATH` | SQLite path; default `runtime/lingua.db`. Back up the database. |
| `CORS_ORIGINS` | Comma-separated exact origins. No model keys in browser environment variables. |
| `DEMO_SEED` | `true` inserts three synthetic text samples once per database; deleted samples stay deleted. |
| `MAX_UPLOAD_MB` | Default 5; PDF limit. Proxy/middleware must also allow multipart overhead. |

The browser stores the workspace token only in sessionStorage for that tab; clearing Settings removes it. The model key never goes to the browser. Set provider spending limits in your provider account. Uploading PDFs in AI mode sends extracted passages for embedding; asking a question sends the question plus retrieved passages and titles. Provider privacy/retention terms apply. Local mode makes no model requests.

API failures return a safe error rather than silently switching modes. No live provider validation is performed in CI; deterministic doubles exercise the AI path. Verify your own key/model access with a synthetic PDF before inviting reviewers.

## Backups, upgrades, and limits

Use SQLite's online backup API (safe while the service is running) or stop the service before copying the database. Example inside a running container:

```sh
docker compose exec linguasearch python -c "import sqlite3; a=sqlite3.connect('/app/runtime/lingua.db'); b=sqlite3.connect('/app/runtime/backup.db'); a.backup(b); b.close(); a.close()"
docker compose cp linguasearch:/app/runtime/backup.db ./lingua-backup.db
```

Keep backups outside the public repository. Back up before upgrading; this v1 creates tables if absent, but future schema changes need explicit migrations. Restore with the service stopped and correct file ownership.

Limits: 100 documents, 5,000 passages total, 100 pages and 300,000 extracted characters per PDF; 20-second isolated parsing timeout; one upload/search/answer/mutation at a time; 60 protected API calls/minute per socket IP. No OCR, background queue, streaming responses, multi-user isolation, external vector database, or PostgreSQL adapter in this MVP. SQLite and linear cosine search suit a small portfolio corpus. For scale, introduce migrations, identity/tenant isolation, background indexing, a shared rate limiter, and pgvector before adding replicas.
