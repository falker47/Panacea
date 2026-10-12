# Frozen source excerpt from falker47/Panacea tag v1.47 (d191f6c2a0ea4a6e9f3a2c37f913d516c2c2a9c9).
# Only update detection/comparison is retained; all IO is replaced by tests.
import json
import urllib.request
VERSION = '1.47'
GITHUB_REPO = 'falker47/panacea'

class LegacyUpdateCheck:
    def _check_app_update(self):
        """Check GitHub releases for a newer version of Panacea."""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "Panacea"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            remote_tag = data.get("tag_name", "").lstrip("v")
            if remote_tag and self._is_newer(remote_tag, VERSION):
                # Find .exe asset download URL
                exe_url = None
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".exe"):
                        exe_url = asset.get("browser_download_url")
                        break
                self.after(0, lambda: self._show_update_banner(remote_tag, exe_url))
        except Exception:
            pass

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        """Compare dotted version strings (e.g. '1.40' > '1.39')."""
        try:
            r_parts = [int(x) for x in remote.split(".")]
            l_parts = [int(x) for x in local.split(".")]
            return r_parts > l_parts
        except ValueError:
            return False
