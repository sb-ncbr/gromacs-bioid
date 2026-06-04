---
name: pod-debug
description: >-
  Read-only Kubernetes pod debugging for BAT3 worker runs. Inspects files
  inside the bat3-bat3-worker deployment via kubectl exec using only safe,
  non-modifying commands (ls, find, cat, head, tail).
---

# Pod Debug Skill

## Purpose

Diagnose failed or in-progress BAT3 pipeline runs by inspecting files inside the worker pod at `/app/runs/<run_id>/`. This skill provides safe, read-only access to pod filesystem contents without executing arbitrary commands or modifying state.

## Target Path Pattern

```
/app/runs/<run_id>/
```

Replace `<run_id>` with the specific run identifier provided by the user.

## Allowed Operations

ONLY use these `kubectl exec` patterns:

```bash
kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- ls <path>
kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- ls -la <path>
kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- find <path>
kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- cat <path>
kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- head <path>
kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- tail <path>
```

## Forbidden Operations

NEVER execute:

- **Write commands**: `rm`, `mv`, `cp`, `write`, `edit`, `tee`
- **Kubectl mutations**: `kubectl apply`, `kubectl delete`, `kubectl create`, `kubectl patch`
- **Shell redirects**: `>`, `>>`, `| tee`, `| xargs`
- **Interactive shells**: `/bin/sh`, `bash`, `-it` flags
- **Arbitrary commands**: Any command not explicitly in the allowed list
- **Pipe to local files**: Never redirect output to local filesystem

## Workflow

1. **Receive run_id**: Obtain the specific run identifier from the user.

2. **List directory contents**:
   ```bash
   kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- ls -la /app/runs/<run_id>/
   ```

3. **Identify relevant files**: Look for log files, output files, status files (e.g., `*.log`, `*.txt`, `*.json`, `status`, `error`).

4. **Read files**: Use `cat`, `head`, or `tail` to read only files the user explicitly requests or that are clearly part of the run output:
   ```bash
   kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- cat /app/runs/<run_id>/logfile.txt
   ```

5. **Report findings**: Summarize the contents concisely for the user.

## Safety Reminders

- **Never** execute interactive shells (`/bin/sh`, `bash`).
- **Never** run arbitrary commands outside the allowed list.
- **Never** pipe output to local files or redirect streams.
- **Never** modify pod state in any way.
- **Only** read files that are part of the run output or explicitly requested by the user.
- **Stay** within the `/app/runs/<run_id>/` path unless the user explicitly requests otherwise.

## Example Session

```
User: Debug run abc123

1. List directory:
   kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- ls -la /app/runs/abc123/

2. Read log file:
   kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- cat /app/runs/abc123/run.log

3. Check status:
   kubectl exec -n gromacs-bioid-ns deployment/bat3-bat3-worker -- cat /app/runs/abc123/status.json
```
