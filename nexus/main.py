import os
import secrets
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from nexus.catalog import fetch_source, parse_markdown
from nexus.db import connect
from nexus.discovery import rank
from nexus.openapi import extract_operations
from nexus.policy import assess_operation
from nexus.reviews import change_status
from nexus.registry import register, transition
from nexus.gateway import plan
from nexus.execution_audit import record_plan, history
from nexus.egress import inspect_target

TOKEN = os.environ.get("NEXUS_ADMIN_TOKEN", "")

@asynccontextmanager
async def lifespan(app: FastAPI):
    with connect():
        pass
    yield

app = FastAPI(title="Kaliv Nexus", version="0.21.0", lifespan=lifespan)

def require_admin(authorization: str | None = Header(default=None)):
    if not TOKEN:
        raise HTTPException(503, "Admin API disabled: configure NEXUS_ADMIN_TOKEN")
    if not authorization or not authorization.startswith("Bearer ") or not secrets.compare_digest(authorization[7:], TOKEN):
        raise HTTPException(401, "Unauthorized")

class ImportResult(BaseModel):
    discovered: int
    inserted: int
    updated: int
    source: str

class Capability(BaseModel):
    id: str
    name: str
    url: str
    category: str
    description: str
    source: str
    status: str

class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(discovered|reviewed|approved|disabled)$")
    reason: str = Field(min_length=5, max_length=500)

@app.get("/healthz")
def health():
    return {"status": "ok", "service": "kaliv-nexus"}

@app.get("/v1/capabilities", response_model=list[Capability])
def capabilities(q: str = Query("", max_length=120), category: str = Query("", max_length=120),
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    sql = "SELECT id,name,url,category,description,source,status FROM capabilities WHERE 1=1"
    args = []
    if q:
        sql += " AND (name LIKE ? OR description LIKE ? OR url LIKE ?)"
        args.extend([f"%{q}%"] * 3)
    if category:
        sql += " AND category = ?"
        args.append(category)
    sql += " ORDER BY name LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    with connect() as db:
        return [dict(row) for row in db.execute(sql, args)]

@app.get("/v1/categories")
def categories():
    with connect() as db:
        return [dict(row) for row in db.execute(
            "SELECT category,COUNT(*) AS count FROM capabilities GROUP BY category ORDER BY count DESC")]

@app.get("/v1/capabilities/{capability_id}", response_model=Capability)
def capability(capability_id: str):
    with connect() as db:
        row = db.execute("SELECT id,name,url,category,description,source,status FROM capabilities WHERE id=?", (capability_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Not found")
    return dict(row)

@app.post("/v1/import", response_model=ImportResult, dependencies=[Depends(require_admin)])
async def import_catalog():
    try:
        markdown, source = await fetch_source()
        records = parse_markdown(markdown, source)
    except Exception as exc:
        raise HTTPException(502, f"Source import failed: {type(exc).__name__}") from exc
    inserted = updated = 0
    with connect() as db:
        for record in records:
            exists = db.execute("SELECT 1 FROM capabilities WHERE id=?", (record["id"],)).fetchone()
            if exists:
                db.execute("""UPDATE capabilities SET name=?, url=?, category=?, description=?, source=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                           (record["name"],record["url"],record["category"],record["description"],record["source"],record["id"]))
                updated += 1
            else:
                db.execute("""INSERT INTO capabilities (id,name,url,category,description,source,status)
                              VALUES (:id,:name,:url,:category,:description,:source,:status)""", record)
                inserted += 1
    return ImportResult(discovered=len(records), inserted=inserted, updated=updated, source=source)

@app.patch("/v1/capabilities/{capability_id}/status", response_model=Capability, dependencies=[Depends(require_admin)])
def update_status(capability_id: str, body: StatusUpdate):
    with connect() as db:
        try:
            change_status(db, capability_id, body.status, body.reason)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    return capability(capability_id)


@app.get("/v1/capabilities/{capability_id}/reviews", dependencies=[Depends(require_admin)])
def review_history(capability_id: str):
    with connect() as db:
        if not db.execute("SELECT 1 FROM capabilities WHERE id=?", (capability_id,)).fetchone():
            raise HTTPException(404, "Not found")
        return [dict(row) for row in db.execute(
            "SELECT id, previous_status, new_status, reason, actor, occurred_at FROM review_events WHERE capability_id=? ORDER BY id", (capability_id,))]


@app.get("/v1/discover")
def discover(q: str = Query(min_length=3, max_length=200), limit: int = Query(10, ge=1, le=50),
             approved_only: bool = True):
    """Rank catalog entries; never fetch or invoke third-party APIs."""
    with connect() as db:
        where = "WHERE status='approved'" if approved_only else ""
        records = [dict(row) for row in db.execute(
            f"SELECT id,name,url,category,description,source,status FROM capabilities {where}")]
    return {"query": q, "results": rank(q, records, limit), "execution_enabled": False}

@app.get("/v1/manifest", dependencies=[Depends(require_admin)])
def manifest():
    """Export reviewed capability metadata, not executable tools or credentials."""
    with connect() as db:
        rows = [dict(row) for row in db.execute(
            "SELECT id,name,url,category,description FROM capabilities WHERE status='approved' ORDER BY name")]
    return {"schema_version": 1, "capabilities": rows, "executable": False}


class OpenAPIImport(BaseModel):
    document: dict

@app.post("/v1/openapi/inspect", dependencies=[Depends(require_admin)])
def inspect_openapi(body: OpenAPIImport):
    """Parse a supplied OpenAPI 3 document without network requests or execution."""
    import json
    if len(json.dumps(body.document)) > 1_000_000:
        raise HTTPException(413, "Document exceeds 1 MB")
    try:
        operations = extract_operations(body.document)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for operation in operations:
        operation.update(assess_operation(operation, body.document))
    return {"operations": operations, "count": len(operations), "executable": False, "policy_version": 1}


@app.post("/v1/specs", dependencies=[Depends(require_admin)])
def register_spec(body: OpenAPIImport):
    try:
        with connect() as db:
            return register(db, body.document)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/v1/specs", dependencies=[Depends(require_admin)])
def list_specs():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT digest, created_at FROM api_specs ORDER BY created_at DESC")]

@app.get("/v1/specs/{digest}/operations", dependencies=[Depends(require_admin)])
def list_operations(digest: str):
    with connect() as db:
        if not db.execute("SELECT 1 FROM api_specs WHERE digest=?", (digest,)).fetchone():
            raise HTTPException(404, "Specification not found")
        return [dict(row) for row in db.execute("SELECT operation_id, method, path, name, risk_level, risk_flags, status FROM api_operations WHERE spec_digest=? ORDER BY method,path", (digest,))]

@app.patch("/v1/specs/{digest}/operations/{operation_id}/status", dependencies=[Depends(require_admin)])
def update_operation(digest: str, operation_id: str, body: StatusUpdate):
    with connect() as db:
        try:
            return transition(db, digest, operation_id, body.status, body.reason)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

@app.get("/v1/specs/{digest}/operations/{operation_id}/reviews", dependencies=[Depends(require_admin)])
def operation_reviews(digest: str, operation_id: str):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT previous_status,new_status,reason,occurred_at FROM operation_review_events WHERE spec_digest=? AND operation_id=? ORDER BY id", (digest, operation_id))]


class ExecutionPlanRequest(BaseModel):
    parameters: dict[str, str] = Field(default_factory=dict)

@app.get("/v1/specs/{digest}/operations/{operation_id}/plan-events", dependencies=[Depends(require_admin)])
def plan_events(digest: str, operation_id: str, limit: int = Query(100, ge=1, le=500)):
    with connect() as db:
        return history(db, digest, operation_id, limit)


@app.post("/v1/specs/{digest}/operations/{operation_id}/plan", dependencies=[Depends(require_admin)])
def plan_operation(digest: str, operation_id: str, body: ExecutionPlanRequest):
    """Audit and preview a request. No external HTTP requests are made."""
    with connect() as db:
        try:
            result = plan(db, digest, operation_id, body.parameters)
        except (LookupError, PermissionError, ValueError) as exc:
            outcome = ('missing' if isinstance(exc, LookupError) else
                       'denied' if isinstance(exc, PermissionError) else 'invalid')
            record_plan(db, digest, operation_id, body.parameters, outcome, type(exc).__name__)
            raise HTTPException({'missing': 404, 'denied': 403, 'invalid': 422}[outcome], str(exc)) from exc
        record_plan(db, digest, operation_id, body.parameters, 'allowed')
        return result


@app.post("/v1/specs/{digest}/operations/{operation_id}/preflight", dependencies=[Depends(require_admin)])
def preflight_operation(digest: str, operation_id: str, body: ExecutionPlanRequest):
    """Resolve DNS and evaluate egress eligibility; never execute HTTP."""
    with connect() as db:
        try:
            request_plan = plan(db, digest, operation_id, body.parameters)
            result = inspect_target(request_plan["target_url"])
        except (LookupError, PermissionError, ValueError) as exc:
            raise HTTPException(403 if isinstance(exc, PermissionError) else 422, str(exc)) from exc
    return {"operation_id": operation_id, **result}

@app.post('/v1/specs/{digest}/operations/{operation_id}/execute', dependencies=[Depends(require_admin)])
def execute_operation(digest: str, operation_id: str, body: ExecutionPlanRequest):
    """Opt-in GET execution; no credentials, redirects or write methods."""
    if os.environ.get('NEXUS_ENABLE_HTTP_EXECUTION') != 'true':
        raise HTTPException(503, 'HTTP execution disabled by default')
    from nexus.isolated import execute_isolated
    from nexus.limits import execution_limiter
    with connect() as db:
        try:
            request_plan = plan(db, digest, operation_id, body.parameters)
            execution_limiter.acquire()
            try:
                result = execute_isolated(request_plan['target_url'])
            finally:
                execution_limiter.release()
            record_plan(db, digest, operation_id, body.parameters, 'executed', str(result['status_code']))
            return result
        except (LookupError, PermissionError, ValueError, OSError, TimeoutError, RuntimeError) as exc:
            record_plan(db, digest, operation_id, body.parameters, 'execution_denied', type(exc).__name__)
            status = 404 if isinstance(exc, LookupError) else 403 if isinstance(exc, PermissionError) else 502
            raise HTTPException(status, str(exc) if status in (403, 404) else 'Upstream request failed') from exc

# v0.14: metadata-only unified discovery; no MCP server connection or tool execution.
from nexus.tools import normalize_mcp_manifest, registered_openapi_tools
from nexus.mcp_registry import register_manifest, change_tool_status, list_mcp_tools
class MCPManifest(BaseModel):
    tools: list[dict]

@app.post('/v1/mcp/inspect', dependencies=[Depends(require_admin)])
def inspect_mcp_manifest(manifest: MCPManifest):
    try:
        return {'tools': normalize_mcp_manifest(manifest.model_dump()), 'executable': False}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get('/v1/tools', dependencies=[Depends(require_admin)])
def list_unified_tools(approved_only: bool = True):
    with connect() as db:
        return {'tools': registered_openapi_tools(db, approved_only) + list_mcp_tools(db, approved_only), 'executable': False}

@app.post('/v1/mcp/manifests', dependencies=[Depends(require_admin)])
def save_mcp_manifest(manifest: MCPManifest):
    try:
        with connect() as db:
            return register_manifest(db, manifest.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get('/v1/mcp/manifests', dependencies=[Depends(require_admin)])
def get_mcp_manifests():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT digest,created_at FROM mcp_manifests ORDER BY created_at DESC')]

@app.get('/v1/mcp/manifests/{digest}/tools', dependencies=[Depends(require_admin)])
def get_mcp_tools(digest: str):
    with connect() as db:
        if not db.execute('SELECT 1 FROM mcp_manifests WHERE digest=?', (digest,)).fetchone():
            raise HTTPException(404, 'Manifest not found')
        return [t for t in list_mcp_tools(db, False) if t['id'].startswith('mcp:' + digest + ':')]

@app.patch('/v1/mcp/manifests/{digest}/tools/{name}/status', dependencies=[Depends(require_admin)])
def review_mcp_tool(digest: str, name: str, body: StatusUpdate):
    try:
        with connect() as db:
            return change_tool_status(db, digest, name, body.status, body.reason)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get('/v1/mcp/manifests/{digest}/tools/{name}/reviews', dependencies=[Depends(require_admin)])
def mcp_tool_reviews(digest: str, name: str):
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT previous_status,new_status,reason,occurred_at FROM mcp_tool_reviews WHERE manifest_digest=? AND name=? ORDER BY id', (digest, name))]


# v0.16: inert MCP connection profiles. No outbound connections are permitted.
from nexus.mcp_connections import register_connection, list_connections

class MCPConnectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    url: str = Field(min_length=1, max_length=2048)
    manifest_digest: str = Field(pattern=r'^[a-f0-9]{64}$')

@app.post('/v1/mcp/connections', dependencies=[Depends(require_admin)], status_code=201)
def create_mcp_connection(body: MCPConnectionRequest):
    try:
        with connect() as db:
            return register_connection(db, body.name, body.url, body.manifest_digest)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get('/v1/mcp/connections', dependencies=[Depends(require_admin)])
def get_mcp_connections():
    with connect() as db:
        return {'connections': list_connections(db), 'execution_enabled': False}

# v0.17: protocol validation only; no live transport or tool invocation.
from nexus.mcp_protocol import inspect_message, session_transition

class MCPEnvelope(BaseModel):
    message: dict

class MCPSessionTransition(BaseModel):
    state: str = Field(pattern='^(new|initializing|initialized|ready)$')
    message: dict

@app.post('/v1/mcp/protocol/inspect', dependencies=[Depends(require_admin)])
def inspect_mcp_protocol(body: MCPEnvelope):
    try:
        return inspect_message(body.message)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post('/v1/mcp/protocol/transition', dependencies=[Depends(require_admin)])
def transition_mcp_protocol(body: MCPSessionTransition):
    try:
        return {'state': session_transition(body.state, body.message), 'connected': False}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

# v0.18: offline Streamable HTTP response inspection; outbound MCP remains disabled.
from nexus.mcp_transport import inspect_http_response
import base64
import binascii

class MCPTransportInspection(BaseModel):
    content_type: str = Field(min_length=1, max_length=128)
    body_base64: str = Field(min_length=1, max_length=1500000)

@app.post('/v1/mcp/transport/inspect', dependencies=[Depends(require_admin)])
def inspect_mcp_transport(body: MCPTransportInspection):
    try:
        raw = base64.b64decode(body.body_base64, validate=True)
        return inspect_http_response(body.content_type, raw)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, str(exc)) from exc


from nexus.mcp_sessions import create_session, get_session, transition_session

class MCPSessionCreate(BaseModel):
    connection_name: str = Field(min_length=1, max_length=128)
    ttl_seconds: int = Field(default=300, ge=1, le=3600)

class MCPSessionUpdate(BaseModel):
    state: str = Field(pattern="^(initializing|initialized|ready|closed)$")

@app.post('/v1/mcp/sessions', dependencies=[Depends(require_admin)], status_code=201)
def create_mcp_session(body: MCPSessionCreate):
    try:
        with connect() as db:
            return create_session(db, body.connection_name, body.ttl_seconds)
    except KeyError:
        raise HTTPException(404, 'Connection not found')

@app.get('/v1/mcp/sessions/{session_id}', dependencies=[Depends(require_admin)])
def read_mcp_session(session_id: str):
    try:
        with connect() as db:
            return get_session(db, session_id)
    except KeyError:
        raise HTTPException(404, 'Session not found')

@app.patch('/v1/mcp/sessions/{session_id}', dependencies=[Depends(require_admin)])
def update_mcp_session(session_id: str, body: MCPSessionUpdate):
    try:
        with connect() as db:
            return transition_session(db, session_id, body.state)
    except KeyError:
        raise HTTPException(404, 'Session not found')
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

# v0.20: offline handshake transcript validation, no live MCP transport.
from nexus.mcp_handshake import validate_handshake

class MCPHandshakeTranscript(BaseModel):
    messages: list[dict] = Field(min_length=3, max_length=3)

@app.post('/v1/mcp/handshake/validate', dependencies=[Depends(require_admin)])
def validate_mcp_handshake(body: MCPHandshakeTranscript):
    try:
        return validate_handshake(body.messages)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

# Offline comparison only: never contacts the MCP server or changes approvals.
from nexus.mcp_reconcile import reconcile_discovery

class MCPReconcileRequest(BaseModel):
    discovery: dict

@app.post('/v1/mcp/sessions/{session_id}/reconcile', dependencies=[Depends(require_admin)])
def reconcile_mcp_session(session_id: str, body: MCPReconcileRequest):
    with connect() as db:
        try:
            return reconcile_discovery(db, session_id, body.discovery)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
