# MCP server (AI assistants)

BioID has a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP)
server, so an AI assistant such as Claude can submit structures and
simulations to BioID, follow the run, and read and explain the
identifications for you.

```text
https://bioid-ceitec.dyn.cloud.e-infra.cz/mcp
```

It uses the **Streamable HTTP** transport and needs no account or API key.
The server is a thin client of the public [REST API](index.md#rest-api):
everything it does, you could also do in the web application.

## Adding it to your assistant

### Claude Code

```bash
claude mcp add --transport http bioid https://bioid-ceitec.dyn.cloud.e-infra.cz/mcp
```

Add `--scope user` to make it available in every project. Check it with
`claude mcp list`, or `/mcp` inside a session.

### Claude.ai and Claude Desktop

1. Open **Settings → Connectors** and choose **Add custom connector**.
2. Name it `BioID` and enter the URL
   `https://bioid-ceitec.dyn.cloud.e-infra.cz/mcp`. Leave the authentication
   settings empty.
3. In a chat, enable the connector from the tools menu.

!!! note
    On Team and Enterprise plans, an organisation owner may have to add the
    connector first.

### Other MCP clients

Any client that supports remote (Streamable HTTP) servers works. Most of
them accept a JSON configuration like this one:

```json
{
  "mcpServers": {
    "bioid": {
      "type": "http",
      "url": "https://bioid-ceitec.dyn.cloud.e-infra.cz/mcp"
    }
  }
}
```

Some clients call the type `streamable-http`, or only support local
(stdio) servers. For those, the `mcp-remote` bridge works:
`npx mcp-remote https://bioid-ceitec.dyn.cloud.e-infra.cz/mcp`.

## Tools

| Tool | What it does |
|---|---|
| `submit_structure` | Starts a run for a **PDB entry** (for example `3PTB`, downloaded from RCSB) or for **one file at a public `https://` URL**, such as a Zenodo file or a `.zip` bundle. |
| `submit_files` | Starts a run from file content the assistant passes along (as text, or base64 for binary formats such as `.tpr`). Suits small files. |
| `prepare_upload` | For files on your computer or larger than a few MB: returns a `curl` command (and a Python equivalent) that uploads them **straight to the BioID REST API**, not through the assistant. An assistant with a shell (Claude Code, for example) runs it and continues with the `run_id` it prints; otherwise it gives you the command. |
| `list_presets` | Lists the presets (`balanced`, `quick`, `exact`, `deep`) and the settings each one changes. |
| `get_run_status` | Queue position, the current stage, how many molecules have been searched, database searches that failed, and errors. |
| `get_results` | For each molecule: its kind, number of copies and size, the best verified database match with its confidence, and the other databases that matched too. |
| `get_molecule_details` | Everything about one molecule: its sequence or SMILES, formula and InChIKey, every verified hit ranked by confidence, the hits that were rejected and why. |
| `get_results_json` | The complete record of a run, [results.json](results-json.md): its download link, the link to its documentation and a guide to its structure; or, given a path such as `data/verification/A`, that part of it. |
| `list_examples` | The finished example runs from the front page, to try the tools without submitting anything. |
| `cancel_run` | Cancels a queued or running run, given the `owner_token` the submit tool returned. |

The server also provides two resources, `bioid://guide` on reading the
results and `bioid://results-json` on the structure of results.json, and a
prompt, `explain_run`, which asks the assistant to explain a run.

Runs take from a few minutes to about an hour, so the tools never wait for a
run to finish. A submit tool returns a `run_id` and a link to the results
page at once. The assistant then checks the status every minute or two. You
can also close the conversation and come back later with the `run_id` or
the link.

The **presets** are the ones on the web page (see
[Presets](index.md#presets-and-advanced-configuration)). `quick` gives a
first answer in minutes, `exact` reports only identical database entries,
and `deep` searches widest. Without a preset, `balanced` (the defaults) is
used. Individual settings cannot be changed through the MCP server; use the
web page or the REST API's `config_json` for that.

## Example prompts

- *"Identify the molecules in PDB entry 1P71 with BioID."*
- *"Run BioID on this GROMACS system"* (with `topol.top`, `conf.gro` and the
  `.itp` files attached), *"using the quick preset."*
- *"What does BioID find in https://zenodo.org/records/…/files/system.tpr?"*
- *"Run BioID on md/topol.tpr and md/conf.gro"* (in Claude Code: the files are
  uploaded with `prepare_upload`'s command).
- *"Download the results.json of my run and plot the confidence of every
  molecule."*
- *"Show me the BioID example runs and explain the membrane one."*
- *"Is the ligand in run 1c2a4d4b-… really benzamidine? How sure is BioID?"*
- *"Which molecules in my run were not identified, and why?"*

## Reading the results

- Each **molecule** is one distinct species in the system: a protein chain, a
  ligand, a lipid type, an ion, water. Identical copies are counted together
  (`copies`).
- Every database hit is **verified**: it is re-fetched from its database and
  compared with the simulated molecule (sequence identity, chemical structure
  or skeleton, element). Only verified hits count.
- **Confidence** is between 0 and 100: 80 or more is *high*, 50 to 80
  *medium*. A best match below 50 is reported as a *lead*, a plausible but
  weak match.
- `state` is `identified`, `lead`, `exact` (a monoatomic ion matched to its
  element) or `not_identified` (no hit passed verification; the rejected hits
  say why).
- Force fields often rename or remove atoms (hydrogens, protonation states,
  united-atom or coarse-grained models), so a correct identification can
  still have a medium confidence.
- If a database search failed or timed out, `get_run_status` lists it under
  `failed_searches`. A molecule may then have missed matches from that
  database.

## Limits

| | |
|---|---|
| Files per submission | `submit_files`: 50 MB in total, at most 20 files. `prepare_upload` (direct to the REST API): 128 MiB per file |
| URL downloads | `https://` only, publicly reachable hosts only, at most 5 redirects |
| Formats | GROMACS `.tpr` or `.top`+`.itp`+`.gro`; AMBER `.prmtop`/`.parm7` with `.rst7`/`.inpcrd`/`.nc`/`.mdcrd`; CHARMM/NAMD `.psf` with `.pdb`/`.crd`/`.dcd`; LAMMPS `.data`; `.pdb`/`.cif`; `.zip`/`.tar`/`.tar.gz` bundles |
| Run time | from a few minutes to about an hour |

!!! tip "Large systems"
    With `submit_files` the file content passes through the assistant, so it
    suits small text files such as a PDB file or a GROMACS topology. For
    anything larger, use `prepare_upload` (the files go straight to the REST
    API), give `submit_structure` a public URL of the file (for example on
    Zenodo), or upload it on the
    [web page](https://bioid-ceitec.dyn.cloud.e-infra.cz/) and ask the
    assistant about the run's `run_id`.

## Privacy

!!! warning "Your files are processed on the BioID service"
    The files you submit (or the URL you give) are sent to the BioID service
    at CEITEC / e-INFRA CZ and processed there, just like an upload on the
    web page. Do not submit unpublished or confidential structures you are
    not allowed to share.

- Runs are not tied to an account. **Anyone who has a run's `run_id` or link
  can open its results**. Only the holder of its `owner_token` (returned by
  the submit tool) can cancel it.
- Molecule sequences and structures are sent to public databases and search
  services (for example RCSB PDB and PubChem) to find matches.
- Results are deleted 30 days after the run finished (ask the assistant for
  another `retention` — a number of days or `preserve` — when submitting).
  To have a run removed earlier, write to the contact below. Runs submitted through the MCP server do not appear under
  **Your annotations** on the web page with a delete button: the owner token
  is with the assistant, not in your browser.
- Submissions are limited per network address (30 per hour) and paused
  while the queue is full; the tools then report when to try again. Cloud
  assistants (Claude.ai, Claude Desktop) share their provider's addresses, so
  that limit is shared too.
- Your assistant's provider also sees what you send through it. That is
  covered by your agreement with that provider.

Questions and bug reports: [tomas.pavlik@muni.cz](mailto:tomas.pavlik@muni.cz).
