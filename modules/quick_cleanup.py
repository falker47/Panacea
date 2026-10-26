"""Confirmed user-facing cleanup bundle; does not replace native maintenance backends.

Three in-app actions run serially. Windows Disk Cleanup is an external Windows
utility and must be launched by the UI *after* this bundle, not misreported as
a completed fourth automated step.
"""
from modules.operations import OperationStep, run_sequence


COMPONENT_CLEANUP = 'DISM /Online /Cleanup-Image /StartComponentCleanup'


def run_quick_cleanup(cleanup_mgr, command_runner, log, *, cancel=None, progress=None):
    """Execute previously confirmed cleanup using the existing safe managers.

    Progress counts attempted/completed operations; skipped files keep their
    partial status. A command with unknown completion is never treated as a
    successful cleanup, and the caller's persistent guard handles that case.
    """
    def temporary_files():
        count, size = cleanup_mgr.clean_temp_files(progress_callback=log)
        record = cleanup_mgr.last_result
        if (record is None or getattr(record, 'preview', False)
                or type(count) is not int or type(size) is not int
                or count < 0 or size < 0):
            return False, 'Temporary-file results could not be verified.'
        skipped = getattr(record, 'skipped', ())
        errors = getattr(record, 'errors', ())
        ok = not skipped and not errors
        return ok, (f'{count} files removed · {size / 1048576:.1f} MB logical bytes freed · '
                    f'{len(skipped)} skipped · {len(errors)} errors')

    def component_store():
        log('Starting Windows component-store cleanup (DISM).')
        ok = command_runner.run_command_stream(
            COMPONENT_CLEANUP, 'Component store cleanup', log) is True
        if getattr(command_runner, 'completion_unknown', False) is True:
            return False, 'DISM completion unknown; further maintenance is blocked.'
        if getattr(command_runner, 'restart_required', False) is True and ok:
            return True, 'Component cleanup completed; Windows restart required.'
        return ok, 'Component cleanup completed.' if ok else 'Component cleanup failed.'

    steps = (
        OperationStep('Temporary files', temporary_files),
        OperationStep('Recycle Bin', cleanup_mgr.empty_recycle_bin),
        OperationStep('Component store', component_store),
    )
    def should_stop():
        return (bool(getattr(command_runner, 'completion_unknown', False))
                or (cancel is not None and cancel.is_set()))
    return run_sequence(steps, cancel=should_stop, progress=progress)
