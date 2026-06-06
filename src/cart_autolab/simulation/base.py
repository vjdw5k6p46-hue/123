from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SimulatorAdapter(ABC):
    @abstractmethod
    def prepare_inputs(self, plan: list[dict], parameters: list[dict], run_dir: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_config(self, run_dir: Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def run(self, run_dir: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def parse_outputs(self, run_dir: Path) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def summarize_results(self, run_dir: Path) -> dict:
        raise NotImplementedError
