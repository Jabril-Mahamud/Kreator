# Frontend Contract

Any frontend template must implement the following to work with the Kreator platform.

## Screens

- **Login**: username/password form, calls POST /api/auth/login
- **Register**: username/password form, calls POST /api/auth/register
- **Todo list**: create todos, toggle completion, delete todos

## Auth

- Store the JWT in React state (not localStorage)
- Pass it as `Authorization: Bearer <token>` on all /api/todos requests
- Redirect to login when receiving a 401

## Backend connectivity

- Health indicator dot showing whether the backend is reachable (GET /healthz)
- Green when connected, red when not

## Environment variables

- Next.js: `NEXT_PUBLIC_API_URL` (e.g., http://api.localhost)
- React/Vite: `VITE_API_URL` (e.g., http://api.localhost)

## Runtime requirements

- Serves on port 3000
- Multi-stage Dockerfile, runs as UID 1001
- Static build output where possible
