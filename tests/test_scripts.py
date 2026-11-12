import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / ".opencode/skills/nkp-deploy/check_deploy.sh"
RESET = ROOT / "reset-demo.sh"


class ScriptTests(unittest.TestCase):
    def test_bash_syntax(self):
        for path in (CHECK, RESET):
            subprocess.run(["bash", "-n", str(path)], check=True)

    def test_check_deploy_has_post_state(self):
        text = CHECK.read_text()
        self.assertIn("post_state()", text)
        self.assertIn("DEMO_STATE_TOKEN_RESOLVED", text)
        self.assertIn("Content-Type: application/json", text)

    def test_reset_mentions_pending(self):
        text = RESET.read_text()
        self.assertIn('"code":"pending"', text)
        self.assertIn('mode":"raz"', text)

    def test_no_hardcoded_token_in_curl(self):
        # reset-demo must not hardcode the token in its curl call
        text = RESET.read_text()
        self.assertNotIn("X-Demo-State-Token: demo-wip-token", text)


if __name__ == "__main__":
    unittest.main()
