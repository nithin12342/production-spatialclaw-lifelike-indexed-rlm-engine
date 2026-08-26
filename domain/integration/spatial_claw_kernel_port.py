"""FILE-016: define kernel port interface — must never import clone"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class ExecutionResult:
    """Structured result from single cell execution — mirrors SpatialClaw kernel/manager.py:38"""
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    display_data: List[Any] = field(default_factory=list)
    execution_time_sec: float = 0.0

@dataclass
class KernelConfig:
    timeout_sec: int = 600  # SpatialClaw default 600 per config.py
    kernel_name: str = "python3"
    max_steps: int = 30
    max_failures: int = 30

class SpatialClawKernelPort(ABC):
    """SRP: define kernel port interface — domain owns, infra implements (DIP)"""

    @abstractmethod
    async def start(self) -> str:
        """METHOD-015: start kernel, return kernel_id"""
        raise NotImplementedError

    @abstractmethod
    async def execute(self, code: str, timeout: Optional[int] = None) -> ExecutionResult:
        """METHOD-015: execute cell with timeout enforcement, interrupt on timeout"""
        raise NotImplementedError

    @abstractmethod
    async def get_variables(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def check_sentinel(self, sentinel_name: str = "_return_answer_result") -> Optional[Dict]:
        raise NotImplementedError

    @abstractmethod
    async def clear_sentinel(self, sentinel_name: str = "_return_answer_result") -> None:
        raise NotImplementedError

    @abstractmethod
    async def reset_namespace(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def restart(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_running(self) -> bool:
        raise NotImplementedError
