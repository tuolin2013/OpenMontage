"""GET  /api/project/{id}/checkpoint?stage=script  — read checkpoint JSON.
PATCH /api/project/{id}/checkpoint               — save human edits to artifact.
POST  /api/project/{id}/approve                  — approve awaiting_human gate.
POST  /api/project/{id}/abort                    — abort in-progress or awaiting stage.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

ROOT = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = ROOT / "projects"
PIPELINE_DIR = ROOT / "pipelines"


# ── Request bodies ────────────────────────────────────────────

class PatchCheckpointRequest(BaseModel):
    stage: str
    artifact_key: str          # e.g. "script", "scene_plan"
    artifact_data: dict[str, Any]   # the edited JSON payload


class ApproveRequest(BaseModel):
    stage: str
    notes: str = ""
    auto_run_next: bool = True   # if True, immediately start the next stage


class AbortRequest(BaseModel):
    reason: str = "User aborted via Web UI"


# ── Routes ────────────────────────────────────────────────────

@router.get("/{project_id}/checkpoint")
async def get_checkpoint(
    project_id: str,
    stage: Optional[str] = Query(None, description="Stage name, e.g. script. Omit for latest."),
):
    """
    Return the checkpoint JSON for a given stage.
    If stage is omitted, returns the most recent checkpoint.
    """
    if stage:
        cp_path = _cp_path(project_id, stage)
        if not cp_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No checkpoint found for project '{project_id}' stage '{stage}'"
            )
        return JSONResponse(content=_load(cp_path))
    else:
        cp_dir = PIPELINE_DIR / project_id
        if not cp_dir.exists():
            raise HTTPException(status_code=404, detail=f"No checkpoints found for '{project_id}'")
        files = sorted(cp_dir.glob("checkpoint_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            raise HTTPException(status_code=404, detail="No checkpoints found")
        return JSONResponse(content=_load(files[0]))


@router.patch("/{project_id}/checkpoint")
async def patch_checkpoint(project_id: str, body: PatchCheckpointRequest):
    """
    Save human-edited artifact data back into a checkpoint.

    The frontend edits the script / scene_plan / etc. in the JSON editor,
    then calls this endpoint. The new payload overwrites the artifact key
    inside the checkpoint file on disk — no agent re-run needed.
    """
    cp_path = _cp_path(project_id, body.stage)
    if not cp_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint not found: {project_id}/{body.stage}"
        )

    data = _load(cp_path)
    if "artifacts" not in data or not isinstance(data["artifacts"], dict):
        data["artifacts"] = {}

    data["artifacts"][body.artifact_key] = body.artifact_data
    data["human_edit"] = {
        "edited_at": datetime.now(timezone.utc).isoformat(),
        "edited_key": body.artifact_key,
        "source": "web_ui",
    }

    # Also persist the artifact as a standalone file
    artifact_path = PROJECTS_DIR / project_id / "artifacts" / f"{body.artifact_key}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(body.artifact_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return JSONResponse(content={
        "success": True,
        "project_id": project_id,
        "stage": body.stage,
        "artifact_key": body.artifact_key,
    })


@router.post("/{project_id}/approve")
async def approve_stage(project_id: str, body: ApproveRequest):
    """
    Mark an awaiting_human checkpoint as completed and optionally launch next stage.
    """
    cp_path = _cp_path(project_id, body.stage)
    if not cp_path.exists():
        raise HTTPException(status_code=404, detail=f"Checkpoint not found: {body.stage}")

    data = _load(cp_path)
    if data.get("status") != "awaiting_human":
        raise HTTPException(
            status_code=400,
            detail=f"Stage is not awaiting human approval (current status: {data.get('status')})"
        )

    data["status"] = "completed"
    data["human_approved"] = True
    data["human_approval"] = {
        "approved": True,
        "notes": body.notes,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "source": "web_ui",
    }
    cp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    next_started = False
    next_stage = None
    if body.auto_run_next:
        meta = _read_meta(project_id)
        pipeline = meta.get("pipeline", "ecommerce-promo")
        brief = _read_brief(project_id)

        from lib.checkpoint import get_next_stage, write_checkpoint
        from lib.pipeline_runner import start_agent_for_project

        next_stage = get_next_stage(PIPELINE_DIR, project_id, pipeline)
        if next_stage:
            next_started = start_agent_for_project(project_id, pipeline, brief, stage=next_stage)
            if next_started:
                write_checkpoint(
                    pipeline_dir=PIPELINE_DIR,
                    project_id=project_id,
                    stage=next_stage,
                    status="in_progress",
                    artifacts={},
                    pipeline_type=pipeline,
                )

    return JSONResponse(content={
        "success": True,
        "stage": body.stage,
        "status": "completed",
        "next_stage": next_stage,
        "next_started": next_started,
    })


@router.post("/{project_id}/abort")
async def abort_project(project_id: str, body: AbortRequest = AbortRequest()):
    """Abort the most recent in-progress or awaiting_human stage."""
    cp_dir = PIPELINE_DIR / project_id
    if not cp_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    aborted_stage = None
    for f in sorted(cp_dir.glob("checkpoint_*.json"), reverse=True):
        data = _load(f)
        if data.get("status") in ("in_progress", "awaiting_human"):
            data["status"] = "failed"
            data["abort"] = {
                "reason": body.reason,
                "aborted_at": datetime.now(timezone.utc).isoformat(),
                "source": "web_ui",
            }
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            aborted_stage = data.get("stage")
            break

    if not aborted_stage:
        return JSONResponse(content={
            "success": False,
            "detail": "No active stage found to abort",
        })

    return JSONResponse(content={
        "success": True,
        "project_id": project_id,
        "aborted_stage": aborted_stage,
    })


@router.get("/{project_id}/log")
async def get_agent_log(project_id: str, tail: int = Query(200, ge=1, le=5000)):
    """Return the last N lines of the agent.log for a project."""
    log_path = PROJECTS_DIR / project_id / "agent.log"
    if not log_path.exists():
        return JSONResponse(content={"lines": [], "exists": False})
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return JSONResponse(content={"lines": lines[-tail:], "exists": True, "total": len(lines)})


# ── Helpers ───────────────────────────────────────────────────

def _cp_path(project_id: str, stage: str) -> Path:
    return PIPELINE_DIR / project_id / f"checkpoint_{stage}.json"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read {path.name}: {exc}")


def _read_meta(project_id: str) -> dict:
    p = PROJECTS_DIR / project_id / "meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_brief(project_id: str) -> str:
    p = PROJECTS_DIR / project_id / "brief.md"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return _read_meta(project_id).get("brief", "")
