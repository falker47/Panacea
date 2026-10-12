def test_frozen_uac_does_not_pass_exe_as_script():
    from main import elevation_arguments
    assert elevation_arguments([r"C:\Program Files\Panacea\Panacea.exe", "--flag", "with space"], frozen=True) == '--flag "with space"'


def test_source_uac_quotes_script_path():
    from main import elevation_arguments
    assert elevation_arguments([r"C:\Code folder\main.py", "--flag"], frozen=False) == '"C:\\Code folder\\main.py" --flag'


def test_smoke_mode_cannot_enable_maintenance():
    from main import parse_startup_args
    args = parse_startup_args(["--smoke-test"])
    assert args.smoke_test
    assert args.panacea_update_helper is None
    assert args.panacea_update_ready is None


def test_packaged_smoke_rejects_collapsed_window(monkeypatch):
    import main
    import panacea_ui
    class CollapsedApp:
        def __init__(self):
            self.callbacks = []
        def after(self, delay, callback):
            self.callbacks.append(callback)
        def winfo_ismapped(self):
            return True
        def winfo_width(self):
            return 200
        def winfo_height(self):
            return 200
        def _on_close(self):
            pass
        def mainloop(self):
            for callback in self.callbacks:
                callback()
    monkeypatch.setattr(panacea_ui, 'PanaceaApp', CollapsedApp)
    assert main.main(['--smoke-test']) == 1


def test_frozen_uac_relaunch_requests_fresh_extraction_environment(monkeypatch):
    import main
    from modules import utils
    monkeypatch.setattr(main.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(utils, 'is_admin', lambda: False)
    monkeypatch.setenv('PYINSTALLER_RESET_ENVIRONMENT', '0')
    observed = []
    def elevated(*args):
        import os
        observed.append(os.environ.get('PYINSTALLER_RESET_ENVIRONMENT'))
        return 33
    monkeypatch.setattr(main.ctypes.windll.shell32, 'ShellExecuteW', elevated)
    assert main.main([]) == 0
    assert observed == ['1']


def test_smoke_detects_error_swallowed_by_ui_dispatcher(monkeypatch):
    import logging
    import main
    import panacea_ui
    class UsableApp:
        def __init__(self):
            self.callbacks = []
        def after(self, delay, callback):
            self.callbacks.append(callback)
        def winfo_ismapped(self):
            return True
        def winfo_width(self):
            return 1020
        def winfo_height(self):
            return 680
        def _on_close(self):
            pass
        def mainloop(self):
            logging.getLogger('modules.ui_dispatch').error('UI callback failed')
            for callback in self.callbacks:
                callback()
    monkeypatch.setattr(panacea_ui, 'PanaceaApp', UsableApp)
    assert main.main(['--smoke-test']) == 1
