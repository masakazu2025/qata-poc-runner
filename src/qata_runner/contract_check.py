"""受けた命令を、読む版の契約（JSON Schema）に照らして判定する。

生成した型は `if`/`then` などを表せないので、判定はここで行い、
合格したものだけを型に読み込む（qata-server の S1 と同じ考え方）。
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

# 読む版の契約。リポジトリの直下の qata-contracts/ に、親のタグから写したもの（R6）。
# 隣に並べた ../qata/ は読まない
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "qata-contracts" / "schemas"


@cache
def _validator(file_name: str) -> Draft202012Validator:
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
    return Draft202012Validator(
        {"$ref": (SCHEMAS_DIR / file_name).as_uri()},
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def ensure_ready() -> None:
    """命令の判定に使う契約がそろっていることを確かめる。そろっていなければ例外。

    立ち上げたときに呼び、最初の命令が来てから気づくことがないようにする。
    """
    _validator("runner-command.schema.json")


def problems(file_name: str, data: Any) -> list[str]:
    """契約に合わない場所と、その説明の一覧。合えば空。"""
    found = []
    for error in _validator(file_name).iter_errors(data):
        where = "".join(f"/{p}" for p in error.absolute_path) or "/"
        found.append(f"{where}：{error.message}")
    return sorted(set(found))
