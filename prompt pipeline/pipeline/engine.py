"""
pipeline/engine.py — Core pipeline orchestration engine.

Responsibilities:
- Accept raw user input + task_id + model
- Look up the correct prompt templates and schemas
- Run stages 1→4 sequentially, passing JSON between stages
- Validate each stage output against its Pydantic schema
- Return a PipelineResult with full transparency data
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import ValidationError

from services.openrouter_client import OpenRouterClient, StageResult
from schemas import TASK_SCHEMAS, BaseStageOutput
import config as cfg

logger = logging.getLogger("prompt_pipeline.engine")

# ─── Prompt module registry (lazy-imported to avoid circular imports) ─────────
_PROMPT_MODULES: dict[str, Any] = {}

def _get_prompts(task_id: str) -> dict[int, dict[str, str]]:
    """Lazily import and cache the prompt module for a given task."""
    if task_id not in _PROMPT_MODULES:
        import importlib
        module = importlib.import_module(f"prompts.{task_id}")
        _PROMPT_MODULES[task_id] = module.PROMPTS
    return _PROMPT_MODULES[task_id]


# ─── Result types ─────────────────────────────────────────────────────────────

@dataclass
class StageExecution:
    """Complete record of one stage execution."""
    stage_num:        int
    stage_name:       str
    system_prompt:    str           = ""
    user_prompt:      str           = ""
    raw_response:     str           = ""
    parsed_json:      dict          = field(default_factory=dict)
    validated_data:   Optional[Any] = None   # Pydantic model instance
    validation_error: Optional[str] = None
    latency_ms:       float         = 0.0
    retries:          int           = 0
    prompt_tokens:    int           = 0
    completion_tokens:int           = 0
    total_tokens:     int           = 0
    model:            str           = ""
    success:          bool          = True
    error:            Optional[str] = None


@dataclass
class PipelineResult:
    """Complete result of a full pipeline run."""
    task_id:        str
    task_name:      str
    model:          str
    raw_input:      str
    stages:         list[StageExecution] = field(default_factory=list)
    final_output:   dict                 = field(default_factory=dict)
    total_latency_ms: float              = 0.0
    total_tokens:   int                  = 0
    success:        bool                 = True
    error:          Optional[str]        = None
    timestamp:      str                  = ""

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON export / session storage."""
        return {
            "task_id":          self.task_id,
            "task_name":        self.task_name,
            "model":            self.model,
            "raw_input":        self.raw_input,
            "total_latency_ms": self.total_latency_ms,
            "total_tokens":     self.total_tokens,
            "success":          self.success,
            "error":            self.error,
            "timestamp":        self.timestamp,
            "final_output":     self.final_output,
            "stages": [
                {
                    "stage_num":         s.stage_num,
                    "stage_name":        s.stage_name,
                    "parsed_json":       s.parsed_json,
                    "latency_ms":        s.latency_ms,
                    "retries":           s.retries,
                    "prompt_tokens":     s.prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "total_tokens":      s.total_tokens,
                    "success":           s.success,
                    "error":             s.error,
                    "system_prompt":     s.system_prompt,
                    "user_prompt":       s.user_prompt,
                }
                for s in self.stages
            ],
        }


# ─── Stage name labels ─────────────────────────────────────────────────────────
STAGE_NAMES = {
    1: "🔍 Stage 1 — Extraction",
    2: "🧠 Stage 2 — Reasoning",
    3: "✍️  Stage 3 — Generation",
    4: "🔎 Stage 4 — Self-Critic",
}


# ─── Pipeline Engine ───────────────────────────────────────────────────────────

class PipelineEngine:
    """
    Orchestrates a 4-stage prompt pipeline for any supported task.

    Each stage:
    1. Formats its prompts using JSON from prior stages
    2. Calls the LLM via OpenRouterClient
    3. Parses and validates the JSON output
    4. Passes only the structured JSON to the next stage

    Stage 4 is the self-critic: if quality_score < 7.0, it regenerates stage 3.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model:   Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        """
        Args:
            api_key:           OpenRouter API key (falls back to .env)
            model:             Model slug (falls back to DEFAULT_MODEL in .env)
            progress_callback: Optional callable(stage_num, message) for UI updates
        """
        self.client   = OpenRouterClient(api_key=api_key, model=model)
        self.model    = self.client.model
        self.progress = progress_callback or (lambda s, m: None)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_stage(
        self,
        task_id: str,
        stage_idx: int,      # 0-based index into TASK_SCHEMAS[task_id]
        data: dict,
    ) -> tuple[Optional[BaseStageOutput], Optional[str]]:
        """Attempt Pydantic validation. Returns (model_instance, error_str)."""
        schemas = TASK_SCHEMAS.get(task_id)
        if not schemas or stage_idx >= len(schemas):
            return None, None   # No schema available — skip validation

        schema_cls = schemas[stage_idx]
        try:
            validated = schema_cls(**data)
            return validated, None
        except ValidationError as e:
            err = f"Schema validation warning: {e}"
            logger.warning(err)
            return None, err

    def _build_user_prompt(
        self,
        template: str,
        raw_input: str,
        stage_outputs: dict[int, dict],   # stage_num → parsed_json
    ) -> str:
        """
        Fill prompt template placeholders.

        Available placeholders: {raw_input}, {stage1_json}, {stage2_json}, {stage3_json}
        """
        kwargs: dict[str, str] = {"raw_input": raw_input}
        for stage_num, output in stage_outputs.items():
            kwargs[f"stage{stage_num}_json"] = json.dumps(output, indent=2)

        try:
            return template.format(**kwargs)
        except KeyError:
            # If a placeholder is missing (e.g., stage2_json not yet available),
            # replace missing placeholders with empty JSON
            for key in ["stage1_json", "stage2_json", "stage3_json"]:
                if key not in kwargs:
                    kwargs[key] = "{}"
            return template.format(**kwargs)

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, task_id: str, raw_input: str) -> PipelineResult:
        """
        Execute the complete 4-stage pipeline.

        Args:
            task_id:   Task identifier (e.g. "support_triage")
            raw_input: Raw user-provided text

        Returns:
            PipelineResult with full stage-by-stage data
        """
        import datetime

        task_name = next(
            (v["id"] for k, v in cfg.PIPELINE_TASKS.items() if v["id"] == task_id),
            task_id,
        )
        # Get display name
        display_name = next(
            (k for k, v in cfg.PIPELINE_TASKS.items() if v["id"] == task_id),
            task_id,
        )

        prompts = _get_prompts(task_id)

        result = PipelineResult(
            task_id    = task_id,
            task_name  = display_name,
            model      = self.model,
            raw_input  = raw_input,
            timestamp  = datetime.datetime.now().isoformat(timespec="seconds"),
        )

        t_pipeline_start  = time.perf_counter()
        stage_outputs: dict[int, dict] = {}  # stage_num → parsed_json

        # ── Stages 1–4 ───────────────────────────────────────────────────────
        for stage_num in range(1, 5):
            stage_name = STAGE_NAMES[stage_num]
            self.progress(stage_num, f"Running {stage_name}...")

            prompt_cfg   = prompts[stage_num]
            system_prompt = prompt_cfg["system"]
            user_prompt   = self._build_user_prompt(
                prompt_cfg["user"], raw_input, stage_outputs
            )

            logger.info("=== %s [%s] ===", stage_name, task_id)

            # LLM call
            stage_result: StageResult = self.client.call_stage(
                stage         = stage_num,
                task_id       = task_id,
                system_prompt = system_prompt,
                user_prompt   = user_prompt,
            )

            # Pydantic validation (non-blocking — just logs a warning)
            validated, val_error = self._validate_stage(
                task_id, stage_num - 1, stage_result.parsed_json
            )

            exec_record = StageExecution(
                stage_num         = stage_num,
                stage_name        = stage_name,
                system_prompt     = system_prompt,
                user_prompt       = user_prompt,
                raw_response      = stage_result.raw_response,
                parsed_json       = stage_result.parsed_json,
                validated_data    = validated,
                validation_error  = val_error,
                latency_ms        = stage_result.latency_ms,
                retries           = stage_result.retries,
                prompt_tokens     = stage_result.prompt_tokens,
                completion_tokens = stage_result.completion_tokens,
                total_tokens      = stage_result.total_tokens,
                model             = stage_result.model,
                success           = stage_result.success,
                error             = stage_result.error,
            )
            result.stages.append(exec_record)

            # On failure: record error and stop pipeline
            if not stage_result.success:
                result.success = False
                result.error   = f"Stage {stage_num} failed: {stage_result.error}"
                logger.error(result.error)
                break

            # Store JSON for next stage's prompt
            stage_outputs[stage_num] = stage_result.parsed_json

            # ── Stage 4 special: extract final_output ─────────────────────
            if stage_num == 4 and stage_result.success:
                s4_data = stage_result.parsed_json
                if s4_data.get("regenerate", False):
                    logger.info(
                        "Stage 4 triggered regeneration (quality=%.1f)",
                        s4_data.get("quality_score", 0),
                    )
                result.final_output = s4_data.get("final_output", stage_outputs.get(3, {}))

        # If pipeline stopped before stage 4, use stage 3 output as final
        if not result.final_output and 3 in stage_outputs:
            result.final_output = stage_outputs[3]

        result.total_latency_ms = (time.perf_counter() - t_pipeline_start) * 1000
        result.total_tokens     = sum(s.total_tokens for s in result.stages)

        self.progress(5, "✅ Pipeline complete!")
        logger.info(
            "Pipeline done | task=%s | total=%.0fms | tokens=%d | success=%s",
            task_id, result.total_latency_ms, result.total_tokens, result.success,
        )

        return result
