# Infrastructure Configuration

This directory contains container and server infrastructure for the NUST LMS Lab Assistant:
- `docker-compose.yml`: Local multi-service topology (Caddy, API, Worker, PostgreSQL, Redis)
- `Caddyfile`: Reverse proxy providing TLS termination and single-origin routing
- `Dockerfile.sandbox`: Non-root, network-isolated code execution container
