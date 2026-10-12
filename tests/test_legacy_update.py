"""Published v1.47 source compatibility, not execution of its old EXE."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from version import VERSION


def test_published_legacy_detection_accepts_candidate_release_manifest(monkeypatch):
    path = Path(__file__).parent / 'fixtures' / 'legacy_v147_update_check.py'
    spec = importlib.util.spec_from_file_location('legacy_update_fixture', path)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    exe = f'https://github.com/falker47/Panacea/releases/download/v{VERSION}/Panacea.exe'
    manifest = {'tag_name': 'v' + VERSION, 'assets': [
        {'name': 'Panacea.exe.sha256', 'browser_download_url': exe + '.sha256'},
        {'name': 'Panacea.exe', 'browser_download_url': exe}]}
    response = SimpleNamespace(read=lambda: json.dumps(manifest).encode('utf-8'))
    class Response:
        def __enter__(self): return response
        def __exit__(self, *args): return False
    calls = []
    def fetch(request, timeout):
        calls.append((request.full_url, timeout))
        return Response()
    monkeypatch.setattr(legacy.urllib.request, 'urlopen', fetch)
    subject = legacy.LegacyUpdateCheck()
    banners = []
    subject.after = lambda delay, callback: callback()
    subject._show_update_banner = lambda remote, url: banners.append((remote, url))
    subject._check_app_update()
    assert calls == [('https://api.github.com/repos/falker47/panacea/releases/latest', 10)]
    assert banners == [(VERSION, exe)]
