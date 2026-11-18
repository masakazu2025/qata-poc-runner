"""受けた命令を、読む版の契約（JSON Schema）に照らして判定する。

生成した型は `if`/`then` などを表せないので、判定はここで行い、
合格したものだけを型に読み込む（qata-server の S1 と同じ考え方）。
"""

import json
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

# 読む版の契約。リポジトリの直下の qata-contracts/ に、親のタグから写したもの（R6）。
# 隣に並べた ../qata/ は読まない
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "qata-contracts" / "schemas"


# 立ち上げたときに確かめる契約。実行の間に判定に使うのは命令だけ
USED_SCHEMAS = ["runner-command.schema.json"]


@cache
def _registry() -> Registry:
    resources = [
        (
            path.as_uri(),
            Resource(
                contents=json.loads(path.read_text(encoding="utf-8")),
                specification=DRAFT202012,
            ),
        )
        for path in sorted(SCHEMAS_DIR.glob("*.schema.json"))
    ]
    if not resources:
        raise FileNotFoundError(f"読む版の契約が見つからない：{SCHEMAS_DIR}")
    return Registry().with_resources(resources)


@cache
def _validator(file_name: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": (SCHEMAS_DIR / file_name).as_uri()},
        registry=_registry(),
        format_checker=FormatChecker(),
    )


def clear_cache() -> None:
    """読み込んだ契約を捨てる。テストで読む場所を差し替えるときに使う。"""
    _registry.cache_clear()
    _validator.cache_clear()


def _refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        found = [node["$ref"]] if isinstance(node.get("$ref"), str) else []
        return found + [r for v in node.values() for r in _refs(v)]
    if isinstance(node, list):
        return [r for v in node for r in _refs(v)]
    return []


def ensure_ready() -> None:
    """命令の判定に使う契約がそろっていることを確かめる。そろっていなければ例外。

    立ち上げたときに呼び、最初の命令が来てから気づくことがないようにする。
    $ref の解決は判定のときまで遅れるので、使う契約から $ref をたどり、
    指す先（ほかのファイルも）がすべて引けることを確かめる。
    """
    resolver = _registry().resolver()
    pending = [(SCHEMAS_DIR / name).as_uri() for name in USED_SCHEMAS]
    seen: set[str] = set()
    while pending:
        uri = pending.pop()
        if uri in seen:
            continue
        seen.add(uri)
        try:
            resolved = resolver.lookup(uri)
        except Unresolvable as e:
            raise FileNotFoundError(f"読む版の契約で、指す先が引けない：{uri}") from e
        base = uri.partition("#")[0]
        pending += [urljoin(base, ref) for ref in _refs(resolved.contents)]


def problems(file_name: str, data: Any) -> list[str]:
    """契約に合わない場所と、その説明の一覧。合えば空。"""
    found = []
    for error in _validator(file_name).iter_errors(data):
        where = "".join(f"/{p}" for p in error.absolute_path) or "/"
        found.append(f"{where}：{error.message}")
    return sorted(set(found))
