# OpenCode workflow for this repository

This repo uses a strict three-agent workflow with optional debugger and kubernetes support:

```text
Human -> /work -> planner -> researcher, if needed -> programmer -> planner summary -> Human
```

And for remote debugging:

```text
Human -> /debug -> planner -> debugger -> planner summary -> Human
```

And for kubernetes operations:

```text
Human -> /kubernetes -> planner -> kubernetes -> planner summary -> Human
```

## Agents

### planner

Primary orchestrator.

- Reads/searches the repo.
- Asks the human blocking questions.
- Invokes researcher for current/external information.
- Invokes programmer for implementation.
- Invokes debugger for remote Kubernetes pod debugging.
- Invokes kubernetes for Kubernetes operations.
- Must never edit files or run shell commands.

### researcher

Web-only subagent.

- Uses websearch/webfetch.
- Cannot read or edit local files.
- Returns source-backed, implementation-oriented findings.

### programmer

Implementation subagent.

- Uses qwen3.5.
- Reads and edits files.
- Runs focused verification.
- Cannot browse.
- Cannot ask the human questions.

### debugger

Read-only remote pod debugger.

- Uses qwen3.5.
- Uses kubectl exec with safe commands (ls, cat, find, grep, etc.) to inspect remote runs.
- Cannot edit files or run destructive commands.
- Only reports observations from remote pods.

### kubernetes

Kubernetes operator agent.

- Uses qwen3.5.
- Has unrestricted kubectl access (get, describe, logs, exec, apply, delete, etc.).
- Cannot edit local files or run arbitrary bash commands.
- Executes kubernetes operations and reports command outputs.

## Normal use

```text
/work Add pasted-table import with live validation.
```

For remote debugging:

```text
/debug Check the status of run 12345 in the bat3 worker pod
```

For kubernetes operations:

```text
/kubernetes Check pod status in the default namespace.
```

## Fallbacks

If planner handoff misbehaves:

```text
/code Add pasted-table import with live validation.
```

If only research is needed:

```text
/research Check current docs for [library/API].
```

If only kubernetes operations are needed:

```text
/kubernetes Get all pods in the gromacs-bioid-ns namespace.
```

## Hard boundary

Planner plans and delegates. Programmer codes. Researcher researches. Debugger inspects. Kubernetes operates.

If Planner prints a programmer task instead of invoking Programmer, run the printed task with `/code`.
