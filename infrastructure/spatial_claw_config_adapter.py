"""FILE-018: adapt SpatialClaw config production — must never execute code"""
import os
import json
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

# Mirror SpatialClaw config.py: _expand_env_vars, _load_dotenv logic but isolated (no clone import)
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

def _expand_env_vars(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    def _sub(m: re.Match) -> str:
        name, default = m.group(1), m.group(2)
        return os.environ.get(name, default if default is not None else "")
    return _ENV_VAR_RE.sub(_sub, value)

@dataclass
class LLMRoleParams:
    max_tokens: int = 16384
    temperature: float = 0.6
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    min_p: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    enable_thinking: Optional[bool] = None
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LLMRoleParams":
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid and v is not None})

@dataclass
class SpatialClawConfig:
    """Production config — mirrors cloning/nvidia-spatial-claw/spatial_agent/config.py:SpatialAgentConfig but adapted"""
    benchmark: str = "erqa"
    question_type: Optional[List[str]] = None
    limit: Optional[int] = None
    sample_ids: Optional[List[str]] = None
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    main_params: LLMRoleParams = field(default_factory=LLMRoleParams)
    vlm_params: LLMRoleParams = field(default_factory=lambda: LLMRoleParams(temperature=0.1, enable_thinking=True))
    vlm_grounding_params: LLMRoleParams = field(default_factory=lambda: LLMRoleParams(max_tokens=16384, temperature=0.1, enable_thinking=True))
    planning_params: LLMRoleParams = field(default_factory=lambda: LLMRoleParams(temperature=1.0))
    general_params: LLMRoleParams = field(default_factory=lambda: LLMRoleParams(max_tokens=32768, enable_thinking=False))
    max_steps: int = 30
    max_failures: int = 30
    max_tool_calls: int = -1
    timeout_sec: int = 600  # production per SpatialClaw config.py
    executor_type: str = "code"
    tools_to_use: List[str] = field(default_factory=lambda: ["Reconstruct", "SAM3"])
    reconstruct_backend: str = "da3"
    reconstruct_max_frames: int = 64
    sam3_max_video_frames: int = 1000
    vlm_query_timeout_sec: int = 600
    video_max_fps: Optional[float] = None
    image_max_long_edge: Optional[int] = 768
    num_key_frames: int = 32
    work_dir: Optional[str] = None
    enable_logging: bool = True
    generate_report: bool = True
    enable_planning: bool = True
    enable_reflection: bool = False
    concurrency: int = 8
    enable_sighted_feedback: bool = True
    gpu_server: str = "auto"
    condense_errors: bool = True
    max_variable_size_mb: int = 500

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for f in fields(self):
            v = getattr(self, f.name)
            result[f.name] = v.to_dict() if isinstance(v, LLMRoleParams) else v
        return result

class SpatialClawConfigAdapter:
    """SRP: adapt SpatialClaw config production — priority CLI > JSON > ENV(SPATIAL_AGENT_*) > defaults, with ${VAR} expansion"""

    @staticmethod
    def load(cli_args: Optional[Dict[str, Any]] = None, model_json: Optional[str] = None, dataset_json: Optional[str] = None) -> SpatialClawConfig:
        """METHOD-017: production load with correct priority"""
        cfg = SpatialClawConfig()

        # 1. Defaults already in dataclass

        # 2. ENV (SPATIAL_AGENT_*) — lowest after defaults, before JSON/CLI
        for f in fields(cfg):
            if isinstance(getattr(cfg, f.name), LLMRoleParams):
                continue
            env_name = f"SPATIAL_AGENT_{f.name.upper()}"
            env_val = os.getenv(env_name)
            if env_val is not None:
                converted = SpatialClawConfigAdapter._convert_type(env_val, str(f.type), f.name)
                if converted is not None:
                    setattr(cfg, f.name, converted)

        # 3. Dataset JSON
        if dataset_json and os.path.exists(dataset_json):
            with open(dataset_json) as fh:
                data = json.load(fh)
            for k, v in data.items():
                if v is not None and hasattr(cfg, k):
                    setattr(cfg, k, v)

        # 4. Model JSON — connection + roles, with ${VAR} expansion
        if model_json and os.path.exists(model_json):
            with open(model_json) as fh:
                data = json.load(fh)
            for key in ("llm_model", "llm_base_url", "llm_api_key"):
                if key in data and data[key] is not None:
                    setattr(cfg, key, _expand_env_vars(data[key]))
            roles = data.get("roles", {})
            role_map = {
                "main": "main_params",
                "vlm": "vlm_params",
                "vlm_grounding": "vlm_grounding_params",
                "planning": "planning_params",
                "general": "general_params",
                "reflection": "reflection_params",
            }
            for role_name, attr in role_map.items():
                if role_name in roles:
                    # reflection_params may not exist on cfg for minimal case
                    if hasattr(cfg, attr):
                        setattr(cfg, attr, LLMRoleParams.from_dict(roles[role_name]))

        # 5. CLI highest priority
        if cli_args:
            for k, v in cli_args.items():
                if v is not None and hasattr(cfg, k):
                    setattr(cfg, k, v)

        return cfg

    @staticmethod
    def _convert_type(value: str, type_hint: str, field_name: str) -> Any:
        if "bool" in type_hint:
            return value.lower() in ("true", "1", "yes")
        if "int" in type_hint and "Optional" not in type_hint:
            try: return int(value)
            except: return None
        if "Optional[int]" in type_hint:
            return int(value) if value else None
        if "float" in type_hint and "Optional" not in type_hint:
            try: return float(value)
            except: return None
        if "Optional[float]" in type_hint:
            return float(value) if value else None
        if "List[str]" in type_hint:
            return [s.strip() for s in value.split(",")]
        return value

    @staticmethod
    def health_check(cfg: SpatialClawConfig) -> Dict[str, Any]:
        return {
            "benchmark": cfg.benchmark,
            "timeout_sec": cfg.timeout_sec,
            "executor_type": cfg.executor_type,
            "tools_to_use": cfg.tools_to_use,
            "llm_model": cfg.llm_model,
            "work_dir": cfg.work_dir,
            "enable_logging": cfg.enable_logging,
        }
