# Frontend Contract

Any frontend template must implement the following Docker and HTTP interface to work with the Kreator platform (Helm charts, ArgoCD, Crossplane, Sealed Secrets).

## Screens

- **Login**: username/password form, calls POST /api/auth/login
- **Register**: username/password form, calls POST /api/auth/register
- **Todo list**: create todos, toggle completion, delete todos

## Auth

- Send `Authorization: Bearer <token>` header on all /api/todos requests
- Redirect to login when receiving a 401

## Backend connectivity

- Health indicator showing whether the backend is reachable (GET /healthz)

## Environment variables

The Helm chart passes a single generic `API_URL` env var (e.g., `http://api.localhost`). The Dockerfile or entrypoint script is responsible for mapping `API_URL` to whatever the framework expects internally. Examples:

- A Next.js template maps `API_URL` to `NEXT_PUBLIC_API_URL`
- A Vite template maps `API_URL` to `VITE_API_URL` at build time
- A Go/HTMX template reads `API_URL` directly

How the mapping happens is internal to the template. The Helm chart does not know or care.

## Runtime requirements

- Serves on port 3000
- Multi-stage Dockerfile, runs as UID 1001
- Accepts `API_URL` as the only required environment variable
