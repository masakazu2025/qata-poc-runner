"""runs.feature の手順。"""

import base64
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pytest_bdd import given, parsers, scenarios, then, when
from support import load_example, walk_to_parent

from qata_runner.contracts.runner_command_schema import RunnerCommand
from qata_runner.contracts.runner_result_schema import RunnerResult
from qata_runner.fake import FakeOperator
from qata_runner.rest import create_app

scenarios("runs.feature")

REMOVE = "（消す）"


@given("偽の操作で立ち上げた runner", target_fixture="client")
def fake_runner() -> TestClient:
    return TestClient(create_app(FakeOperator()))


@given(
    parsers.parse('read_text が "{text}" を返す偽の操作で立ち上げた runner'),
    target_fixture="client",
)
def fake_runner_with_text(text: str) -> TestClient:
    return TestClient(create_app(FakeOperator(text)))


class HeldOperator:
    """始まったところで、進めてよいと言われるまで止まる偽の操作。同時に動いた数を数える。"""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.proceed = threading.Event()
        self.running = 0
        self.max_running = 0
        self._count = threading.Lock()
        self._fake = FakeOperator()

    def run(self, command: RunnerCommand) -> RunnerResult:
        with self._count:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        try:
            self.started.set()
            self.proceed.wait(timeout=10)
            return self._fake.run(command)
        finally:
            with self._count:
                self.running -= 1


class FailOnceOperator:
    """1 回目だけ、想定していない例外で止まる偽の操作。"""

    def __init__(self) -> None:
        self.calls = 0
        self._fake = FakeOperator()

    def run(self, command: RunnerCommand) -> RunnerResult:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("偽の操作が止まった")
        return self._fake.run(command)


@given("止めておける偽の操作で立ち上げた runner", target_fixture="client")
def held_runner(context: dict) -> TestClient:
    context["operator"] = HeldOperator()
    return TestClient(create_app(context["operator"]))


@given("1 回目だけ例外を出す偽の操作で立ち上げた runner", target_fixture="client")
def fail_once_runner() -> TestClient:
    return TestClient(create_app(FailOnceOperator()))


@when(
    parsers.parse(
        '契約の例 "{file_name}" の命令を送り、操作が始まったところで止めておく'
    )
)
def send_and_hold(context: dict, client: TestClient, file_name: str) -> None:
    context["command"] = load_example(file_name)
    first: dict = {}

    def send() -> None:
        first["response"] = client.post("/runs", json=context["command"])

    thread = threading.Thread(target=send)
    thread.start()
    context["first"] = first
    context["thread"] = thread
    assert context["operator"].started.wait(timeout=10), "操作が始まらない"


@when("その間にもう一つ命令を送る")
def send_while_running(context: dict, client: TestClient) -> None:
    context["response"] = client.post("/runs", json=context["command"])


@when("もう一度同じ命令を送る")
def send_again(context: dict, client: TestClient) -> None:
    context["response"] = client.post("/runs", json=context["command"])


@then("止めておいた操作を進めると、1 つめの応答は 200")
def release_first(context: dict) -> None:
    context["operator"].proceed.set()
    context["thread"].join(timeout=10)
    response = context["first"]["response"]
    assert response.status_code == 200, response.text


@then("同時に動いた操作は 1 つだけ")
def only_one_ran(context: dict) -> None:
    assert context["operator"].max_running == 1


@then("そのあとに送った命令は 200 で受ける")
def accepted_after(context: dict, client: TestClient) -> None:
    response = client.post("/runs", json=context["command"])
    assert response.status_code == 200, response.text


@given(parsers.parse('契約の例 "{file_name}" の命令'))
def given_command(context: dict, file_name: str) -> None:
    context["command"] = load_example(file_name)


@when(parsers.parse('命令の "{pointer}" を {value} にする'))
def change_command(context: dict, pointer: str, value: str) -> None:
    parent, key = walk_to_parent(context["command"], pointer)
    if value == REMOVE:
        del parent[key]
    else:
        parent[key] = json.loads(value)


@when("その命令を送る")
def send_command(context: dict, client: TestClient) -> None:
    context["response"] = client.post("/runs", json=context["command"])


@when(parsers.parse('契約の例 "{file_name}" の命令を送る'))
def send_example(context: dict, client: TestClient, file_name: str) -> None:
    context["command"] = load_example(file_name)
    context["response"] = client.post("/runs", json=context["command"])


@when(parsers.parse('本文 "{body}" を送る'))
def send_body(context: dict, client: TestClient, body: str) -> None:
    context["response"] = client.post(
        "/runs", content=body, headers={"content-type": "application/json"}
    )


@then("結果の run_id は命令と同じ")
def run_id_matches(context: dict) -> None:
    assert context["response"].json()["run_id"] == context["command"]["run_id"]


@then("開始の時刻は終わりの時刻より後でない")
def times_in_order(context: dict) -> None:
    result = context["response"].json()
    started = datetime.fromisoformat(result["started_at"])
    finished = datetime.fromisoformat(result["finished_at"])
    assert started <= finished


@then(parsers.parse("どのステップのスクショも {width:d} x {height:d} の PNG"))
def screenshots_are_png(context: dict, width: int, height: int) -> None:
    for step in context["response"].json()["steps"]:
        data = base64.b64decode(step["screenshot"]["data_base64"], validate=True)
        image = Image.open(io.BytesIO(data))
        assert image.format == "PNG"
        assert image.size == (width, height)


@then(parsers.parse('read_text のステップだけが文字 "{text}" を持つ'))
def only_read_text_has_text(context: dict, text: str) -> None:
    steps = context["response"].json()["steps"]
    commands = context["command"]["steps"]
    for command_step, result_step in zip(commands, steps, strict=True):
        if command_step["type"] == "read_text":
            assert result_step["text"] == text
        else:
            assert "text" not in result_step


@pytest.fixture
def runner_process():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    executable = Path(sys.executable).parent / "qata-runner"
    process = subprocess.Popen(
        [str(executable)],
        env={**os.environ, "QATA_RUNNER_PORT": str(port)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield f"http://127.0.0.1:{port}"
    process.terminate()
    process.wait(timeout=10)


@given("qata-runner をプロセスとして立ち上げた", target_fixture="base_url")
def started_process(runner_process: str) -> str:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{runner_process}/docs", timeout=1)
            return runner_process
        except httpx.TransportError:
            time.sleep(0.2)
    raise AssertionError("qata-runner が立ち上がらない")


@when(parsers.parse('契約の例 "{file_name}" の命令をそのプロセスに送る'))
def send_to_process(context: dict, base_url: str, file_name: str) -> None:
    context["command"] = load_example(file_name)
    context["response"] = httpx.post(
        f"{base_url}/runs", json=context["command"], timeout=30
    )
