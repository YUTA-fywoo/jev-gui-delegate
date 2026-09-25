"""Controlled failure injection only; these tests never count as live API success."""
import asyncio
import contextlib
import io
import json
import logging
import socket
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx2
from typesafe_sdk import SystemOneResponse
from jev_client import (ROOT, JevClient, BridgeError, Settings, load_settings,
    EvaluationInput, validate_response, guard_model, database, statistics)

SENTINEL="synthetic-secret-for-leak-test"
PAYLOAD=json.loads((ROOT/"example.json").read_text("utf-8"))

class FailureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/"usage.sqlite3"
        self.output=io.StringIO()
        self.handler=logging.StreamHandler(self.output)
        logging.getLogger().addHandler(self.handler)

    async def asyncTearDown(self):
        logging.getLogger().removeHandler(self.handler)
        self.assertNotIn(SENTINEL,self.output.getvalue())
        if self.db.exists():
            self.assertNotIn(SENTINEL.encode(),self.db.read_bytes())
        self.temp.cleanup()

    def client(self,transport=None,**kw):
        return JevClient(transport=transport,usage_path=self.db,
            credential_resolver=lambda:(SENTINEL,"synthetic-test"),**kw)

    async def error(self,client,code,payload=PAYLOAD,attempts=None):
        with self.assertRaises(BridgeError) as raised:
            await client.evaluate(payload)
        self.assertEqual(raised.exception.code,code)
        if attempts is not None: self.assertEqual(raised.exception.attempts,attempts)
        self.assertNotIn(SENTINEL,str(raised.exception))

    async def test_missing_key_zero_requests(self):
        client=JevClient(usage_path=self.db,credential_resolver=lambda:(None,"missing"))
        await self.error(client,"MISSING_API_KEY",attempts=0)

    async def test_invalid_input_zero_requests(self):
        await self.error(self.client(),"INVALID_INPUT",{"state":{},"questions":{}},0)
        bad=json.loads(json.dumps(PAYLOAD));bad["questions"]["readiness"]["criteria"]=["only one"]
        await self.error(self.client(),"INVALID_INPUT",bad,0)

    async def test_invalid_config_and_alias_calibration(self):
        path=Path(self.temp.name)/"settings.json"
        path.write_text('{"model":"jev-latest","max_retries":999}',encoding="utf-8")
        with self.assertRaises(BridgeError) as raised: load_settings(path)
        self.assertEqual(raised.exception.code,"INVALID_CONFIG")
        with self.assertRaises(ValueError): Settings(model="jev-latest",expected_model="jev-1.13.0",calibrated=True)

    async def test_401_no_retry_no_response_body_leak(self):
        transport=httpx2.MockTransport(lambda r:httpx2.Response(401,json={"error":SENTINEL}))
        await self.error(self.client(transport),"AUTHENTICATION_FAILED",attempts=1)

    async def test_429_bounded_retry(self):
        transport=httpx2.MockTransport(lambda r:httpx2.Response(429,json={"error":SENTINEL},headers={"retry-after":"0"}))
        await self.error(self.client(transport),"RATE_LIMITED",attempts=3)

    async def test_retry_after_larger_than_budget(self):
        transport=httpx2.MockTransport(lambda r:httpx2.Response(529,json={"error":SENTINEL},headers={"retry-after":"600"}))
        await self.error(self.client(transport),"SERVICE_OVERLOADED",attempts=1)

    async def test_actual_local_connection_refused_bounded(self):
        sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        # Bound but not listening: deterministic loopback connection refusal, no real key.
        class LoopbackTransport(httpx2.AsyncBaseTransport):
            async def handle_async_request(self,request):
                async with httpx2.AsyncHTTPTransport(retries=0) as real:
                    request.url=httpx2.URL(f"http://127.0.0.1:{port}/failure-test")
                    return await real.handle_async_request(request)
        try: await self.error(self.client(LoopbackTransport()),"NETWORK_ERROR",attempts=3)
        finally: sock.close()

    async def test_absolute_timeout_cancels(self):
        async def slow(_request):
            await asyncio.sleep(5)
            return httpx2.Response(500)
        settings=Settings(model="jev-latest",operation_timeout_seconds=0.1,total_timeout_seconds=0.2)
        await self.error(self.client(httpx2.MockTransport(slow),settings=settings),"NETWORK_TIMEOUT",attempts=1)

    async def test_invalid_response_rejected(self):
        transport=httpx2.MockTransport(lambda r:httpx2.Response(200,json={"model":"jev-1.13.0","answers":{},"usage":{"input_tokens":1,"output_tokens":1}}))
        await self.error(self.client(transport),"INVALID_RESPONSE",attempts=1)

    async def test_probability_validation(self):
        # Direct validator fixture, explicitly not an API-success test.
        response=SystemOneResponse(model="jev-1.13.0",usage={"input_tokens":1,"output_tokens":1},
            answers={"q":{"type":"choice","choice":"a","confidence":0.5,"probabilities":{"a":0.8,"b":0.8}}})
        req=EvaluationInput.model_validate({"state":"fixture","questions":{"q":{"type":"choice","instructions":"pick","criteria":{"a":None,"b":None}}}})
        with self.assertRaises(BridgeError): validate_response(response,req)

    async def test_model_change_guard(self):
        settings=Settings(model="jev-latest")
        guard_model(settings,"jev-1.13.0",self.db)
        with self.assertRaises(BridgeError) as raised: guard_model(settings,"jev-99.0.0",self.db)
        self.assertEqual(raised.exception.code,"MODEL_VERSION_CHANGED")

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(FailureTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={"status":"PASS" if result.wasSuccessful() else "FAIL","tests_run":result.testsRun,
        "failures":len(result.failures),"errors":len(result.errors),"kind":"controlled failure injection; no live API success claimed"}
    (ROOT/"reports/failure-tests.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
