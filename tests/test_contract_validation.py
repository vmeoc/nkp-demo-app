import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"
RENDER = ROOT / ".opencode/skills/nkp-deploy/render.py"


def validate(contract):
    return subprocess.run(
        [str(PYTHON), str(RENDER), "--validate-input"],
        cwd=ROOT,
        input=json.dumps(contract),
        capture_output=True,
        text=True,
        check=True,
    )


def valid_contract():
    return {
        "app": "hello-nkp",
        "owner": "vincent",
        "env": "dev",
        "archi": "stateless",
        "runtime": "python",
        "port": 8080,
        "size": "S",
        "backup": "none",
        "tracing": True,
        "expose": {"type": "loadbalancer"},
        "llm": "none",
        "expires": "2099-12-31",
    }


class ContractValidationTests(unittest.TestCase):
    def test_valid_contract_returns_effective_replicas_and_warnings(self):
        result = json.loads(validate(valid_contract()).stdout)

        self.assertTrue(result["valid"])
        self.assertEqual(result["replicas"], 1)
        self.assertEqual(result["error_type"], "rules")
        self.assertTrue(any("OpenTelemetry" in warning for warning in result["warnings"]))

    def test_prod_requires_cost_center(self):
        contract = valid_contract()
        contract.update({"env": "prod", "replicas": 2})

        result = json.loads(validate(contract).stdout)

        self.assertFalse(result["valid"])
        self.assertIn("cost_center : obligatoire en prod.", result["errors"])

    def test_static_runtime_cannot_use_tracing(self):
        contract = valid_contract()
        contract["runtime"] = "static"

        result = json.loads(validate(contract).stdout)

        self.assertFalse(result["valid"])
        self.assertTrue(any("ne s'applique pas à un site statique" in error for error in result["errors"]))

    def test_schema_errors_are_reported_before_platform_rules(self):
        contract = valid_contract()
        contract["port"] = 70000
        contract["expose"] = {"type": "ingress"}

        result = json.loads(validate(contract).stdout)

        self.assertFalse(result["valid"])
        self.assertEqual(result["error_type"], "schema")
        self.assertTrue(any("port" in error for error in result["errors"]))
        self.assertTrue(any("host" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
