"""POST /api/project/{id}/run_stage — trigger a specific pipeline stage.

The stage parameter accepts: script, scene_plan, assets, compose
(plus any other stage defined in the pipeline manifest).

Identity-preservation inputs (LoRA ID, ControlNet weight, transparent PNG)
are read from meta.json and injected into the agent prompt automatically —
the frontend does not need to re-submit them on every stage call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

ROOT = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = ROOT / "projects"
PIPELINE_DIR = ROOT / "pipelines"


class RunStageRequest(BaseModel):
    stage: Optional[str] = None   # None → auto-detect next stage
    # Override identity-preservation at call time (optional)
    lora_model_path: Optional[str] = None
    controlnet_weight: Optional[float] = None
    transparent_png_path: Optional[str] = None


@router.post("/{project_id}/run_stage")
async def run_stage(project_id: str, body: RunStageRequest = RunStageRequest()):
    """
    Trigger a single pipeline stage for the given project.

    - If body.stage is provided, that exact stage is executed.
    - If body.stage is None, the next pending stage is auto-detected.
    - Identity-preservation overrides in the request body are merged with
      whatever was stored in meta.json at project creation time.
    """
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    meta = _read_meta(project_dir)
    pipeline = meta.get("pipeline", "ecommerce-promo")
    brief_text = _read_brief(project_dir)

    # Merge identity-preservation from meta + request override
    lora = body.lora_model_path or meta.get("lora_model_path")
    cw = body.controlnet_weight if body.controlnet_weight is not None else meta.get("controlnet_weight")
    png = body.transparent_png_path or meta.get("transparent_png_path")

    # Append identity-preservation annotations to brief if present
    brief_text = _annotate_brief(brief_text, lora, cw, png)

    # Resolve the target stage
    from lib.checkpoint import get_next_stage

    if body.stage:
        target_stage = body.stage
    else:
        target_stage = get_next_stage(PIPELINE_DIR, project_id, pipeline)

    if not target_stage:
        return JSONResponse(content={
            "status": "all_complete",
            "message": "All stages for this project have been completed.",
            "project_id": project_id,
        })

    # Check for in-progress guard: refuse to double-start
    in_progress_stage = _get_in_progress_stage(project_id)
    if in_progress_stage and in_progress_stage != target_stage:
        raise HTTPException(
            status_code=409,
            detail=f"Stage '{in_progress_stage}' is already in progress. Wait for it to finish.",
        )

    from lib.pipeline_runner import start_agent_for_project
    from lib.checkpoint import write_checkpoint

    started = start_agent_for_project(project_id, pipeline, brief_text, stage=target_stage)
    if started:
        write_checkpoint(
            pipeline_dir=PIPELINE_DIR,
            project_id=project_id,
            stage=target_stage,
            status="in_progress",
            artifacts={},
            pipeline_type=pipeline,
        )

    return JSONResponse(content={
        "status": "started" if started else "failed_to_start",
        "project_id": project_id,
        "stage": target_stage,
        "pipeline": pipeline,
        "identity_preservation": {
            "lora_model_path": lora,
            "controlnet_weight": cw,
            "transparent_png_path": png,
        },
    })


@router.get("/{project_id}/status")
async def project_status(project_id: str):
    """Return the current stage + checkpoint summary for a project."""
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    meta = _read_meta(project_dir)
    pipeline = meta.get("pipeline", "ecommerce-promo")
    checkpoints = _read_checkpoints(project_id)
    overall = _derive_status(checkpoints)
    current_stage = None
    for cp in reversed(checkpoints):
        if cp.get("status") in ("in_progress", "awaiting_human"):
            current_stage = cp.get("stage")
            break
    if current_stage is None and checkpoints:
        current_stage = checkpoints[-1].get("stage")

    from lib.checkpoint import get_next_stage

    next_stage = get_next_stage(PIPELINE_DIR, project_id, pipeline)

    return JSONResponse(content={
        "project_id": project_id,
        "pipeline": pipeline,
        "status": overall,
        "current_stage": current_stage,
        "next_stage": next_stage,
        "checkpoints": checkpoints,
        "meta": meta,
    })


# ── Internal helpers ──────────────────────────────────────────

def _read_meta(project_dir: Path) -> dict:
    p = project_dir / "meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_brief(project_dir: Path) -> str:
    p = project_dir / "brief.md"
    if p.exists():
        return p.read_text(encoding="utf-8")
    meta = _read_meta(project_dir)
    return meta.get("brief", "")


def _annotate_brief(brief: str, lora, cw, png) -> str:
    annotations = []
    if lora:
        annotations.append(f"[IDENTITY] LoRA 模型路径: {lora}")
    if cw is not None:
        annotations.append(f"[IDENTITY] ControlNet 权重: {cw}")
    if png:
        annotations.append(f"[IDENTITY] 产品透明底图: {png}")
    if annotations:
        brief = brief + "\n\n" + "\n".join(annotations)
    return brief


def _read_checkpoints(project_id: str) -> list:
    cp_dir = PIPELINE_DIR / project_id
    if not cp_dir.exists():
        return []
    result = []
    for f in sorted(cp_dir.glob("checkpoint_*.json")):
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


def _derive_status(checkpoints: list) -> str:
    if not checkpoints:
        return "created"
    statuses = [cp.get("status", "") for cp in checkpoints]
    if "failed" in statuses:
        return "failed"
    if "awaiting_human" in statuses:
        return "awaiting_human"
    if "in_progress" in statuses:
        return "in_progress"
    if all(s == "completed" for s in statuses):
        return "completed"
    return "in_progress"


def _get_in_progress_stage(project_id: str) -> Optional[str]:
    for cp in _read_checkpoints(project_id):
        if cp.get("status") == "in_progress":
            return cp.get("stage")
    return None
