"""
MCP tool input schemas and metadata.

This module is the single source of truth for cma-mcp's tool surface.
Each tool entry mirrors a bash cma primitive (see cma's DESIGN.md);
the schema describes the input shape an MCP client passes; the
description teaches the agent both how to invoke the tool and when
to invoke it (you say X, OR the agent itself recognizes a
capture-worthy moment).

Field-name discipline: snake_case in MCP schema (e.g.,
`applies_when`, `revisit_when`, `miss_id`). cma_subprocess translates
these to bash cma's CLI flag form (`--applies-when`, `--revisit-when`,
`--miss-id`).

Surface labels are open-ended. cma's data substrate stores `surface`
as an opaque string; the canonical examples (`auth`, `db`, `docs`,
`ui`, `infra`, `general`, `git`) are listed in the field description
but you may pass any short label that fits your work.

`fm` (failure-mode) is opaque per DECISIONS AD-006. cma-mcp does not
bundle a failure-mode catalog. Whatever methodology you practice owns
the vocabulary; pass its tag through as opaque data.
"""

from __future__ import annotations

from typing import Any


# ── shared schema fragments ─────────────────────────────────────────

_SURFACE_DESCRIPTION = (
    "Surface label (the domain area). Canonical values used by the cma "
    "reference implementation: auth, db, docs, ui, infra, general, git. "
    "Custom values are accepted; cma stores the surface as an opaque "
    "string."
)

_FM_DESCRIPTION = (
    "Failure-mode tag, opaque to cma. When you practice a "
    "methodology with a canonical failure-mode catalog, pass that "
    "catalog's tag here as a string. cma-mcp does not "
    "bundle a catalog "
    "itself. If unset, cma falls back to your "
    "CMA_FM_CLASSIFIER plugin (if configured) or stores the miss "
    "with no fm."
)


# ── input size bounds ───────────────────────────────────────────────
#
# Every string field carries an upper bound so an adversarial or
# malfunctioning MCP client cannot push payloads past the OS ARG_MAX
# limit (typically ~2 MiB on Linux x86_64) when cma-mcp shells out to
# bash cma. The bounds below leave headroom for argv overhead and
# multiple fields per call.
#
# MAX_DESCRIPTION   one-line capture summaries. 4 KiB is generous.
# MAX_TEXTURE       multi-line excerpts. 64 KiB covers realistic
#                   conversation excerpts; longer payloads should be
#                   stored externally and referenced by path.
# MAX_SHORT_FIELD   labels, predicates, IDs. 2 KiB.
MAX_DESCRIPTION = 4096
MAX_TEXTURE = 65536
MAX_SHORT_FIELD = 2048


def _surface_field() -> dict:
    return {
        "type": "string",
        "maxLength": MAX_SHORT_FIELD,
        "description": _SURFACE_DESCRIPTION,
    }


def _fm_field() -> dict:
    return {
        "type": "string",
        "maxLength": MAX_SHORT_FIELD,
        "description": _FM_DESCRIPTION,
    }


# ── per-tool definitions ────────────────────────────────────────────

CMA_MISS = {
    "name": "cma_miss",
    "title": "Record a miss",
    "description": (
        "Capture a failure: a specific moment where work fell short of "
        "intent and is likely to recur. Wraps `cma miss`.\n\n"
        "Invoke when (a) you say 'record a miss', 'log this', "
        "'this was wrong', or similar, OR (b) you yourself notice a "
        "miss worth surfacing in future similar work.\n\n"
        "Description should preserve enough specifics that the same "
        "failure-shape would be recognizable next time it appears. "
        "Generic captures ('I made a mistake') are useless; specific "
        "captures ('I claimed verified without testing the cross-tenant "
        "write path') fire as warnings later via cma's surface-time "
        "matching.\n\n"
        "Pass `files` as the path just edited. The next edit shows "
        "this miss only when that file's basename appears there. "
        "Pass `corrected` as the action that replaced the failure. "
        "The next edit shows that line and does not show `intended`."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "What failed, in your own words. Phrase "
                    "actively ('Treated X as Y without verifying') "
                    "rather than passively. Specific enough that the "
                    "same shape of failure would be recognizable next "
                    "time."
                ),
            },
            "surface": _surface_field(),
            "fm": _fm_field(),
            "files": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Path of the file just edited, or several paths "
                    "separated by commas. The next edit shows this "
                    "miss when the file's basename appears here. "
                    "Without it, that edit shows nothing."
                ),
            },
            "intended": {
                "type": "string",
                "maxLength": MAX_TEXTURE,
                "description": (
                    "What was about to happen. Kept for the behavior "
                    "view. The next edit does not show this line."
                ),
            },
            "corrected": {
                "type": "string",
                "maxLength": MAX_TEXTURE,
                "description": (
                    "The action that replaced the failure. The next "
                    "matching edit shows this as an Instead line. "
                    "Pass it when you know what to do instead."
                ),
            },
            "excerpt": {
                "type": "string",
                "maxLength": MAX_TEXTURE,
                "description": (
                    "Multi-line excerpt of the conversation or session "
                    "that produced the miss. Newlines and quotes are "
                    "preserved through bash cma's JSON encoding."
                ),
            },
        },
    },
}

CMA_DECISION = {
    "name": "cma_decision",
    "title": "Record an architectural or strategic decision",
    "description": (
        "Capture a non-trivial choice you want surfaced in "
        "future similar work. Wraps `cma decision`.\n\n"
        "Format: 'TOPIC: choice (rationale)'. The TOPIC is the decision "
        "domain; the choice is what was decided; the rationale is the "
        "why.\n\n"
        "Invoke when (a) you articulate a decision, OR "
        "(b) you yourself are about to commit to or recommend a "
        "non-trivial choice (pattern, architecture, security stance, "
        "configuration philosophy) whose rationale matters more than "
        "its mechanics.\n\n"
        "Read the cma://decisions resource first to avoid duplicating "
        "an existing decision. Implementation tweaks, bug fixes, "
        "polish, refactors are not decisions.\n\n"
        "Pass `applies_when` to set the predicate cma matches against "
        "context keywords at surface time. A decision with "
        "applies_when='auth db' surfaces whenever the current action's "
        "surface or file path contains 'auth' or 'db', closing the "
        "decision-surfacing loop."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 15,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "TOPIC: choice (rationale). Real-world decisions "
                    "like 'GIT: Commit only' (16 chars) are valid."
                ),
            },
            "surface": _surface_field(),
            "applies_when": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Predicate matched against context keywords at "
                    "surface time. Coarse predicates (surface name, "
                    "file pattern) are sufficient; cma performs "
                    "substring matching."
                ),
            },
        },
    },
}

CMA_REJECT = {
    "name": "cma_reject",
    "title": "Record an explicit rejection",
    "description": (
        "Capture an option considered and ruled out. Survives session "
        "compaction and prevents silently rebuilding what was "
        "deliberately not built. Wraps `cma reject`.\n\n"
        "Format: 'OPTION: reason for elimination'.\n\n"
        "Invoke when (a) you state a rejection, OR (b) you "
        "yourself recognize that you have just eliminated an option "
        "whose rationale is non-obvious enough that a future you "
        "(or another model) might rebuild it without context.\n\n"
        "Read the cma://rejections resource first to see what is "
        "already eliminated.\n\n"
        "Pass `revisit_when` to name the trigger that would warrant "
        "reconsidering the rejection ('if performance becomes "
        "critical', 'if Python 4 ships', etc.)."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": "OPTION: reason for elimination.",
            },
            "surface": _surface_field(),
            "revisit_when": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Trigger that would warrant reconsidering this "
                    "rejection. Surfaces alongside the rejection so "
                    "you see the reopen condition in context."
                ),
            },
        },
    },
}

CMA_PREVENTED = {
    "name": "cma_prevented",
    "title": "Record a prevention catch",
    "description": (
        "Record a note that you stopped because of a prior warning. "
        "The note is self-attested. It is not a measurement that the "
        "warning changed a later edit. "
        "Wraps `cma prevented`.\n\n"
        "Invoke immediately after the catch, while the chain (warning "
        "→ recognition → different choice) is still legible. "
        "Triggered by either (a) a request from you, OR (b) the agent's own "
        "recognition that it almost did something a warning had "
        "named, and it stopped.\n\n"
        "Description names what was almost done versus what was done "
        "instead. If the warning came from a specific prior miss, "
        "pass that miss's id as `miss_id` so cma can compute the "
        "miss's prevention rate."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "What was almost done versus what was done "
                    "instead. The chain is most useful when explicit."
                ),
            },
            "miss_id": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "ID of the original miss this prevention links to "
                    "(format: YYYYMMDD-HHMMSS-<8-hex>). Lets cma "
                    "compute the miss's prevention rate."
                ),
            },
            "warning_id": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "ID of the surface event whose warning was heeded. "
                    "Optional; cma uses it to track which warnings "
                    "actually catch repeats."
                ),
            },
        },
    },
}

CMA_DISTILL = {
    "name": "cma_distill",
    "title": "Promote, retire, or review distilled learnings",
    "description": (
        "Operate on cma's core-learnings layer: promote a captured "
        "pattern to permanent surfacing, retire one that no longer "
        "applies, or preview the patterns that have accumulated since "
        "the last distillation. Wraps `cma distill`.\n\n"
        "Three modes:\n"
        "- `default`: promote a learning. Pass `description` (the "
        "  distilled rule), optional `scope` (project / language / "
        "  general; default general) and optional `surface`.\n"
        "- `retire`: mark matching core learnings as retired. Pass "
        "  `pattern` (substring matched against existing learnings).\n"
        "- `review`: read-only preview of patterns that would warrant "
        "  distillation. No other arguments.\n\n"
        "Invoke when you articulate a distilled learning, "
        "or when reviewing recurring miss patterns and wanting to "
        "promote one to permanent surfacing."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["mode"],
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["default", "retire", "review"],
                "description": (
                    "Operation mode. `default` promotes; `retire` "
                    "removes from active surfacing; `review` previews."
                ),
            },
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "Distilled rule (mode=default only). Phrased as a "
                    "permanent rule, not a one-off observation."
                ),
            },
            "pattern": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Substring pattern (mode=retire only). Matches "
                    "against existing core learnings; matches are "
                    "marked retired."
                ),
            },
            "scope": {
                "type": "string",
                "enum": ["project", "language", "general"],
                "description": (
                    "Scope of the learning (mode=default only). "
                    "Defaults to 'general'."
                ),
            },
            "surface": _surface_field(),
        },
    },
}

CMA_SURFACE = {
    "name": "cma_surface",
    "title": "Surface prior captures for a file or a surface",
    "description": (
        "Show prior captures for a file or a surface. A miss matches "
        "when the file filter is that file's own name, or when "
        "the surface matches exactly. A longer name that only contains "
        "the filter does not match. A decision also matches when a "
        "word in applies_when appears in the filter. Wraps `cma surface`.\n\n"
        "This call has a side effect: cma writes a record to "
        "surface_events.jsonl with the filters used and the matched "
        "captures. The leak-detection view (cma_stats view=leaks) "
        "later joins these events against subsequent misses to flag "
        "failures that occurred despite a relevant warning being "
        "surfaced. Disabling the log defeats leak detection, so cma-mcp "
        "does not expose the --no-log flag.\n\n"
        "Invoke before an edit when you want prior notes for that file "
        "or surface. Without arguments, this returns the newest records "
        "in the data directory. It does not look at the working "
        "directory. Pass file or surface to narrow it."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "surface": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Filter by domain area. Matches captures whose "
                    "stored surface equals this value, or whose "
                    "applies_when predicate (decisions only) "
                    "substring-matches it."
                ),
            },
            "file": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Filter by file path or basename. Matches a capture "
                    "whose stored path has this file's own name."
                ),
            },
            "type": {
                "type": "string",
                "enum": ["miss", "decision", "rejection", "prevention"],
                "description": "Filter by capture type.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of results. Default 10.",
            },
        },
    },
}

CMA_STATS = {
    "name": "cma_stats",
    "title": "Counts of the notes you recorded",
    "description": (
        "Show the counts of notes recorded over a trailing window. "
        "Wraps `cma stats`.\n\n"
        "Views:\n"
        "- `default`: summary (totals, recent activity, top surfaces, "
        "  top failure shapes, prevention rate, recurrence trends).\n"
        "- `evidence`: a count of notes in a trailing 30-day window, "
        "  evidenced preventions over those preventions plus leaks. "
        "  It is not a measurement that a later edit changed.\n"
        "- `leaks`: a later miss whose surface and fm both match a "
        "  capture that was already shown. There is no warning-weight "
        "  field.\n"
        "- `recurrence`: failure shapes ordered by how often the same "
        "  surface and fm were recorded again.\n"
        "- `preventions`: notes recorded with `cma prevented`, with "
        "  linked misses. Self-attested.\n"
        "- `rejections`: active rejections with surfaces, ages, and "
        "  revisit triggers.\n"
        "- `behavior`: the intended and corrected lines you stored, "
        "  grouped by surface and fm. This is not a measurement that "
        "  a warning changed a later edit.\n\n"
        "Invoke to read those counts. The on/off comparison in "
        "docs/EVALUATION.md has not been run."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "view": {
                "type": "string",
                "enum": [
                    "default",
                    "evidence",
                    "leaks",
                    "recurrence",
                    "preventions",
                    "rejections",
                    "behavior",
                ],
                "description": (
                    "Which view to compute. Defaults to 'default' "
                    "(summary). The 'evidence' view composes "
                    "preventions and leaks into a prevention-rate "
                    "signal over a trailing 30-day window."
                ),
            },
            "window": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3650,
                "description": (
                    "Trailing window in days for the evidence view. "
                    "Defaults to 30. Ignored when view is not "
                    "'evidence'."
                ),
            },
        },
    },
}


# Shared output schema. Every cma-mcp tool returns the same three-section
# payload, so the shape is declared once and attached to each tool below.
# 2025-06-18+ clients use it to validate `structuredContent`; older clients
# ignore the field, so it is backward-compatible.
THREE_SECTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Every cma-mcp tool returns the same three-section payload: the "
        "tool's data, guidance for relaying it, and provenance."
    ),
    "properties": {
        "analysis": {
            "type": "object",
            "description": "Tool-specific result data and the raw cma stdout.",
        },
        "agent_guidance": {
            "type": "object",
            "description": (
                "How to relay the result: what the tool does, what it does "
                "not do, and how to cite it faithfully."
            ),
            "properties": {
                "what_this_tool_does": {"type": "string"},
                "what_this_tool_does_not_do": {"type": "string"},
                "how_to_cite_faithfully": {"type": "string"},
            },
        },
        "provenance": {
            "type": "object",
            "description": "Reproducibility metadata for the call.",
            "properties": {
                "server_name": {"type": "string"},
                "server_version": {"type": "string"},
                "protocol_version": {"type": "string"},
                "license": {"type": "string"},
                "cost_usd": {"type": "number"},
                "citation": {"type": "string"},
                "deterministic": {"type": "boolean"},
                "timestamp": {"type": "string"},
            },
        },
    },
    "required": ["analysis", "agent_guidance", "provenance"],
}


# Ordered list (the order defines the sequence in tools/list response).
TOOLS: list[dict[str, Any]] = [
    CMA_MISS,
    CMA_DECISION,
    CMA_REJECT,
    CMA_PREVENTED,
    CMA_DISTILL,
    CMA_SURFACE,
    CMA_STATS,
]

# Every cma tool returns the same three-section payload; attach the shared
# output schema to each so tools/list advertises it uniformly.
for _tool in TOOLS:
    _tool["outputSchema"] = THREE_SECTION_OUTPUT_SCHEMA


# ── resources ─────────────────────────────────────────────────────

RESOURCES: list[dict[str, Any]] = [
    {
        "uri": "cma://decisions",
        "name": "decisions",
        "title": "Active decisions in scope",
        "description": (
            "Decisions you have captured. No project filter. The "
            "newest 30 whose timestamp is within 180 days."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "cma://rejections",
        "name": "rejections",
        "title": "Active rejections",
        "description": (
            "Options you have rejected and the reason. No project "
            "filter. The newest 30 whose timestamp is within 30 days."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "cma://core",
        "name": "core",
        "title": "Active core learnings",
        "description": (
            "Distilled learnings promoted via cma_distill. Retired "
            "learnings are removed. The newest 30 active records."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "cma://stats",
        "name": "stats",
        "title": "Compound-practice statistics summary",
        "description": (
            "Default stats summary. For specific views (leaks, "
            "recurrence, preventions, rejections, behavior), call the "
            "cma_stats tool with the view argument."
        ),
        "mimeType": "application/json",
    },
]


def get_tool(name: str) -> dict[str, Any] | None:
    """Look up a tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_resource(uri: str) -> dict[str, Any] | None:
    """Look up a resource definition by URI."""
    for res in RESOURCES:
        if res["uri"] == uri:
            return res
    return None
