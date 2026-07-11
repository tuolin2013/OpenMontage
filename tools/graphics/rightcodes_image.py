"""Image generation via right.codes /draw API.

Uses the same LLM_API_KEY already configured for the right.codes LLM gateway.

API flow (async):
  1. POST https://www.right.codes/draw  with {"async": true, ...}
     → returns {"task_id": "..."}
  2. Poll GET https://www.right.codes/v1/tasks/{task_id}
     → until status == "completed"
  3. Extract image URL or base64 from task result

Docs: https://docs.right.codes/docs/rc_draw/
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_DRAW_ENDPOINT  = "https://www.right.codes/draw/v1/images/generations"
_TASK_ENDPOINT  = "https://www.right.codes/v1/tasks/{task_id}"
_POLL_INTERVAL  = 3   # seconds between polls
_POLL_TIMEOUT   = 300 # seconds max wait


class RightcodesImage(BaseTool):
    name = "rightcodes_image"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "right.codes"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set LLM_API_KEY to your right.codes API key.\n"
        "  Get one at https://right.codes"
    )
    agent_skills = ["flux-best-practices"]

    capabilities = ["generate_image", "text_to_image", "generate_illustration"]
    supports = {
        "negative_prompt": True,
        "seed": True,
        "custom_size": True,
    }
    best_for = [
        "general-purpose image generation via right.codes gateway",
        "teams already using right.codes for LLM — no extra key needed",
        "photorealistic and illustrative images",
    ]
    not_good_for = ["offline generation", "SVG vector output"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "default": ""},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "model": {
                "type": "string",
                "description": "Model: gpt-image-2, gpt-image-2-vip, nano-banana, nano-banana-2, nano-banana-pro",
                "default": "gpt-image-2",
            },
            "seed": {"type": "integer"},
            "steps": {"type": "integer"},
            "guidance_scale": {"type": "number"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "width", "height", "seed", "model"]
    side_effects = ["writes image file to output_path", "calls right.codes /draw API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("LLM_API_KEY") or os.environ.get("RIGHTCODES_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "gpt-image-2")
        if "vip" in model:
            return 0.03
        if "nano" in model:
            return 0.02
        return 0.04  # gpt-image-2 standard

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No right.codes API key found. " + self.install_instructions,
            )

        import requests

        start = time.time()
        prompt  = inputs["prompt"]
        model   = inputs.get("model", "gpt-image-2")
        width   = inputs.get("width", 1024)
        height  = inputs.get("height", 1024)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "width": width,
            "height": height,
            "async": True,   # required by right.codes draw API
        }
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        if inputs.get("steps"):
            payload["steps"] = inputs["steps"]
        if inputs.get("guidance_scale"):
            payload["guidance_scale"] = inputs["guidance_scale"]

        hdrs = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Step 1: submit task
            resp = requests.post(_DRAW_ENDPOINT, headers=hdrs, json=payload, timeout=30)
            resp.raise_for_status()
            task_data = resp.json()
            task_id = task_data.get("task_id") or task_data.get("id")
            if not task_id:
                return ToolResult(
                    success=False,
                    error=f"No task_id in response: {resp.text[:200]}",
                )

            # Step 2: poll until completed
            image_url: str | None = None
            b64_data: str | None = None
            deadline = time.time() + _POLL_TIMEOUT

            while time.time() < deadline:
                time.sleep(_POLL_INTERVAL)
                poll_url = _TASK_ENDPOINT.format(task_id=task_id)
                pr = requests.get(poll_url, headers=hdrs, timeout=30)
                pr.raise_for_status()
                pd = pr.json()
                status = pd.get("status", "")

                # Completed: right.codes returns OpenAI images format
                # {"created": ..., "data": [{"url": "..."}]} with no status field
                if pd.get("data") and isinstance(pd["data"], list) and pd["data"]:
                    first = pd["data"][0]
                    image_url = first.get("url")
                    b64_data = first.get("b64_json")
                    break

                # Also handle explicit completed status
                if status == "completed":
                    result = pd.get("result") or pd.get("output") or pd
                    if isinstance(result, dict):
                        image_url = result.get("url") or result.get("image_url")
                        if not image_url and result.get("data"):
                            first = result["data"][0]
                            image_url = first.get("url")
                            b64_data = first.get("b64_json")
                        if not image_url and result.get("images"):
                            first = result["images"][0]
                            image_url = first.get("url") or first.get("image_url")
                    break

                if status in ("failed", "error", "cancelled"):
                    err_msg = pd.get("error") or pd.get("message") or status
                    return ToolResult(success=False, error=f"Task {task_id} {status}: {err_msg}")
                # still pending / running — keep polling

            else:
                return ToolResult(
                    success=False,
                    error=f"Timed out waiting for task {task_id} after {_POLL_TIMEOUT}s",
                )

            # Step 3: download image
            output_path = Path(inputs.get("output_path", "generated_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if b64_data:
                import base64
                output_path.write_bytes(base64.b64decode(b64_data))
            elif image_url:
                img_resp = requests.get(image_url, timeout=120)
                img_resp.raise_for_status()
                output_path.write_bytes(img_resp.content)
            else:
                return ToolResult(
                    success=False,
                    error=f"Task {task_id} completed but no image URL found in result",
                )

        except Exception as e:
            return ToolResult(success=False, error=f"right.codes /draw generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "right.codes",
                "model": model,
                "prompt": prompt,
                "output": str(output_path),
                "task_id": task_id,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
