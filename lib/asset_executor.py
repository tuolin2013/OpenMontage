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
        log.info("Generating %d images…", len(images))
        image_tool = _get_image_tool()
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

            log.info("  Generating scene %s via %s…", scene_id, image_tool.provider)
            tool_result = image_tool.execute({
                "prompt": prompt,
                "width": 1080,
                "height": 1920,   # 9:16 for short video
                "model": "gpt-image-2",
                "output_path": str(out_path),
            })

            if tool_result.success:
                img["file_path"] = str(out_path)
                log.info("  ✅ scene %s → %s", scene_id, out_path.name)
                results.append({"task": f"image_scene_{scene_id}", "status": "ok", "path": str(out_path)})
            else:
                log.error("  ❌ scene %s failed: %s", scene_id, tool_result.error)
                results.append({"task": f"image_scene_{scene_id}", "status": "failed", "error": tool_result.error})

    # ── 2. Videos ────────────────────────────────────────────────────────────
    # Generate a short video clip for each scene from its image (i2v) or prompt (t2v)
    videos = manifest.get("videos", [])
    # If no explicit videos list, derive from images
    if not videos and images:
        videos = [
            {
                "scene_id": img.get("scene_id"),
                "prompt": img.get("video_prompt") or img.get("prompt", ""),
                "image_path": img.get("file_path"),
                "file_path": img.get("video_path"),
            }
            for img in images
        ]

    if videos:
        log.info("Generating %d video clips…", len(videos))
        for clip in videos:
            scene_id = clip.get("scene_id", "unknown")
            if clip.get("file_path"):
                log.info("  video scene %s already exists, skipping", scene_id)
                continue

            out_vid = assets_dir / "video" / (
                f"scene_{scene_id:02d}.mp4" if isinstance(scene_id, int) else f"scene_{scene_id}.mp4"
            )
            vid_result = _generate_video_clip(
                prompt=clip.get("prompt", ""),
                image_path=clip.get("image_path"),
                out_path=out_vid,
            )
            if vid_result["success"]:
                clip["file_path"] = vid_result["path"]
                # Also back-fill into the images entry for compose stage
                for img in images:
                    if img.get("scene_id") == scene_id:
                        img["video_path"] = vid_result["path"]
                log.info("  ✅ video scene %s → %s", scene_id, out_vid.name)
                results.append({"task": f"video_scene_{scene_id}", "status": "ok", "path": vid_result["path"]})
            else:
                log.error("  ❌ video scene %s failed: %s", scene_id, vid_result.get("error"))
                results.append({"task": f"video_scene_{scene_id}", "status": "failed", "error": vid_result.get("error")})

    # ── 3. Voiceover ─────────────────────────────────────────────────────────
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

def _get_image_tool():
    """Return the best available image generation tool.

    Priority: RightcodesImage (uses LLM_API_KEY, no extra key) → FluxImage (FAL_KEY)
    """
    import os
    if os.environ.get("LLM_API_KEY") or os.environ.get("RIGHTCODES_API_KEY"):
        try:
            from tools.graphics.rightcodes_image import RightcodesImage
            tool = RightcodesImage()
            if tool.get_status().name == "AVAILABLE":
                log.info("Image tool: RightcodesImage (right.codes gpt-image-2)")
                return tool
        except Exception as exc:
            log.warning("RightcodesImage unavailable (%s), falling back to FLUX", exc)

    if os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY"):
        try:
            from tools.graphics.flux_image import FluxImage
            log.info("Image tool: FluxImage (fal.ai FLUX dev)")
            return FluxImage()
        except Exception as exc:
            log.warning("FluxImage unavailable: %s", exc)

    raise RuntimeError(
        "No image generation tool available. "
        "Set LLM_API_KEY (right.codes) or FAL_KEY (fal.ai) in .env"
    )


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


def _upload_to_fal(local_path: str) -> str | None:
    """Upload a local file to fal.ai storage and return the public URL.

    Tries two methods:
    1. fal-client SDK (handles auth + retries cleanly)
    2. Direct REST POST to storage.fal.run/upload (fallback)
    """
    import os
    api_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")
    if not api_key:
        return None

    # Method 1: fal-client SDK
    try:
        import fal_client  # pip install fal-client
        os.environ.setdefault("FAL_KEY", api_key)
        url = fal_client.upload_file(local_path)
        log.info("  Uploaded (sdk) %s → %s", Path(local_path).name, url)
        return url
    except ImportError:
        pass
    except Exception as exc:
        log.debug("  fal-client SDK upload failed: %s", exc)

    # Method 2: direct REST upload
    try:
        import requests
        filename = Path(local_path).name
        with open(local_path, "rb") as f:
            data = f.read()
        resp = requests.post(
            "https://storage.fal.run/upload",
            headers={"Authorization": f"Key {api_key}"},
            files={"file": (filename, data, "image/png")},
            timeout=60,
        )
        resp.raise_for_status()
        url = resp.json().get("url")
        log.info("  Uploaded (rest) %s → %s", filename, url)
        return url
    except Exception as exc:
        log.warning("  fal.ai upload failed: %s", exc)
        return None


def _generate_video_clip(prompt: str, image_path: str | None, out_path: Path) -> dict:
    """Generate a 5s video clip.

    Strategy:
    - If image_path exists (generated from scene image): KlingVideo image_to_video
      → preserves product appearance, ~$0.10/clip
    - Otherwise: KlingVideo text_to_video
    - Fallback: SeedanceVideo (more expensive but higher quality)
    """
    import os
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not (os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")):
        return {"success": False, "error": "FAL_KEY not set — video generation unavailable"}

    from tools.video.kling_video import KlingVideo
    kling = KlingVideo()

    # Decide operation
    has_image = image_path and Path(image_path).exists()
    operation = "image_to_video" if has_image else "text_to_video"

    inputs: dict = {
        "prompt": prompt,
        "operation": operation,
        "model_variant": "v3/standard",
        "duration": "5",
        "aspect_ratio": "9:16",
        "output_path": str(out_path),
    }
    if has_image:
        # Kling needs a public URL — upload local file to fal.ai storage first
        fal_url = _upload_to_fal(image_path)
        if fal_url:
            inputs["image_url"] = fal_url
        else:
            # Can't upload, fall back to text_to_video
            log.warning("  fal.ai upload failed, switching to text_to_video")
            inputs["operation"] = "text_to_video"
            inputs.pop("image_url", None)

    log.info("  Generating clip (%s) via Kling v3…", operation)
    r = kling.execute(inputs)
    if r.success:
        return {"success": True, "path": str(out_path)}

    log.warning("Kling failed (%s), trying Seedance…", r.error)

    # Seedance fallback
    from tools.video.seedance_video import SeedanceVideo
    seedance = SeedanceVideo()
    s_inputs: dict = {
        "prompt": prompt,
        "operation": "image_to_video" if has_image else "text_to_video",
        "model_variant": "fast",
        "duration": "5",
        "aspect_ratio": "9:16",
        "generate_audio": False,  # we have separate TTS
        "output_path": str(out_path),
    }
    if has_image:
        s_inputs["image_path"] = image_path

    r2 = seedance.execute(s_inputs)
    if r2.success:
        return {"success": True, "path": str(out_path)}

    return {"success": False, "error": f"All video tools failed. Kling: {r.error}. Seedance: {r2.error}"}


def _generate_music(style_prompt: str, out_path: Path) -> dict:
    """Try Suno → ElevenLabs → Pixabay fallback."""
    import os
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. Suno (best quality, any genre, instrumental) ───────────────────
    if os.environ.get("SUNO_API_KEY"):
        try:
            from tools.audio.suno_music import SunoMusic
            suno = SunoMusic()
            r = suno.execute({
                "prompt": style_prompt[:500],
                "instrumental": True,
                "model": "V4",
                "output_path": str(out_path),
            })
            if r.success:
                log.info("  Suno music: %s", r.data.get("title", "untitled"))
                return {"success": True, "path": str(out_path)}
            log.warning("Suno music failed (%s), trying ElevenLabs…", r.error)
        except Exception as exc:
            log.warning("Suno music exception (%s), trying ElevenLabs…", exc)

    # ── 2. ElevenLabs ────────────────────────────────────────────────────
    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            from tools.audio.music_gen import MusicGen
            mg = MusicGen()
            r = mg.execute({
                "prompt": style_prompt[:200],
                "duration": 30,
                "duration_seconds": 30,
                "output_path": str(out_path),
            })
            if r.success:
                return {"success": True, "path": str(out_path)}
            log.warning("ElevenLabs music failed (%s), trying Pixabay…", r.error)
        except Exception as exc:
            log.warning("MusicGen exception (%s), trying Pixabay…", exc)

    # ── 3. Pixabay free stock music ───────────────────────────────────────
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
