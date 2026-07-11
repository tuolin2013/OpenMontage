"""Pipeline Runner - Starts and manages the background AI Agent for a project.

This module launches Claude Code as a non-interactive headless subprocess.
The agent receives a structured prompt that enforces batch/headless execution:
no questions, no onboarding, no capability menus — just execute the stage and exit.

Implementation note:
On Windows, passing a long multi-line prompt as a CLI argument to `claude -p` is
unreliable because the shell (cmd.exe) has a command-line length limit (~8191 chars)
and may mangle newlines/quotes. Instead, we write the prompt to a temp file and
pipe it into claude's stdin via the `-F` / `--input-file` flag, or via stdin pipe.
"""

import subprocess
import platform
import tempfile
import os
import threading
from pathlib import Path
import logging

PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"
PIPELINE_DEFS_DIR = Path(__file__).resolve().parent.parent / "pipeline_defs"

logger = logging.getLogger(__name__)

def _wait_and_close(proc, *files):
    proc.wait()
    for f in files:
        try:
            f.close()
        except Exception:
            pass


def get_pipeline_name(pipeline_id: str) -> str:
    """Read the pipeline name from the yaml manifest if possible."""
    yaml_path = PIPELINE_DEFS_DIR / f"{pipeline_id}.yaml"
    if not yaml_path.exists():
        return pipeline_id
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("name", pipeline_id)
    except Exception:
        return pipeline_id


def _build_headless_prompt(
    project_id: str,
    pipeline_id: str,
    p_name: str,
    brief_text: str,
    stage: str | None,
) -> str:
    """Build the structured headless prompt for the background agent."""
    rel_project_dir = f"projects/{project_id}"
    rel_brief_path = f"projects/{project_id}/brief.md"

    # ── HEADLESS SYSTEM BLOCK ──────────────────────────────────────────────
    headless_block = f"""# HEADLESS BATCH EXECUTION MODE

## Role
You are the OpenMontage pipeline engine executing a single automated task.
This process was spawned by the web UI backend via `claude -p` (non-interactive).
stdin is CLOSED. There is NO human on the other end.

## Absolute Constraints — read these before doing anything else
1. DO NOT ask questions. DO NOT request clarification. DO NOT present options.
2. DO NOT run `skills/meta/onboarding.md` or any onboarding/discovery flow.
3. DO NOT run preflight capability discovery (`provider_menu_summary`). Skip it.
4. DO NOT present a capability menu to the user. There is no user session.
5. When a pipeline stage has `human_approval_default: true`, write the checkpoint
   with `"status": "awaiting_human"` and EXIT. The web UI handles approval gates.
6. If a tool or provider is unavailable, pick the best available fallback and proceed.
   Log your substitution. Never stop to ask which fallback to use.
7. Write ALL artifacts and assets to: {rel_project_dir}/
8. Write ALL checkpoints to: pipelines/{project_id}/checkpoint_<stage>.json

## Project Context
- Pipeline ID  : {pipeline_id}
- Pipeline Name: {p_name}
- Project dir  : {rel_project_dir}
- Brief file   : {rel_brief_path}

## Video Brief (verbatim — use this as the production brief)
---
{brief_text}
---
"""

    # ── STAGE-SPECIFIC TASK BLOCK ──────────────────────────────────────────
    if stage:
        task_block = f"""## Your Task: Execute stage `{stage}` ONLY

Follow these steps in order:
1. Read `pipeline_defs/{pipeline_id}.yaml` — locate the `{stage}` stage entry.
2. Read that stage's director skill (`skills/pipelines/{pipeline_id}/{stage}-director.md`).
   If the file does not exist at that path, search `skills/pipelines/` for a matching file.
3. Read any Layer 3 skills listed in the `agent_skills` field of any tools you will call.
4. Execute all work required for the `{stage}` stage. Produce the canonical artifact.
5. Write the artifact JSON to: {rel_project_dir}/artifacts/
6. Write the checkpoint JSON to: pipelines/{project_id}/checkpoint_{stage}.json
   - CRITICAL: The `artifacts` object inside the checkpoint MUST contain the FULL JSON payload of the artifact you produced, NOT just the string file path!
   - If `human_approval_default: true` for this stage -> set `"status": "awaiting_human"`
   - Otherwise -> set `"status": "completed"`
7. STOP HERE. Do not continue to the next stage. Exit after writing the checkpoint.

Begin now. Read the YAML, read the skill, do the work, write the checkpoint, exit.
"""
    else:
        task_block = f"""## Your Task: Run the `{pipeline_id}` pipeline from the first stage

Follow these steps:
1. Read `{rel_brief_path}` — confirm the brief content matches what is above.
2. Read `pipeline_defs/{pipeline_id}.yaml` — understand the ordered stage sequence.
3. Execute stages sequentially:
   a. For each stage: read its director skill, read any required Layer 3 skills.
   b. Do the work. Produce the canonical artifact.
   c. Write the artifact to `{rel_project_dir}/artifacts/`
   d. Write the checkpoint to `pipelines/{project_id}/checkpoint_<stage>.json`
      - CRITICAL: The `artifacts` object inside the checkpoint MUST contain the FULL JSON payload of the artifact you produced, NOT just the string file path!
   e. If `human_approval_default: true` -> set `"status": "awaiting_human"` and STOP.
   f. If `human_approval_default: false` -> set `"status": "completed"` and continue.
4. Stop when you hit an `awaiting_human` gate or all stages are complete.

Begin now. Read the pipeline YAML and execute the first stage.
"""

    return headless_block + task_block


def start_agent_for_project(
    project_id: str,
    pipeline_id: str,
    brief_text: str,
    stage: str = None,
) -> bool:
    """
    Launch Claude Code in the background for a specific project stage.

    Args:
        project_id: The unique project directory name
        pipeline_id: The pipeline type (e.g., animated-explainer)
        brief_text: The user's input brief (verbatim text, not a file path)
        stage: If provided, the agent executes ONLY this stage and exits.

    Returns:
        bool: True if the subprocess was successfully spawned, False otherwise.
    """
    project_dir = PROJECTS_DIR / project_id
    log_path = project_dir / "agent.log"

    p_name = get_pipeline_name(pipeline_id)
    prompt_text = _build_headless_prompt(project_id, pipeline_id, p_name, brief_text, stage)

    # Write the prompt to a temp file in the project directory.
    # This avoids Windows command-line length limits and shell argument mangling
    # that can truncate or corrupt multi-line prompts passed as CLI arguments.
    prompt_file_path = project_dir / "agent_prompt.txt"
    try:
        with open(prompt_file_path, "w", encoding="utf-8") as pf:
            pf.write(prompt_text)
    except Exception as e:
        logger.error(f"Failed to write prompt file for {project_id}: {e}")
        return False

    cwd = project_dir.parent.parent  # Workspace root (OpenMontage repo root)
    is_windows = platform.system() == "Windows"

    # Build the subprocess environment: inherit current env + load .env file.
    # This ensures ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, etc. are available
    # to the claude subprocess even when uvicorn was started without them.
    import os as _os
    child_env = _os.environ.copy()
    dotenv_path = cwd / ".env"
    if dotenv_path.exists():
        try:
            for line in dotenv_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.split("#")[0].strip()  # strip inline comments
                if k and v:
                    child_env.setdefault(k, v)  # don't overwrite already-set vars
        except Exception as _e:
            logger.warning(f"Could not load .env for subprocess: {_e}")

    try:
        log_file = open(log_path, "a", encoding="utf-8")
        prompt_fd = open(prompt_file_path, "r", encoding="utf-8")
        
        stage_msg = f"stage '{stage}'" if stage else "full pipeline"
        log_file.write(f"--- Starting Background Agent for {project_id} ({stage_msg}) ---\n")
        log_file.flush()

        # Build command: use executable alias on Windows
        executable = "claude.cmd" if is_windows else "claude"
        cmd_list = [executable, "-p", "--permission-mode", "bypassPermissions"]

        # Run as a detached process on Windows so it doesn't receive Ctrl+C from the UI console,
        # which causes cmd.exe to prompt "Terminate batch job (Y/N)?" and read from our stdin (the prompt).
        kwargs = {}
        if is_windows:
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS

        p = subprocess.Popen(
            cmd_list,
            cwd=str(cwd),
            stdin=prompt_fd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            shell=False,
            text=True,
            env=child_env,
            **kwargs
        )

        # Quick-check: give the process 2 seconds to either produce output or crash.
        # If it exits immediately with a non-zero code, log the failure clearly.
        def _monitor(proc, log_fd, prompt_fd, pid, stg):
            import time
            time.sleep(2)
            rc = proc.poll()
            if rc is not None and rc != 0:
                try:
                    log_fd.write(
                        f"\n[ERROR] Agent process exited immediately with code {rc}.\n"
                        f"  Possible causes:\n"
                        f"  1. 'claude' CLI is not installed or not on PATH.\n"
                        f"     Install: npm install -g @anthropic-ai/claude-code\n"
                        f"  2. API key (ANTHROPIC_API_KEY) is missing or invalid.\n"
                        f"     Check: .env file at project root.\n"
                        f"  3. claude.cmd not found on Windows PATH.\n"
                        f"     Try running 'claude --version' in a terminal.\n"
                    )
                    log_fd.flush()
                except Exception:
                    pass
                # Write a failed checkpoint so the UI shows the error state
                try:
                    import json as _json
                    cp_dir = Path(__file__).resolve().parent.parent / "pipelines" / pid
                    cp_dir.mkdir(parents=True, exist_ok=True)
                    cp_path = cp_dir / f"checkpoint_{stg or 'unknown'}.json"
                    # Only overwrite if currently in_progress
                    if cp_path.exists():
                        existing = _json.loads(cp_path.read_text(encoding="utf-8"))
                        if existing.get("status") == "in_progress":
                            existing["status"] = "failed"
                            existing["error"] = f"Agent process exited with code {rc}. Check agent.log for details."
                            cp_path.write_text(_json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
            # Always close handles when process ends
            try:
                proc.wait()
                log_fd.close()
                prompt_fd.close()
            except Exception:
                pass

        threading.Thread(
            target=_monitor,
            args=(p, log_file, prompt_fd, project_id, stage),
            daemon=True
        ).start()

        logger.info(f"Background agent started for {project_id} (stage={stage})")
        return True
    except FileNotFoundError:
        # claude.cmd / claude not found on PATH
        msg = (
            f"'claude' CLI not found on PATH. "
            f"Install it with: npm install -g @anthropic-ai/claude-code"
        )
        logger.error(msg)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[ERROR] {msg}\n")
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(f"Failed to spawn background agent for {project_id}: {e}")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[ERROR] Failed to start agent subprocess: {e}\n")
        except Exception:
            pass
        return False
