"""operator.feature の手順。pywinauto・起動・スクショを差し替えて、画面なしで動かす。"""

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pytest_bdd import given, parsers, scenarios, then, when
from pywinauto.findwindows import ElementAmbiguousError

from qata_runner import windows
from qata_runner.rest import create_app
from qata_runner.windows import WindowsOperator

scenarios("operator.feature")

TITLE = "練習台"
DISPLAY = "Display"
BROKEN = "偽の pywinauto が壊れた"


def _ambiguous(count: int) -> ElementAmbiguousError:
    # pywinauto と同じく、見つかった要素を elements に持たせる
    error = ElementAmbiguousError(f"There are {count} elements that match")
    error.elements = [object()] * count  # type: ignore[attr-defined]
    return error


class FakeRectangle:
    left, top, right, bottom = 0, 0, 400, 600

    def width(self) -> int:
        return self.right - self.left

    def height(self) -> int:
        return self.bottom - self.top


class FakeWrapper:
    handle = 1

    def __init__(self, text: str = "", focus_error: Exception | None = None) -> None:
        self.text = text
        self.focus_error = focus_error

    def rectangle(self) -> FakeRectangle:
        return FakeRectangle()

    def set_focus(self) -> None:
        if self.focus_error is not None:
            raise self.focus_error

    def window_text(self) -> str:
        return self.text


class FakeSpecification:
    """pywinauto の WindowSpecification の代わり。wait で例外を投げさせられる。"""

    def __init__(self, wrapper: FakeWrapper, wait_error: Exception | None = None):
        self.wrapper = wrapper
        self.wait_error = wait_error
        self.children: dict[str, FakeSpecification] = {}

    def wait(self, wait_for: str, timeout: float | None = None) -> None:
        if self.wait_error is not None:
            raise self.wait_error

    def wrapper_object(self) -> FakeWrapper:
        return self.wrapper

    def child_window(self, auto_id: str) -> "FakeSpecification":
        return self.children[auto_id]


class FakeDesktop:
    """Desktop の代わり。起動・キー・タップ・スクショで、例外を投げさせられる。"""

    def __init__(self) -> None:
        self.window_spec = FakeSpecification(FakeWrapper())
        self.window_spec.children[DISPLAY] = FakeSpecification(FakeWrapper("3"))
        self.launch_error: Exception | None = None
        self.failing_key: str | None = None  # この send_keys の書き方で例外を投げる
        self.tap_error: Exception | None = None
        self.failing_screenshot: int | None = None  # 何枚目のスクショで例外を投げるか
        self.screenshots = 0

    def popen(self, command: str) -> None:
        if self.launch_error is not None:
            raise self.launch_error

    def send_keys(self, keys: str, **options: object) -> None:
        if keys == self.failing_key:
            raise RuntimeError(BROKEN)

    def click(self, **options: object) -> None:
        if self.tap_error is not None:
            raise self.tap_error

    def grab(self, **options: object) -> Image.Image:
        self.screenshots += 1
        if self.screenshots == self.failing_screenshot:
            raise OSError(BROKEN)
        return Image.new("RGB", (4, 4), "white")

    def __call__(self, backend: str) -> "FakeDesktop":
        return self

    def window(self, **criteria: object) -> FakeSpecification:
        return self.window_spec

    def windows(self, **criteria: object) -> list:
        return []  # 閉じる前のウィンドウはない


@pytest.fixture
def desktop(monkeypatch: pytest.MonkeyPatch) -> FakeDesktop:
    fake = FakeDesktop()
    monkeypatch.setattr(windows, "Desktop", fake)
    monkeypatch.setattr(windows.subprocess, "Popen", fake.popen)
    monkeypatch.setattr(windows.keyboard, "send_keys", fake.send_keys)
    monkeypatch.setattr(windows.mouse, "click", fake.click)
    monkeypatch.setattr(windows, "_visible_bounds", lambda handle: (0, 0, 4, 4))
    monkeypatch.setattr(windows.ImageGrab, "grab", fake.grab)
    return fake


@given("pywinauto を差し替えた本物の操作で立ち上げた runner", target_fixture="client")
def faked_runner(desktop: FakeDesktop) -> TestClient:
    return TestClient(create_app(WindowsOperator(settle=0)))


@given("同じタイトルのウィンドウが二つある")
def two_windows(desktop: FakeDesktop) -> None:
    desktop.window_spec.wait_error = _ambiguous(2)


@given("表示の要素が二つある")
def two_elements(desktop: FakeDesktop) -> None:
    desktop.window_spec.children[DISPLAY].wait_error = _ambiguous(2)


@given("表示を読むと想定していない例外が出る")
def read_breaks(desktop: FakeDesktop) -> None:
    desktop.window_spec.children[DISPLAY].wait_error = RuntimeError(BROKEN)


@given("ウィンドウを前に出すと想定していない例外が出る")
def focus_breaks(desktop: FakeDesktop) -> None:
    desktop.window_spec.wrapper.focus_error = RuntimeError(BROKEN)


@given("アプリを起動すると OSError が出る")
def launch_breaks(desktop: FakeDesktop) -> None:
    # 仲間（FileNotFoundError など）ではなく、素の OSError を投げる。exe として読めない
    # ファイルを起動したときは素の OSError になるので、捕まえる範囲が狭まれば落ちる
    desktop.launch_error = OSError(BROKEN)


@given(parsers.parse('キー "{key}" を押すと例外が出る'))
def key_breaks(desktop: FakeDesktop, key: str) -> None:
    desktop.failing_key = key


@given("タップすると例外が出る")
def tap_breaks(desktop: FakeDesktop) -> None:
    desktop.tap_error = RuntimeError(BROKEN)


@given(parsers.parse("{count:d} 枚目のスクショを撮ると例外が出る"))
def screenshot_breaks(desktop: FakeDesktop, count: int) -> None:
    desktop.failing_screenshot = count


def _step(word: str) -> dict:
    if word == "表示を読む":
        return {
            "type": "read_text",
            "source": {"method": "uia", "automation_id": DISPLAY},
        }
    if word == "タップ":
        return {"type": "tap", "point": {"x": 10, "y": 20}}
    return {"type": "key", "key": word}


@when(parsers.parse('ステップを "{words}" にして送る'))
def send_steps(context: dict, client: TestClient, words: str) -> None:
    steps = [_step(word) for word in words.split(" ")]
    context["command"] = {
        "run_id": "run_test",
        "app": {"launch": {"command": "practice.exe"}, "window": {"title": TITLE}},
        "screenshot": {"scope": "window"},
        "steps": steps,
    }
    context["response"] = client.post("/runs", json=context["command"])


@then("error の message に例外の中身が入っている")
def message_has_exception(context: dict) -> None:
    result = context["response"].json()
    assert BROKEN in result["error"]["message"]
    if result["steps"]:  # 止めたステップにも、同じ理由が付いている
        assert result["steps"][-1]["error"] == result["error"]
