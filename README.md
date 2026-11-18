# qata-runner

[qata](https://github.com/masakazu2025/qata) の runner です。server から命令を受けて Windows 上で操作（キー・タップ・文字の読み取り）を実行し、ステップごとの結果とスクショを返します。部品の辞書もテストケースも知らず、判定もしません。

操作は二つあり、立ち上げるときに選びます。

| 操作 | `QATA_RUNNER_OPERATOR` | 中身 |
| --- | --- | --- |
| 偽物 | `fake`（既定） | アプリは動かさず、どのステップも成功として、決まった文字と、操作を書いた白い PNG を返す。端から端までのテストのため |
| 本物 | `windows` | pywinauto でアプリを起動し直し、キー・タップ・UI Automation での読み取りを実行して、スクショを撮る |

契約と全体の要件は、親のリポジトリ `qata` が正です。契約は、その版を `qata-contracts/` に写して持つので（下の「読む契約の版」）、このリポジトリだけで動きます。

```
作業フォルダ/
├── qata/          ← 親
└── qata-runner/   ← ここ
```

やることは、このリポジトリの GitHub の issue で管理しています。部品をまたぐものと全体の判断は、親の [qata の issue](https://github.com/masakazu2025/qata/issues) に置きます。

## 関門

pull request と main への push のたびに、GitHub Actions（`.github/workflows/ci.yml`）が下を回します。通らないと main にマージできません。

```
uv sync
uv run python scripts/sync_contracts.py --check  # 契約の写しを手で直していないか
uv run pytest          # 生成した型と契約・POST /runs・本物の操作（電卓）・依存の向き（import-linter）
uv run ruff check
uv run ruff format --check
uv run pyright         # 型（契約から生成した型は報告から外す）
```

本物の操作のテスト（`tests/windows/windows.feature`）は、Windows の電卓を起動し、キーボードとマウスを数秒使います。走っている間は触らないでください。デスクトップのない所では、環境変数 `QATA_RUNNER_NO_DESKTOP=1` で飛ばします（CI はこれ）。

CI は、読む契約の版が親の最新より古いと警告を出します（関門は落としません。`sync_contracts.py --warn-if-old`）。

## 読む契約の版

runner は、親の契約の版を一つ選んで写して持ち、その版だけを読みます。親の `main` が進んでも、ここで版を上げるまで前の版を読み続けます。隣に並べた親（`../qata/`）の中身は読みません。

- 写し：`qata-contracts/`。親のタグ `contracts-v<版>` の `contracts/` を丸ごと写したもの。手で直しません。
- 読む版：`qata-contracts/VERSION`。変更の記録は `qata-contracts/CHANGELOG.md`。
- 型の生成・テスト・実行（命令の判定）は、どれも `qata-contracts/` を読みます。

版を上げるときは、写し直してから型を生成し直します。

```
uv run python scripts/sync_contracts.py 1.1.0
uv run python scripts/generate_contracts.py
```

## 契約から型を生成する

読む版の契約のうち、runner が使うもの（runner への命令・runner からの結果・共通の部品）から pydantic の型を生成し、`src/qata_runner/contracts/` に置いてコミットします。手で直しません。契約が変わったら生成し直します。生成物が契約と合っているかは `pytest` で確かめます。

```
uv run python scripts/generate_contracts.py
```

## 立ち上げる

```
uv run qata-runner
```

`http://127.0.0.1:8001` で待ち受けます（qata-server が既定で見に行く場所）。変えるときは環境変数 `QATA_RUNNER_HOST`・`QATA_RUNNER_PORT` を使います。偽の操作で read_text が返す文字は `QATA_RUNNER_FAKE_TEXT`（既定は「表示は 3 です」）で変えられます。本物の電卓を動かすときは、`QATA_RUNNER_OPERATOR=windows` を付けて立ち上げます。

- `POST /runs`：本文は runner への命令（`runner-command.schema.json`）。実行が終わるまで待って、runner からの結果（`runner-result.schema.json`）を返す。
- 命令が契約に合わなければ、422 で `{"code": "invalid_command", "message": ...}` を返す。
- 実行は一度に一つだけ。実行中に次の命令が来たら、待たずに 409 で `{"code": "runner_busy", "message": ...}` を返す。
