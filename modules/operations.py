"""Sequential maintenance results; cancellation is honored between commands."""
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class OperationStep:
    name: str
    action: Callable
    critical: bool = False


@dataclass(frozen=True)
class StepResult:
    name: str
    success: bool
    message: str


@dataclass
class OperationResult:
    status: str
    steps: list = field(default_factory=list)
    error: str = ''


def run_sequence(steps, cancel=None, progress=None):
    """Run already-confirmed steps, stopping if a safety prerequisite fails.

    Each action returns bool or (bool, message). This strict contract avoids
    interpreting a nonzero exit code, deletion count or None as success.
    """
    steps = list(steps)
    results = []
    for step in steps:
        try:
            if cancel is not None and (cancel.is_set() if hasattr(cancel, 'is_set') else cancel()):
                return OperationResult('cancelled', results)
        except Exception as exc:
            return OperationResult('partial' if any(item.success for item in results) else 'failed', results,
                                   f'Cancellation check failed: {exc}')
        try:
            value = step.action()
            if type(value) is bool:
                success, message = value, 'Completed.' if value else 'Failed.'
            elif isinstance(value, tuple) and len(value) == 2 and type(value[0]) is bool:
                success, message = value[0], str(value[1])
            else:
                success, message = False, 'Operation returned an unverified result.'
        except Exception as exc:
            success, message = False, str(exc)
        result = StepResult(step.name, success, message)
        results.append(result)
        if progress:
            try:
                progress(len(results), len(steps), result)
            except Exception as exc:
                return OperationResult('partial' if any(item.success for item in results) else 'failed', results,
                                       f'Progress reporting failed: {exc}')
        if step.critical and not success:
            return OperationResult('partial' if any(item.success for item in results) else 'failed', results)
    status = ('completed' if all(item.success for item in results)
              else 'partial' if any(item.success for item in results) else 'failed')
    return OperationResult(status, results)
