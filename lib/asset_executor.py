"""lib/asset_executor.py — Execute asset generation from an asset_manifest.

Reads the asset_manifest produced by the 'assets' pipeline stage and drives
the actual tool calls:
  - images[]    → FluxImage (fal.ai FLUX)
  - voiceover   → ElevenLabsTTS (or DoubaoTTS if ELEVENLABS unavailable)
  - background_music → ElevenLabs music_gen (or pixabay_music fallback)

All generated file paths are written back into the manifest and saved as
artifacts/assets.json so the compose stage can reference real files.

Usage:
    from lib.asset_executor import execute_assets
    result = execute_assets(project_id, project_dir)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def execute_assets(project_id: str, project_dir: Path) -> dict[str, Any]:
    """Run all asset generation tasks defined in artifact/assets.json.

    Returns a summary dict with counts of succeeded/failed tasks and the
    updated manifest (with file_path fields populated).
    """
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    artifact_path = project_dir / "artifacts" / "assets.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"asset_manifest not found: {artifact_path}")

    raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    manifest = raw.get("asset_manifest", raw)  # support both wrapped and flat

    assets_dir = project_dir / "assets"
    results: list[dict] = []

    # ── 1. Images ───────────────────────────────────────────────────────────
    images = manifest.get("images", [])
    if images:
        log.info("Generating %d images via FLUX…", len(images))
        from tools.graphics.flux_image import FluxImage
        flux = FluxImage()
        for img in images:
            scene_id = img.get("scene_id", "unknown")
            prompt = img.get("prompt", "")
            if img.get("file_path"):
                log.info("  scene %s already has file_path, skipping", scene_id)
                continue
            if not prompt:
                log.warning("  scene %s has no prompt, skipping", scene_id)
                continue

            out_path = assets_dir / "images" / f"scene_{scene_id:02d}.png" \
                if isinstance(scene_id, int) else \
                assets_dir / "images" / f"scene_{scene_id}.png"

            log.info("  Generating scene %s…", scene_id)
            tool_result = flux.execute({
                "prompt": prompt,
                "width": 1080,
                "height": 1920,   # 9:16 for short video
                "model": "flux/dev",
                "output_path": str(out_path),
            })

            if tool_result.success:
                img["file_path"] = str(out_path)
                log.info("  ✅ scene %s → %s", scene_id, out_path.name)
                results.append({"task": f"image_scene_{scene_id}", "status": "ok", "path": str(out_path)})
            else:
                log.error("  ❌ scene %s failed: %s", scene_id, tool_result.error)
                results.append({"task": f"image_scene_{scene_id}", "status": "failed", "error": tool_result.error})

    # ── 2. Voiceover ─────────────────────────────────────────────────────────
    voiceover = manifest.get("voiceover", {})
    vo_text = voiceover.get("text", "")
    if vo_text and not voiceover.get("file_path"):
        log.info("Generating voiceover TTS…")
        out_path = assets_dir / "audio" / "voiceover.mp3"

        # Try ElevenLabs first; fall back to Doubao if unavailable
        tts_result = _generate_tts(vo_text, out_path)
        if tts_result["success"]:
            voiceover["file_path"] = tts_result["path"]
            log.info("  ✅ voiceover → %s", out_path.name)
            results.append({"task": "voiceover", "status": "ok", "path": tts_result["path"]})
        else:
            log.error("  ❌ voiceover failed: %s", tts_result.get("error"))
            results.append({"task": "voiceover", "status": "failed", "error": tts_result.get("error")})

    # ── 3. Background Music ──────────────────────────────────────────────────
    bgm = manifest.get("background_music", {})
    bgm_style = bgm.get("style", "")
    if bgm_style and not bgm.get("file_path"):
        log.info("Generating background music…")
        out_path = assets_dir / "music" / "background.mp3"
        music_result = _generate_music(bgm_style, out_path)
        if music_result["success"]:
            bgm["file_path"] = music_result["path"]
            log.info("  ✅ background music → %s", out_path.name)
            results.append({"task": "background_music", "status": "ok", "path": music_result["path"]})
        else:
            log.error("  ❌ background music failed: %s", music_result.get("error"))
            results.append({"task": "background_music", "status": "failed", "error": music_result.get("error")})

    # ── Save updated manifest ─────────────────────────────────────────────
    raw["asset_manifest"] = manifest
    artifact_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("asset_manifest updated: %s", artifact_path)

    succeeded = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    return {
        "project_id": project_id,
        "tasks_total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
        "manifest": manifest,
    }


# ── Internal helpers ──────────────────────────────────────────────────────

def _generate_tts(text: str, out_path: Path) -> dict:
    """Try VoxCPM2 (Modal) → ElevenLabs → Doubao → fail."""
    import os
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. VoxCPM2 (self-hosted on Modal, free, best for Chinese) ──────────
    if os.environ.get("NEXT_PUBLIC_VOXCPM2_URL"):
        try:
            from tools.audio.voxcpm2_tts import VoxCPM2TTS
            tts = VoxCPM2TTS()
            # Use a Chinese female voice prompt suitable for ecommerce short video
            wav_path = out_path.with_suffix(".wav")
            r = tts.execute({
                "text": text,
                "voice_prompt": "声音甜美自然，语速稍快，节奏紧凑，有感染力，适合电商短视频旁白",
                "cfg_value": 2.0,
                "timesteps": 10,
                "output_path": str(wav_path),
            })
            if r.success:
                # Convert wav → mp3 if ffmpeg available, otherwise keep wav
                final_path = _wav_to_mp3(wav_path, out_path)
                return {"success": True, "path": str(final_path)}
            log.warning("VoxCPM2 TTS failed (%s), trying ElevenLabs…", r.error)
        except Exception as exc:
            log.warning("VoxCPM2 TTS exception (%s), trying ElevenLabs…", exc)

    # ── 2. ElevenLabs ──────────────────────────────────────────────────────
    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            from tools.audio.elevenlabs_tts import ElevenLabsTTS
            tts = ElevenLabsTTS()
            r = tts.execute({
                "text": text,
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel — multilingual
                "model_id": "eleven_multilingual_v2",
                "output_path": str(out_path),
                "stability": 0.6,
                "similarity_boost": 0.8,
                "style": 0.3,
            })
            if r.success:
                return {"success": True, "path": str(out_path)}
            log.warning("ElevenLabs TTS failed (%s), trying Doubao…", r.error)
        except Exception as exc:
            log.warning("ElevenLabs TTS exception (%s), trying Doubao…", exc)

    # ── 3. Doubao ──────────────────────────────────────────────────────────
    if os.environ.get("DOUBAO_SPEECH_API_KEY"):
        try:
            from tools.audio.doubao_tts import DoubaoTTS
            tts = DoubaoTTS()
            r = tts.execute({"text": text, "output_path": str(out_path)})
            if r.success:
                return {"success": True, "path": str(out_path)}
            log.warning("Doubao TTS failed: %s", r.error)
        except Exception as exc:
            log.warning("Doubao TTS exception: %s", exc)

    return {"success": False, "error": "All TTS providers failed or unavailable"}


def _wav_to_mp3(wav_path: Path, mp3_path: Path) -> Path:
    """Convert wav to mp3 via ffmpeg if available, otherwise return wav as-is."""
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0:
            wav_path.unlink(missing_ok=True)
            return mp3_path
    except Exception:
        pass
    # ffmpeg not available or failed — return wav
    return wav_path


def _generate_music(style_prompt: str, out_path: Path) -> dict:
    """Try ElevenLabs music → Pixabay fallback."""
    import os
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            from tools.audio.music_gen import MusicGen
            mg = MusicGen()
            r = mg.execute({
                "prompt": style_prompt[:200],  # keep prompt concise
                "duration": 30,
                "duration_seconds": 30,
                "output_path": str(out_path),
            })
            if r.success:
                return {"success": True, "path": str(out_path)}
            log.warning("ElevenLabs music failed (%s), trying Pixabay…", r.error)
        except Exception as exc:
            log.warning("MusicGen exception (%s), trying Pixabay…", exc)

    # Pixabay free stock music as fallback
    if os.environ.get("PIXABAY_API_KEY"):
        try:
            from tools.audio.pixabay_music import PixabayMusic
            pm = PixabayMusic()
            r = pm.execute({
                "query": "background calm",
                "output_path": str(out_path),
            })
            if r.success:
                return {"success": True, "path": str(out_path)}
        except Exception as exc:
            log.warning("Pixabay music exception: %s", exc)

    return {"success": False, "error": "All music providers failed or unavailable"}
