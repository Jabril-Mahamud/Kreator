# Backend Contract

Any backend template must implement the following HTTP API to work with the Kreator platform (Helm charts, ArgoCD, Crossplane, Sealed Secrets, and the frontend).

## Auth endpoints

### POST /api/auth/register
Body: `{"username": "...", "password": "..."}`
Returns: `{"id": "...", "username": "..."}`
Passwords hashed with bcrypt. Returns 409 if username taken.

### POST /api/auth/login
Body: `{"username": "...", "password": "..."}`
Returns: `{"token": "..."}`
Token is a JWT signed with JWT_SECRET, expires after 24 hours. Returns 401 for invalid credentials.

## Todo endpoints (all require Authorization: Bearer <token>)

All return 401 without a valid token. Todos are scoped to the authenticated user.

### GET /api/todos
Returns the authenticated user's todos as a JSON array.

### POST /api/todos
Body: `{"title": "...", "description": "..."}`
Creates a todo with `completed: false` by default.

### GET /api/todos/:id
Returns a single todo. 404 if it belongs to another user or does not exist.

### PATCH /api/todos/:id
Body: any subset of `{"title": "...", "description": "...", "completed": true/false}`
Updates the specified fields. 404 if not owned by the user.

### DELETE /api/todos/:id
Deletes the todo. 404 if not owned by the user.

## Infrastructure endpoints

### GET /healthz
Returns `{"status": "ok"}`. No auth required.

### GET /readyz
Checks database connectivity. Returns `{"status": "ready"}` or 503.

### GET /metrics
Prometheus-format metrics. No auth required.

## Database schema

Two tables:
- `users`: id (uuid, PK), username (text, unique), password_hash (text)
- `todos`: id (uuid, PK), user_id (uuid, FK to users), title (text), description (text, nullable), completed (boolean, default false), created_at (timestamp)

The backend creates/migrates tables on startup.

## Environment variables

- `DATABASE_URL`: Postgres connection string
- `JWT_SECRET`: Secret key for signing JWTs
- `PORT`: defaults to 8000

## Runtime requirements

- Listens on port 8000
- Structured JSON logging to stdout
- Multi-stage Dockerfile, runs as UID 1001
- Prometheus metrics on /metrics
