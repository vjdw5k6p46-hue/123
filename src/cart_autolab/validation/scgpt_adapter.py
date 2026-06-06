from __future__ import annotations


class ScGPTValidationAdapter:
    """Optional future extension for transcriptomic consistency checks.

    This adapter does not replace PhysiCell. It is reserved for annotation of
    simulated CAR-T states, perturbation-informed checking, and comparison with
    single-cell signatures when the user supplies scGPT installation and model
    assets.
    """

    def available(self) -> bool:
        return False

    def validate_states(self, *_args, **_kwargs) -> dict:
        return {
            "status": "not_configured",
            "message": "Install and configure scGPT or another single-cell foundation model to enable this optional validation path.",
        }
