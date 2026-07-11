"""POST /api/project/create — scaffold a new project and optionally start first stage.

Accepts product metadata, LoRA model path, and a transparent PNG asset path
so the assets/compose stages can leverage identity-preservation inputs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

ROOT = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = ROOT / "projects"
PIPELINE_DIR = ROOT / "pipelines"


class CreateProjectRequest(BaseModel):
    # Core brief
    product_name: str
    key_selling_points: str
    pipeline: str = "ecommerce-promo"
    project_name: str = ""
    # Identity preservation (LoRA / ControlNet / transparent PNG)
    lora_model_path: Optional[str] = None
    controlnet_weight: Optional[float] = None
    transparent_png_path: Optional[str] = None


@router.post("/create")
async def create_project(body: CreateProjectRequest):
    """
    Initialise a project directory from product metadata.

    Identity-preservation fields (lora_model_path, controlnet_weight,
    transparent_png_path) are written into meta.json so the assets and
    compose stage agents can read them without re-querying the frontend.
    """
    from lib.project_manager import create_project as scaffold

    brief_text = _build_brief(body)

    try:
        result = scaffold(body.pipeline, brief_text, body.project_name)
    except ValueError as exc:
        code = 400 if "required" in str(exc).lower() else 409
        raise HTTPException(status_code=code, detail=str(exc))

    project_id = result["project_id"]
    project_dir = PROJECTS_DIR / project_id

    # Patch meta.json with identity-preservation fields
    meta_path = project_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["product_name"] = body.product_name
    meta["key_selling_points"] = body.key_selling_points
    if body.lora_model_path:
        meta["lora_model_path"] = body.lora_model_path
    if body.controlnet_weight is not None:
        meta["controlnet_weight"] = body.controlnet_weight
    if body.transparent_png_path:
        meta["transparent_png_path"] = body.transparent_png_path
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Auto-start the first stage
    from lib.checkpoint import get_next_stage
    from lib.pipeline_runner import start_agent_for_project
    from lib.checkpoint import write_checkpoint

    first_stage = get_next_stage(PIPELINE_DIR, project_id, body.pipeline)
    started = False
    if first_stage:
        started = start_agent_for_project(project_id, body.pipeline, brief_text, stage=first_stage)
        if started:
            write_checkpoint(
                pipeline_dir=PIPELINE_DIR,
                project_id=project_id,
                stage=first_stage,
                status="in_progress",
                artifacts={},
                pipeline_type=body.pipeline,
            )

    return JSONResponse(content={
        **result,
        "agent_started": started,
        "first_stage": first_stage,
        "identity_preservation": {
            "lora_model_path": body.lora_model_path,
            "controlnet_weight": body.controlnet_weight,
            "transparent_png_path": body.transparent_png_path,
        },
    })


@router.post("/create/upload")
async def create_project_with_upload(
    product_name: str = Form(...),
    key_selling_points: str = Form(...),
    pipeline: str = Form("ecommerce-promo"),
    project_name: str = Form(""),
    lora_model_path: Optional[str] = Form(None),
    controlnet_weight: Optional[float] = Form(None),
    transparent_png: Optional[UploadFile] = File(None),
):
    """
    Multipart variant of /create — accepts a transparent PNG upload directly.
    The file is saved into the project's assets/images/ directory and its
    path is written into meta.json as transparent_png_path.
    """
    from lib.project_manager import create_project as scaffold

    req = CreateProjectRequest(
        product_name=product_name,
        key_selling_points=key_selling_points,
        pipeline=pipeline,
        project_name=project_name,
        lora_model_path=lora_model_path,
        controlnet_weight=controlnet_weight,
    )
    brief_text = _build_brief(req)

    try:
        result = scaffold(pipeline, brief_text, project_name)
    except ValueError as exc:
        code = 400 if "required" in str(exc).lower() else 409
        raise HTTPException(status_code=code, detail=str(exc))

    project_id = result["project_id"]
    project_dir = PROJECTS_DIR / project_id

    # Save uploaded PNG
    png_rel_path = None
    if transparent_png and transparent_png.filename:
        img_dir = project_dir / "assets" / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        dest = img_dir / "product_transparent.png"
        with open(dest, "wb") as f:
            shutil.copyfileobj(transparent_png.file, f)
        png_rel_path = f"projects/{project_id}/assets/images/product_transparent.png"

    # Patch meta.json
    meta_path = project_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["product_name"] = product_name
    meta["key_selling_points"] = key_selling_points
    if lora_model_path:
        meta["lora_model_path"] = lora_model_path
    if controlnet_weight is not None:
        meta["controlnet_weight"] = controlnet_weight
    if png_rel_path:
        meta["transparent_png_path"] = png_rel_path
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Auto-start first stage
    from lib.checkpoint import get_next_stage, write_checkpoint
    from lib.pipeline_runner import start_agent_for_project

    first_stage = get_next_stage(PIPELINE_DIR, project_id, pipeline)
    started = False
    if first_stage:
        started = start_agent_for_project(project_id, pipeline, brief_text, stage=first_stage)
        if started:
            write_checkpoint(
                pipeline_dir=PIPELINE_DIR,
                project_id=project_id,
                stage=first_stage,
                status="in_progress",
                artifacts={},
                pipeline_type=pipeline,
            )

    return JSONResponse(content={
        **result,
        "agent_started": started,
        "first_stage": first_stage,
        "transparent_png_saved": png_rel_path,
    })


# ── Internal helpers ──────────────────────────────────────────

def _build_brief(body: CreateProjectRequest) -> str:
    lines = [
        f"商品名称: {body.product_name}",
        f"核心卖点: {body.key_selling_points}",
    ]
    if body.lora_model_path:
        lines.append(f"LoRA 模型路径: {body.lora_model_path}")
    if body.controlnet_weight is not None:
        lines.append(f"ControlNet 权重: {body.controlnet_weight}")
    if body.transparent_png_path:
        lines.append(f"产品透明底图: {body.transparent_png_path}")
    return "\n".join(lines)
