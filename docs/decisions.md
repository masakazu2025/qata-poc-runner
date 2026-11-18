# 決めたこと

この部品の中だけで閉じることを残します。全体に関わることは親の `../qata/docs/decisions.md` に置きます。新しいものを上に足します。

---

## R6. 読む契約の版を写して持ち、立ち上げたときにそろっていることを確かめる

- 決めた人：AI　レビュー：未（人のレビューは要らない。形は親の D54 で決めたもの）
- 形は親の [repos-and-contracts.md の「子の持ち方」](https://github.com/masakazu2025/qata/blob/main/.claude/rules/qata/repos-and-contracts.md#子の持ち方)のとおり。写す道具は `scripts/sync_contracts.py` の一つにまとめ、写す・`--check`（写しを手で直していないか）・`--warn-if-old`（親に新しい版があるか）を持たせた。どれも版とタグの扱いを共有するため。
- **`--check` は、tarball の中身と写しを直に比べる。** 一時の場所に写してから比べるのと同じ結果で、手順が少ない。比べ方そのもの（違いを見つけること）は、写しから作った tarball でテストする。ネットにつながずに確かめるため。
- **runner は動いている間も契約を読むので、`create_app` で、命令の判定に使う契約がそろっていることを確かめる（`contract_check.ensure_ready`）。** 命令の契約から `$ref` をたどり、指す先（`common` も）がすべて引けることまで見る。`$ref` の解決は判定のときまで遅れるので、読み込むだけでは、ファイルが一つ欠けても最初の命令が 500 になるまで気づけないため（reviewer の指摘）。
- **版を比べるのは、`git ls-remote` の出力を引数に取る `newer_version`。** タグの `^{}`（注釈付きのタグの指す先）と、形の違うタグは読み飛ばす。

---

## R5. 想定していない例外でも、それまでのステップを付けて aborted を返す

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- **二段で捕まえる。** `WindowsOperator.run` で、起動とステップのどこで出た例外も捕まえ、それまでのステップを付けて aborted を返す（ステップの途中なら、そのステップを error にする）。それでも漏れたもの（偽物を含む操作そのものが投げたもの）は、`rest.py` で捕まえて、ステップを空にした aborted を 200 で返す。どこまで進んだかは REST では分からないため、空にする。
- **二つあるときは、名前の付いたコードにする。** 同じタイトルのウィンドウが二つ：`window_ambiguous`（ステップは空）。同じ AutomationId の要素が二つ：`element_ambiguous`（そのステップを error）。業務アプリではよく起き、人がすることが分かる（閉じる・辞書を直す）ので、`internal_error` とは分けた。pywinauto は待つ（`wait`）の中から `ElementAmbiguousError` を、待たずにそのまま投げる（コードを読んで確かめた）。
- **ほかは `internal_error`。** message に例外の型と中身を入れる。名前は server の側（qata-server#17）とそろえる。コードは契約では自由な文字列なので、契約は変えていない。
- **テスト。** `tests/windows/operator.feature` で、pywinauto（`Desktop`）・起動・キー・スクショを差し替え、画面なしで REST の入口から動かす。CI でも回る。差し替えは qata-runner#13 でも使う。止め方の確かめに共通の手順は `tests/conftest.py` に移した。

---

## R4. 型の検査は pyright の standard で、契約から生成した型は報告から外す

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 関門に `uv run pyright` を足した。設定は pyproject.toml の `[tool.pyright]`。対象は src・tests・scripts。server（S9）とそろえた。
- モードは standard。strict は、型の付いていないライブラリ（pywinauto など）の扱いで誤りが多く出て、中身より抑えの記述が増えるため。困ったら上げる。
- 契約から生成した型（`src/qata_runner/contracts`）は、ruff と同じく報告から外す。手で直さない生成物のため。外しても、import されれば型は読まれるので、使い方の誤りは捕まる（今回の日時の誤りもこれで見つかった）。
- `extraPaths` は pytest の `pythonpath` と同じ（scripts・tests）。テストが直下のモジュールを import するため。
- 結果の日時は、契約の型 `Timestamp` で包んで渡す。生の `datetime` でも pydantic が変換するので動きは同じだが、型が合わないため。

## R3. 本物の操作（pywinauto）

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 本物の操作は `windows.py` の `WindowsOperator`。偽物と同じ `run(command) -> result` を持ち、`main.py` で `QATA_RUNNER_OPERATOR`（`fake`・`windows`）から選ぶ。既定は偽物のまま。web の端から端までのテストが既定で runner を立ち上げているので、切り替えは親の段取りの 1c でする。
- pywinauto は Windows でしか入らないので、依存に `sys_platform == 'win32'` を付け、`main.py` では `windows` を選んだときだけ読み込む。
- 実行の流れ：同じタイトルのウィンドウを閉じる → `launch.command` を起動 → タイトルの完全一致で UI Automation のウィンドウを待つ（既定 15 秒）→ 大きさがあれば `MoveWindow` でそろえる → 前に出す → ステップを順に。ウィンドウはタイトルで探す（電卓は起動したプロセスと別のプロセスで窓を持つので、プロセスでは探せない）。
- 大きさをそろえたあとに測り、命令と違えば `window_size_mismatch` で止める。座標がその大きさを前提にしているので、ずれたまま押すより止めるほうがよい。電卓は 336 x 509 より小さくできず、契約の例の 320 x 500 はここで止まる。
- 座標とスクショは物理ピクセルにそろえる（プロセスを Per Monitor の DPI 対応にする）。タップの座標の原点は、契約どおり外枠（`GetWindowRect`）の左上。
- スクショ（`window`）は、外枠ではなく DWM の見えている範囲で撮る。外枠には見えない縁（数ピクセル）があり、後ろの別のウィンドウが写り込むため。そのぶん、スクショの左上はタップの原点と数ピクセルずれる。
- 操作のあと 0.3 秒待ってから撮る（画面の書き換えを待つ）。
- キーは pywinauto の `send_keys` の書き方に変える。名前付きのキーは `{ENTER}` などに、`+ ^ % ~ ( ) { } [ ]` は `{}` で囲む。
- つまずいたときの `error.code`：`launch_failed`・`window_not_found`・`window_size_mismatch`（ステップは空）、`key_failed`・`tap_failed`・`element_not_found`・`screenshot_failed`（そのステップを error にして止める）。二つあるとき・想定していない例外のときは R5。
- 実行のあと、ウィンドウは閉じずに残す。次の実行の始めに閉じる。人が最後の状態を見られるようにするため。
- 関門：`tests/windows/windows.feature` で、REST の入口から本物の電卓を動かす（キー・タップ・すべての画面・三つの止まり方）。電卓は前に使ったモード（標準・関数電卓）で開くので、テストのタップの座標は UI Automation でボタンを探して決める。CI にはデスクトップがないので `QATA_RUNNER_NO_DESKTOP` で飛ばし、手元で回す。キーの書き換えは CI でも回す。
- テストで共通の手順（応答・契約・completed）は `tests/conftest.py` に移した。

## R2. 偽の操作と入口

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 入口は `rest.py` の `create_app(operator)`。`operator` は `run(command) -> result` を持つものなら何でもよい（`Operator` の Protocol）。組み立ては `main.py` で、いまは偽の操作（`fake.py` の `FakeOperator`）を渡す。本物に置き換えるときは、`main.py` で渡すものを変える。
- 依存の向きは import-linter の layers で、`main` → `rest`・`fake`（互いに知らない）→ `contract_check`・契約の型。入口が偽物を知らないことも関門にした。
- 命令は FastAPI で検証せず、親の `runner-command.schema.json` で判定してから型に読み込む（qata-server の S1 と同じ）。合わなければ 422 で、契約の共通の部品 `error` の形（`code`：`invalid_command`）を返す。契約は runner の HTTP のエラーを決めていないが、server はどの HTTP のエラーも「runner に届かない」として扱う（qata-server の S6）ので、形を合わせておけば足りる。
- 本物の操作は終わるまで待つので、入口は操作をスレッドで動かす。
- 偽の操作は、どのステップも `ok` にし、read_text では決まった文字（既定は「表示は 3 です」、`QATA_RUNNER_FAKE_TEXT` で変える）を返す。電卓のデモの 1 + 2 = 3 が通るようにするため。失敗（aborted）を返す偽物は作らない。失敗の扱いは server が自分の偽の runner で確かめている。
- スクショは Pillow で作る白い PNG に、ステップの番号と操作を書く（既定のフォントは日本語を出せないので ASCII）。web でスクショが並ぶのを見られるようにするため。大きさは、`window` で命令に大きさがあればその大きさ、それ以外（`all_screens`、大きさのないアプリ）は 1920 x 1080。
- 時刻は runner の手元の時刻（タイムゾーン付き）。
- 待ち受けは `127.0.0.1:8001`（qata-server の既定の `QATA_RUNNER_URL` に合わせた）。設定の環境変数は `QATA_RUNNER_` で始め、server と同じマシンで立ち上げても混ざらないようにした。
- 関門の feature には、`qata-runner` をプロセスとして立ち上げて `POST /runs` を受けることも入れた。端から端までつなぐときの立ち上げ方を確かめておくため。

## R1. 型の生成と契約の読み方

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- qata-server の S1・S2 と同じく、datamodel-code-generator で生成し、`scripts/generate_contracts.py` に手順を置く。生成するのは runner が使う契約（`runner-command`・`runner-result` と、それが指す `common`）だけ。使わない型を持たないため。
- 契約そのものの検査（例が形式に通る・間違った例をはじく・$ref が解決できる）は、親の D22 のとおり qata-server が持つ。runner は、生成した型が契約の例を読めることと、生成し直しても同じことだけを確かめる。
- 親の契約は、作業フォルダで隣に並べた `../qata/` から読む（実行のときの判定も）。相対のパスで親を読むのは、次の周回で直す（親の ideas.md）。→ R6 で、読む版の写し `qata-contracts/` を読む形に変えた。
- 観点は pytest-bdd の日本語の Gherkin で書く。
- 作った最初から `.gitattributes` で改行を LF にそろえる（親の D24）。
