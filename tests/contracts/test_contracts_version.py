"""contracts_version.feature の手順。"""

import io
import shutil
import tarfile
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sync_contracts import COPY_DIR, differences, newer_version

scenarios("contracts_version.feature")


@given(parsers.parse('読む版 "{version}"'), target_fixture="current")
def given_current(version: str) -> str:
    return version


@given(parsers.re('親のタグ "(?P<tags>.*)"'), target_fixture="ls_remote")
def given_tags(tags: str) -> str:
    # git ls-remote --tags の出力の形（ハッシュ、タブ、refs/tags/<タグ>）
    return "".join(
        f"0123abcd\trefs/tags/{tag}\n" for tag in tags.split(",") if tag.strip()
    )


@then(parsers.parse('知らせる新しい版は "{expected}"'))
def then_newer(current: str, ls_remote: str, expected: str) -> None:
    assert newer_version(current, ls_remote) == (
        None if expected == "なし" else expected
    )


@given("写しと同じ中身の、親のタグの tarball", target_fixture="tarball")
def given_tarball() -> bytes:
    # GitHub のタグの tarball と同じく、一段目のフォルダの下に contracts/ がある
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(COPY_DIR, arcname="qata-contracts-v0.0.0/contracts")
    return buffer.getvalue()


@pytest.fixture
def copy_dir(tmp_path: Path) -> Path:
    """写しを手で直す手順のために、一時の場所に複製した写し。"""
    copy = tmp_path / "qata-contracts"
    shutil.copytree(COPY_DIR, copy)
    return copy


@when(parsers.parse('写しの "{name}" を書き換える'))
def when_edit(copy_dir: Path, name: str) -> None:
    path = copy_dir / name
    path.write_bytes(path.read_bytes() + b"x")


@then("写しとの違いはない")
def then_no_difference(tarball: bytes, copy_dir: Path) -> None:
    assert differences(tarball, copy_dir) == []


@then(parsers.parse('写しとの違いに "{name}" がある'))
def then_difference(tarball: bytes, copy_dir: Path, name: str) -> None:
    assert name in differences(tarball, copy_dir)
