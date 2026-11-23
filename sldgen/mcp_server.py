"""MCP (Model Context Protocol) server on stdio, for chat assistants without a shell.

Run `sldgen mcp` (or `sldgen-mcp`). Messages are JSON-RPC 2.0, one per line, on
stdin/stdout; logs go to stderr. No third-party packages. See docs/TOOLS.md.

The tools are thin wrappers over the CLI: `check_project` and `build_project` return the
same JSON as `sldgen check --json` and `sldgen build --json`, but take the project as an
inline JSON object instead of a file path.
"""

import contextlib
import json
import re
import sys
import traceback

from . import __version__
from .__main__ import SCHEMA, TEMPLATE, run_build, run_check
from .project import ProjectError, load_library, prepare_project

PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]  # newest first

INSTRUCTIONS = """\
Generates Malaysian Solar ATAP residential PV Single Line Diagrams (A3 PDF).
Workflow: list_library -> get_template -> fill the project object -> check_project ->
fix until "passed" -> build_project. Rules: never calculate ratings yourself (quote the
check output); never invent datasheet values; never fill in identity or certification
data (account holder, TNB account no., QP/CP names, certificate numbers) you weren't
given; only pass force=true when the user explicitly asks for a draft over errors. Ask
for missing information once, in one message. Defaults when not given: DC run 20 m,
AC run 15 m, one string per MPPT split as evenly as possible; tell the user you used them.
Reply with the PDF path, a short summary (kWp/kWac, strings, MCB/RCD, cable sizes,
total voltage drop), assumptions, every warning, and the submission fields left blank."""

PROJECT_ARG = {"type": "object", "description": "The project, as a JSON object in the shape of "
               "get_template / get_schema (not a file path)."}

TOOLS = [
    {"name": "list_library",
     "description": "List the PV modules and inverters in the datasheet library, with their keys and "
                    "full specs. Use a key as `pv_module` / `inverter` in the project. Entries with "
                    "verified=false print a PRELIMINARY warning on the sheet.",
     "inputSchema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["pv_module", "inverter"],
                  "description": "Only this kind (default: both)."}}}},
    {"name": "get_template",
     "description": "Return the blank project template (templates/project.json) to fill in.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_schema",
     "description": "Return the JSON Schema of the project object, with a description of every field.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "check_project",
     "description": "Run all sizing calculations and compliance checks on a project; writes no files. "
                    "result is 'incomplete' (see problems), 'failed' (issues with level 'error') or "
                    "'passed'. Same JSON as `sldgen check --json`.",
     "inputSchema": {"type": "object", "properties": {"project": PROJECT_ARG}, "required": ["project"]}},
    {"name": "build_project",
     "description": "Check, then draw the A3 SLD: writes PDF, PNG preview, SVG and design report to "
                    "output/<drawing_no>/ and returns their paths in files. Refuses to build over errors "
                    "unless force=true. Same JSON as `sldgen build --json`.",
     "inputSchema": {"type": "object", "properties": {
         "project": PROJECT_ARG,
         "force": {"type": "boolean", "default": False,
                   "description": "Build a watermarked 'DESIGN CHECK FAILED' draft even if the check "
                                  "fails. Only when the user explicitly asks for a draft."}},
         "required": ["project"]}},
]


class ToolError(Exception):
    pass


def _project(args):
    raw = args.get("project")
    if isinstance(raw, str):  # some hosts send objects as JSON text
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ToolError(f"project is not valid JSON: {e}")
    if not isinstance(raw, dict):
        raise ToolError("project must be a JSON object (the project file contents), not a path")
    try:
        return prepare_project(raw), None
    except ProjectError as e:
        return None, {"result": "incomplete", "problems": e.problems}


def _safe_name(text):
    """A drawing number usable as a folder/file name (no path separators or reserved characters)."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", str(text)).strip(" .-")
    return name or "untitled"


def tool_list_library(args):
    kind = args.get("kind")
    if kind not in (None, "pv_module", "inverter"):
        raise ToolError("kind must be 'pv_module' or 'inverter'")
    return {k: load_library(k) for k in ([kind] if kind else ["pv_module", "inverter"])}


def tool_get_template(args):
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def tool_get_schema(args):
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def tool_check_project(args):
    p, incomplete = _project(args)
    return incomplete or run_check(p)[1]


def tool_build_project(args):
    p, incomplete = _project(args)
    if incomplete:
        return incomplete
    rev = str(p["project"].get("revision", ""))
    if rev and _safe_name(rev) != rev:
        raise ToolError(f"project.revision {rev!r} can't be used in a file name; use e.g. 'A' or '1'")
    return run_build(p, _safe_name(p["project"].get("drawing_no") or "untitled"),
                     force=bool(args.get("force", False)))[1]


HANDLERS = {t["name"]: globals()[f"tool_{t['name']}"] for t in TOOLS}


def call_tool(name, args):
    if name not in HANDLERS:
        raise ToolError(f"unknown tool '{name}'")
    try:
        payload = HANDLERS[name](args or {})
    except ToolError as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": text}],
            "structuredContent": json.loads(text),
            "isError": isinstance(payload, dict) and payload.get("result") == "error"}


def handle(msg):
    """Handle one JSON-RPC message; return the response dict, or None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    method, params, mid = msg["method"], msg.get("params") or {}, msg.get("id")
    if "id" not in msg:  # notification (notifications/initialized, cancelled, ...): no reply
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            result = {"protocolVersion": wanted if wanted in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "sldgen", "title": "Solar ATAP SLD generator", "version": __version__},
                      "instructions": INSTRUCTIONS}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            if params.get("name") not in HANDLERS:
                return _error(mid, -32602, f"Unknown tool: {params.get('name')}")
            result = call_tool(params["name"], params.get("arguments"))
        else:
            return _error(mid, -32601, f"Method not found: {method}")
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return _error(mid, -32603, f"Internal error: {e}")
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    print(f"sldgen {__version__} MCP server on stdio", file=sys.stderr, flush=True)

    def send(obj):
        stdout.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            send(_error(None, -32700, f"Parse error: {e}"))
            continue
        # Anything a tool prints must not corrupt the protocol stream.
        with contextlib.redirect_stdout(sys.stderr):
            if isinstance(msg, list):
                replies = [r for r in map(handle, msg) if r is not None] if msg else [
                    _error(None, -32600, "Invalid Request")]
            else:
                replies = handle(msg)
        if replies:
            send(replies)
    return 0


def main():
    sys.exit(serve())


if __name__ == "__main__":
    main()
