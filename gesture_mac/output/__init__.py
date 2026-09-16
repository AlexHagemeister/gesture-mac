"""Performs actions on macOS. The only package that imports Quartz.
MacPerformer satisfies mapping.mapper.Performer."""
from .performer import MacPerformer, accessibility_trusted

__all__ = ["MacPerformer"]
