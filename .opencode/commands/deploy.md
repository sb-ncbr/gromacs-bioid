---
description: >-
  Deploy BAT3 to Kubernetes. Usage: /deploy [all|backend|api|worker|frontend] [--build]
agent: deployer
---

Deploy BAT3 to Kubernetes.

Reads the repository deployment configuration and executes the appropriate deployment via `./deploy.sh`.

Usage examples:
- `/deploy all` — deploy full stack
- `/deploy backend --build` — build images, then redeploy API + Worker
- `/deploy api` — restart API deployment
- `/deploy frontend --build` — build and redeploy frontend

Request:
$ARGUMENTS
