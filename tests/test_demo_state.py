import copy
import json
import os
import tempfile
import unittest

import app


class DemoStateTests(unittest.TestCase):
    def setUp(self):
        app._reset_demo_state()
        self.client = app.app.test_client()
        self.headers = {
            "X-Demo-State-Token": "demo-wip-token",
            "Content-Type": "application/json",
        }

    def test_default_state_shape(self):
        res = self.client.get("/demo-state")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "idle")
        self.assertEqual(data["mode"], "idle")
        self.assertEqual(set(data["pipeline"].keys()), set(app.PIPELINE_KEYS))
        self.assertTrue(all(v == "pending" for v in data["pipeline"].values()))

    def test_get_returns_copy(self):
        res1 = self.client.get("/demo-state").get_json()
        res1["pipeline"]["code"] = "success"
        res2 = self.client.get("/demo-state").get_json()
        self.assertEqual(res2["pipeline"]["code"], "pending")

    def test_auth_accepts_both_headers(self):
        for header in ("X-Wip-Token", "X-Demo-State-Token"):
            app._reset_demo_state()
            res = self.client.post(
                "/demo-state",
                headers={header: "demo-wip-token", "Content-Type": "application/json"},
                json={"status": "in-progress", "mode": "demo"},
            )
            self.assertEqual(res.status_code, 200, msg=header)

    def test_unauthorized(self):
        res = self.client.post("/demo-state", json={"status": "idle"})
        self.assertEqual(res.status_code, 401)
        res = self.client.post(
            "/demo-state",
            headers={"X-Demo-State-Token": "wrong"},
            json={"status": "idle"},
        )
        self.assertEqual(res.status_code, 401)

    def test_invalid_status_and_mode(self):
        res = self.client.post("/demo-state", headers=self.headers, json={"status": "nope"})
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/demo-state", headers=self.headers, json={"mode": "nope"})
        self.assertEqual(res.status_code, 400)

    def test_invalid_pipeline_value_ignored(self):
        res = self.client.post(
            "/demo-state",
            headers=self.headers,
            json={"pipeline": {"code": "bogus", "ci": "running"}},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["pipeline"]["code"], "pending")
        self.assertEqual(data["pipeline"]["ci"], "running")

    def test_partial_update_preserves_fields(self):
        self.client.post(
            "/demo-state",
            headers=self.headers,
            json={
                "status": "in-progress",
                "mode": "demo",
                "message": "msg",
                "theme": "theme",
            },
        )
        res = self.client.post(
            "/demo-state",
            headers=self.headers,
            json={"pipeline": {"ci": "running"}},
        )
        data = res.get_json()
        self.assertEqual(data["status"], "in-progress")
        self.assertEqual(data["mode"], "demo")
        self.assertEqual(data["message"], "msg")
        self.assertEqual(data["theme"], "theme")
        self.assertEqual(data["pipeline"]["ci"], "running")

    def test_idle_resets_started_and_gitpushed_when_status_provided(self):
        self.client.post(
            "/demo-state",
            headers=self.headers,
            json={"status": "in-progress", "mode": "demo", "gitPushed": True},
        )
        data = self.client.get("/demo-state").get_json()
        self.assertTrue(data["started"])
        self.assertTrue(data["gitPushed"])
        self.client.post(
            "/demo-state",
            headers=self.headers,
            json={"status": "idle", "mode": "idle"},
        )
        data = self.client.get("/demo-state").get_json()
        self.assertEqual(data["started"], "")
        self.assertFalse(data["gitPushed"])

    def test_pipeline_only_does_not_reset_started(self):
        self.client.post(
            "/demo-state",
            headers=self.headers,
            json={"status": "in-progress", "mode": "demo"},
        )
        before = self.client.get("/demo-state").get_json()["started"]
        self.client.post(
            "/demo-state",
            headers=self.headers,
            json={"pipeline": {"ci": "success"}},
        )
        after = self.client.get("/demo-state").get_json()["started"]
        self.assertEqual(before, after)

    def test_init_from_raz_marker(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write('<meta name="demo-state" content="raz">')
            path = f.name
        try:
            app._reset_demo_state()
            app._init_demo_state_from_index(path)
            data = app._demo_state_copy() if hasattr(app, "_demo_state_copy") else None
        finally:
            os.unlink(path)
        self.assertIsNotNone(data)
        self.assertEqual(data["mode"], "raz")
        self.assertEqual(data["status"], "idle")
        self.assertTrue(all(v == "pending" for v in data["pipeline"].values()))

    def test_wip_status_alias(self):
        res = self.client.get("/wip-status")
        self.assertEqual(res.status_code, 200)
        res = self.client.post(
            "/wip-status",
            headers=self.headers,
            json={"status": "idle"},
        )
        self.assertEqual(res.status_code, 200)

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
