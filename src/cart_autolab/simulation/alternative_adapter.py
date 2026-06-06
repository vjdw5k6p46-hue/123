from __future__ import annotations

from pathlib import Path

from .base import SimulatorAdapter


class VitruCellAdapter(SimulatorAdapter):
    """Optional placeholder for an externally supplied compatible simulator.

    Alternative compatible multicellular simulation engines can be substituted
    through the same adapter interface. This placeholder intentionally makes no
    unsupported installation or API claims.
    """

    def prepare_inputs(self, plan: list[dict], parameters: list[dict], run_dir: Path) -> None:
        raise NotImplementedError("Provide VitruCell installation details and API bindings before use.")

    def write_config(self, run_dir: Path) -> Path:
        raise NotImplementedError("Provide VitruCell installation details and API bindings before use.")

    def run(self, run_dir: Path) -> None:
        raise NotImplementedError("Provide VitruCell installation details and API bindings before use.")

    def parse_outputs(self, run_dir: Path) -> list[dict]:
        raise NotImplementedError("Provide VitruCell installation details and API bindings before use.")

    def summarize_results(self, run_dir: Path) -> dict:
        raise NotImplementedError("Provide VitruCell installation details and API bindings before use.")
