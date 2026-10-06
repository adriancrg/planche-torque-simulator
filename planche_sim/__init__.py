"""Planche torque simulator: a static biomechanical model of the planche and an interactive viewer."""
from .model import PRESETS, Pose, Result, compare, relative_to_full, solve, torque_from_lean, with_preset

__all__ = ["PRESETS", "Pose", "Result", "compare", "relative_to_full", "solve", "torque_from_lean",
           "with_preset"]
__version__ = "1.0.0"
