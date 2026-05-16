# Security Policy

This policy covers both components in this repository: bash cma
(repository root) and cma-mcp (`cma-mcp/` subdirectory).

## Supported versions

| Component | Version | Supported |
|---|---|---|
| cma       | 1.0.x   | Yes |
| cma       | < 1.0   | No  |
| cma-mcp   | 0.1.x   | Yes |
| cma-mcp   | < 0.1   | No  |

Security fixes land on the latest minor release line of each
component; older minor releases are not backported. Operators
tracking security posture should pin to the latest published
artifact and update on each minor release.

## Reporting a vulnerability

If you find a security issue in either component, do not open a
public GitHub issue. Email `hello@clarethium.com` with
`[cma security]` in the subject line. Include:

- Affected component (cma or cma-mcp) and version
  (`cma --version` or `cma-mcp --version`)
- Reproduction steps
- Impact assessment if you have one

Acknowledgement within 7 days. Disclosure timeline negotiated on the
specifics; default is 90 days from acknowledgement to public
disclosure or coordinated release of a fix, whichever comes first.

## Threat model

Both components run locally on the operator's machine. The bash
cma CLI runs in an interactive terminal session (or as a hook
invoked by Claude Code, zsh, or bash-preexec). cma-mcp runs as an
MCP server (stdio transport) spawned by the operator's MCP client.
Their combined threat surface is limited:

1. **Untrusted input from MCP clients.** Tool arguments and resource
   read URIs originate in the MCP client (which itself runs an LLM
   agent). All inputs are validated against schemas before being
   passed to the bash cma subprocess. Argument injection into the
   subprocess is prevented by passing arguments as an argv array,
   never as a shell-interpolated string.
2. **Filesystem reads.** cma-mcp reads `$CMA_DIR/*.jsonl` files
   (default `~/.cma/`). It honors the `CMA_DIR` environment variable
   for redirection. cma-mcp does not read files outside this
   directory, and resource URIs do not accept arbitrary filesystem
   paths.
3. **Subprocess execution.** cma-mcp invokes the `cma` bash binary
   from the operator's `PATH`. Operators are responsible for
   confirming the `cma` binary on their `PATH` is the canonical one
   (run `cma --version` and verify the SHA against the
   [Clarethium/cma](https://github.com/Clarethium/cma) release).
4. **No network calls.** cma-mcp performs zero network I/O. No
   telemetry, no remote configuration, no external dependencies at
   runtime beyond the Python standard library.

## Out of scope

- Protection against a malicious MCP client. An operator who
  deliberately wires their MCP client to an untrusted server is
  outside this threat model. cma-mcp is the server; the trust
  boundary is the operator's local machine.
- Protection against malicious local processes. A process running
  with the operator's filesystem permissions can already read or
  modify `~/.cma/` directly. cma-mcp does not add or subtract from
  that surface.

## Supply-chain attestation

cma-mcp wheels uploaded to PyPI carry PEP 740 attestations: each
file is signed via Sigstore using the GitHub Actions identity of
the publishing workflow, and the signature is logged in the public
Sigstore transparency log (rekor.sigstore.dev). Adopters who want
to verify a downloaded wheel before installing can fetch the
provenance bundle from PyPI's integrity endpoint:

```
https://pypi.org/integrity/cma-mcp/<version>/<filename>/provenance
```

The returned JSON identifies the publisher as `Clarethium/cma`,
workflow `publish-mcp.yml`, environment `pypi`. Verification
tooling such as [`pypi-attestation-models`](https://pypi.org/project/pypi-attestation-models/)
can validate the bundle and confirm the wheel was produced by
this repository's release workflow rather than swapped at the
registry layer.

This protection is automatic for adopters using `pip install`
against a PyPI index that enforces attestation checks. It does
not change the threat model for cma-mcp itself (which still runs
locally and trusts its operator), but it tightens the chain
between this repository and the wheel an adopter actually
installs.
