# Source Development Mode

This setup runs PostgreSQL with pgvector and Redis in Docker, while the Django backend and Vite frontend run from source.

## 1. Start dependencies

```bash
./scripts/dev-deps-up.sh
```

This starts:

- PostgreSQL 17 on `127.0.0.1:5432`
- pgvector extension in database `maxkb`
- Redis on `127.0.0.1:6379`

Default local credentials:

```text
PostgreSQL database: maxkb
PostgreSQL user: root
PostgreSQL password: Password123@postgres
Redis password: Password123@redis
```

## 2. Start backend

```bash
./scripts/dev-backend.sh
```

The backend listens on:

```text
http://localhost:8080
```

The script creates `.venv` automatically with Python 3.11 through `uv`, installs backend dependencies, runs migrations, and starts the Django development server.

Local runtime files such as logs, temporary files, and model cache are written under `.local/maxkb`.

## 3. Start admin frontend

Open a second terminal:

```bash
./scripts/dev-frontend-admin.sh
```

Admin UI:

```text
http://localhost:3000/admin/
```

Default login:

```text
admin
MaxKB@123..
```

## 4. Remove the default local embedding model

The source database migration creates a default local embedding model. If you plan to use an online embedding provider, remove that local default from the development database:

```bash
./scripts/dev-remove-local-embedding.sh
```

Then add your online embedding model in the MaxKB UI before creating or vectorizing knowledge bases.

## 5. Optional chat frontend

Open another terminal:

```bash
./scripts/dev-frontend-chat.sh
```

Chat UI:

```text
http://localhost:3001/chat/
```

## Stop dependencies

```bash
./scripts/dev-deps-down.sh
```

To delete local database and Redis volumes too:

```bash
docker compose -f docker-compose.dev.yml down -v
```
