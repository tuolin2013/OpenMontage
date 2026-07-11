"""Pipeline Runner — Deterministic LLM stage executor.

Architecture: NO subprocess, NO CLI, NO agent interaction.
Each stage is a single stateless HTTP request to the OpenAI-compatible
Chat Completions API (right.codes gateway by default).

Flow per stage:
  1. Load pipeline YAML + stage definition
  2. Load previous stage artifacts from checkpoint files
  3. Build system prompt (role + JSON contract) + user message (brief + artifacts)
  4. POST to /v1/chat/completions  (blocking, one request/response)
  5. Parse JSON from response
  6. Write artifact JSON + checkpoint JSON to disk
  7. Return result dict — caller decides next action

The stage runs in a background thread so the FastAPI endpoint returns immediately
and the frontend polls /status + /log.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# ── Directory layout ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
PIPELINE_DEFS_DIR = ROOT / "pipeline_defs"
PIPELINES_DIR = ROOT / "pipelines"   # checkpoint storage


# ── Stage artifact schemas (inline — no external AI agent needed) ─────
# Maps stage name → the JSON shape the LLM must return inside "artifacts"
STAGE_ARTIFACT_CONTRACTS: dict[str, dict] = {
    "research": {
        "research_brief": {
            "summary": "string — market research summary",
            "competitors": ["list of competitor product names"],
            "platform_trends": ["list of trend observations"],
            "audience_profile": "string — target audience description",
            "hook_patterns": ["list of effective hook patterns found"],
            "key_insights": ["list of actionable insights"]
        }
    },
    "proposal": {
        "proposal_packet": {
            "recommended_video_type": "string — e.g. 产品展示/种草测评/直播引流/品牌故事",
            "duration_seconds": "number",
            "target_platform": "string — e.g. 抖音/小红书/淘宝",
            "core_selling_points": ["list of up to 3 selling points"],
            "concept_options": [
                {
                    "id": "A",
                    "angle": "string — selling angle",
                    "visual_strategy": "string",
                    "rationale": "string"
                }
            ],
            "cost_estimate_usd": "number",
            "render_runtime": "string — e.g. remotion/hyperframes"
        }
    },
    "script": {
        "script": {
            "hook": "string — opening 3 seconds, grab attention",
            "pain_point": "string — audience pain point addressed",
            "product_intro": "string — product introduction",
            "key_points": ["list of selling point lines"],
            "cta": "string — call to action",
            "full_script": "string — complete narration text",
            "duration_estimate_seconds": "number",
            "word_count": "number"
        }
    },
    "scene_plan": {
        "scene_plan": {
            "scenes": [
                {
                    "scene_id": "number",
                    "duration_seconds": "number",
                    "shot_description": "string",
                    "overlay_text": "string or null",
                    "sound_note": "string or null",
                    "is_product_closeup": "boolean"
                }
            ],
            "total_duration_seconds": "number",
            "product_closeup_ratio": "number 0-1"
        }
    },
    "assets": {
        "asset_manifest": {
            "voiceover": {"text": "string", "voice": "string", "file_path": "string or null"},
            "background_music": {"style": "string", "file_path": "string or null"},
            "images": [{"scene_id": "number", "prompt": "string", "file_path": "string or null"}],
            "subtitles_file": "string or null",
            "notes": "string"
        }
    },
    "edit": {
        "edit_decisions": {
            "timeline": [
                {
                    "scene_id": "number",
                    "start_sec": "number",
                    "end_sec": "number",
                    "transition": "string — cut/fade/slide",
                    "text_overlay": "string or null",
                    "audio_level_db": "number"
                }
            ],
            "total_duration_seconds": "number",
            "bgm_volume_db": "number",
            "render_runtime": "string"
        }
    },
    "compose": {
        "render_report": {
            "status": "completed",
            "output_file": "string — relative path to rendered video or HyperFrames composition",
            "resolution": "string — e.g. 1080x1920",
            "duration_seconds": "number",
            "file_size_bytes": "number or null",
            "render_notes": "string"
        }
    },
    "publish": {
        "publish_log": {
            "platforms": [
                {
                    "name": "string",
                    "video_file": "string",
                    "title": "string",
                    "description": "string",
                    "tags": ["list of tags"],
                    "cover_frame": "string or null"
                }
            ],
            "status": "ready"
        }
    },
}


# ── Environment helpers ───────────────────────────────────────

def _load_env() -> dict[str, str]:
    """Read key=value pairs from .env file (strip inline comments)."""
    env: dict[str, str] = {}
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return env
    for line in dotenv.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.split("#")[0].strip()
        if k and v:
            env[k] = v
    return env


def _get_llm_config() -> tuple[str, str, str]:
    """Return (api_key, base_url, model) from env, falling back to .env file."""
    file_env = _load_env()

    api_key = (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or file_env.get("ANTHROPIC_API_KEY")
        or file_env.get("LLM_API_KEY")
        or ""
    )
    base_url = (
        os.environ.get("ANTHROPIC_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or file_env.get("ANTHROPIC_BASE_URL")
        or file_env.get("LLM_BASE_URL")
        or "https://api.openai.com/v1"
    )
    model = (
        os.environ.get("LLM_MODEL")
        or file_env.get("LLM_MODEL")
        or "claude-sonnet-4-5"
    )
    return api_key, base_url, model


# ── Pipeline YAML helpers ─────────────────────────────────────

def _load_pipeline_yaml(pipeline_id: str) -> dict:
    path = PIPELINE_DEFS_DIR / f"{pipeline_id}.yaml"
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _get_stage_def(pipeline_yaml: dict, stage: str) -> dict:
    for s in pipeline_yaml.get("stages", []):
        if s.get("name") == stage:
            return s
    return {}


def get_pipeline_name(pipeline_id: str) -> str:
    return _load_pipeline_yaml(pipeline_id).get("name", pipeline_id)


# ── Checkpoint helpers ────────────────────────────────────────

def _cp_path(project_id: str, stage: str) -> Path:
    d = PIPELINES_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"checkpoint_{stage}.json"


def _read_checkpoints(project_id: str) -> list[dict]:
    cp_dir = PIPELINES_DIR / project_id
    if not cp_dir.exists():
        return []
    result = []
    for f in sorted(cp_dir.glob("checkpoint_*.json")):
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


def _write_checkpoint(project_id: str, pipeline_id: str, stage: str,
                       status: str, artifacts: dict,
                       human_approval_required: bool = False,
                       error: str | None = None) -> None:
    cp = {
        "version": "1.0",
        "project_id": project_id,
        "pipeline_type": pipeline_id,
        "stage": stage,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checkpoint_policy": "guided",
        "human_approval_required": human_approval_required,
        "human_approved": False,
        "artifacts": artifacts,
    }
    if error:
        cp["error"] = error
    _cp_path(project_id, stage).write_text(
        json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_prior_artifacts(project_id: str) -> dict:
    """Collect all artifacts from completed checkpoints."""
    merged: dict[str, Any] = {}
    for cp in _read_checkpoints(project_id):
        if cp.get("status") in ("completed", "awaiting_human"):
            merged.update(cp.get("artifacts", {}))
    return merged


# ── Log helper ────────────────────────────────────────────────

def _log(log_path: Path, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    logger.info(line)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── LLM call ─────────────────────────────────────────────────

def _call_llm(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_message: str,
    log_path: Path,
    timeout: int = 180,
) -> str:
    """Single blocking HTTP POST to OpenAI-compatible chat completions endpoint.
    Returns the raw response content string."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    _log(log_path, f"→ POST {url}  model={model}")
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if resp.status_code != 200:
        raise RuntimeError(
            f"LLM API error {resp.status_code}: {resp.text[:500]}"
        )

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    _log(log_path, f"← {resp.status_code}  tokens={usage.get('total_tokens','?')}")
    return content


# ── JSON extraction ───────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from LLM response (handles markdown fences)."""
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    text = text.strip()

    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")

    # Walk to find matching closing brace
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise ValueError("Unbalanced JSON braces in LLM response")


# ── System prompt builder ─────────────────────────────────────

def _build_system_prompt(
    pipeline_id: str,
    stage: str,
    stage_def: dict,
    artifact_contract: dict,
    human_approval_required: bool,
) -> str:
    contract_str = json.dumps(artifact_contract, ensure_ascii=False, indent=2)
    produces = stage_def.get("produces", list(artifact_contract.keys()))
    review_focus = "\n".join(f"  - {r}" for r in stage_def.get("review_focus", []))
    success_criteria = "\n".join(f"  - {s}" for s in stage_def.get("success_criteria", []))

    approval_note = (
        "This stage requires human approval. You are producing content for review."
        if human_approval_required
        else "This stage is auto-approved. Produce complete, final content."
    )

    return f"""You are the OpenMontage pipeline engine executing stage "{stage}" of the "{pipeline_id}" pipeline.

## Your Role
You are a deterministic content generator. You receive a product brief and prior stage artifacts,
and you produce exactly ONE JSON object as output. No explanations, no questions, no markdown prose —
ONLY the JSON object.

## Stage: {stage}
Produces: {', '.join(produces)}
{approval_note}

## Review Focus
{review_focus or '  - Produce high-quality, complete output'}

## Success Criteria
{success_criteria or '  - Valid JSON matching the contract below'}

## OUTPUT CONTRACT
You MUST return a single valid JSON object with this exact structure:
{contract_str}

## Rules
1. Return ONLY a JSON object. No text before or after.
2. All string fields must be in Simplified Chinese unless they are technical identifiers.
3. Never use placeholder text like "string" — fill in real content based on the brief.
4. If a field is marked "string or null", use null if not applicable.
5. Do not add extra fields not in the contract.
"""


# ── Stage executor (runs in background thread) ───────────────

def _execute_stage(
    project_id: str,
    pipeline_id: str,
    stage: str,
    brief_text: str,
    lora_model_path: str | None = None,
    controlnet_weight: float | None = None,
    transparent_png_path: str | None = None,
) -> None:
    """Run a single pipeline stage via direct LLM API call. Designed to run in a thread."""
    log_path = PROJECTS_DIR / project_id / "agent.log"
    _log(log_path, f"=== Stage '{stage}' starting ===")

    try:
        api_key, base_url, model = _get_llm_config()
        if not api_key:
            raise ValueError(
                "No LLM API key found. Set LLM_API_KEY or ANTHROPIC_API_KEY in .env"
            )

        # Load pipeline definition
        pipeline_yaml = _load_pipeline_yaml(pipeline_id)
        stage_def = _get_stage_def(pipeline_yaml, stage)
        human_approval_required = stage_def.get("human_approval_default", False)

        # Get artifact contract for this stage
        artifact_contract = STAGE_ARTIFACT_CONTRACTS.get(stage, {
            "output": {"summary": "string — stage output"}
        })

        # Build system prompt
        system_prompt = _build_system_prompt(
            pipeline_id, stage, stage_def, artifact_contract, human_approval_required
        )

        # Build user message: brief + prior artifacts + identity preservation
        prior_artifacts = _load_prior_artifacts(project_id)
        user_parts = [f"## Product Brief\n{brief_text}"]

        if prior_artifacts:
            user_parts.append(
                "## Prior Stage Artifacts\n"
                + json.dumps(prior_artifacts, ensure_ascii=False, indent=2)
            )

        # Identity preservation annotations
        if lora_model_path:
            user_parts.append(f"## Identity Preservation\nLoRA model path: {lora_model_path}")
        if controlnet_weight is not None:
            user_parts.append(f"ControlNet weight: {controlnet_weight}")
        if transparent_png_path:
            user_parts.append(f"Product transparent PNG: {transparent_png_path}")

        user_parts.append(
            f"\nProduce the '{stage}' stage output now. "
            "Return ONLY a valid JSON object matching the contract."
        )
        user_message = "\n\n".join(user_parts)

        _log(log_path, f"Calling LLM: base_url={base_url} model={model}")

        raw_response = _call_llm(
            api_key, base_url, model,
            system_prompt, user_message, log_path
        )

        _log(log_path, "Parsing JSON response...")
        artifacts = _extract_json(raw_response)
        _log(log_path, f"JSON parsed OK — keys: {list(artifacts.keys())}")

        # Write artifact file
        artifact_dir = PROJECTS_DIR / project_id / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / f"{stage}.json").write_text(
            json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Determine final status
        final_status = "awaiting_human" if human_approval_required else "completed"

        _write_checkpoint(
            project_id, pipeline_id, stage,
            status=final_status,
            artifacts=artifacts,
            human_approval_required=human_approval_required,
        )

        _log(log_path, f"=== Stage '{stage}' → {final_status} ===")

    except Exception as exc:
        _log(log_path, f"[ERROR] Stage '{stage}' failed: {exc}")
        logger.exception(f"Stage '{stage}' failed for project '{project_id}'")
        _write_checkpoint(
            project_id, pipeline_id, stage,
            status="failed",
            artifacts={},
            error=str(exc),
        )


# ── Public API ────────────────────────────────────────────────

def start_agent_for_project(
    project_id: str,
    pipeline_id: str,
    brief_text: str,
    stage: str | None = None,
    lora_model_path: str | None = None,
    controlnet_weight: float | None = None,
    transparent_png_path: str | None = None,
) -> bool:
    """
    Launch a pipeline stage in a background thread.

    No subprocess, no CLI — uses direct HTTP requests to the OpenAI-compatible
    LLM API configured in .env (LLM_API_KEY + LLM_BASE_URL).

    Returns True immediately after spawning the thread.
    The frontend polls /api/project/{id}/status and /log for progress.
    """
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        logger.error(f"Project directory not found: {project_dir}")
        return False

    if stage is None:
        # Auto-detect next stage from pipeline YAML
        from lib.checkpoint import get_next_stage
        stage = get_next_stage(PIPELINE_DEFS_DIR, project_id, pipeline_id)
        if not stage:
            logger.info(f"All stages complete for {project_id}")
            return False

    log_path = project_dir / "agent.log"
    _log(log_path, f"--- Starting stage '{stage}' for {project_id} ---")

    thread = threading.Thread(
        target=_execute_stage,
        args=(project_id, pipeline_id, stage, brief_text,
              lora_model_path, controlnet_weight, transparent_png_path),
        daemon=True,
        name=f"stage-{project_id}-{stage}",
    )
    thread.start()
    logger.info(f"Thread started: stage={stage} project={project_id}")
    return True
