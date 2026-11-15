# language: ja
機能: 本物の操作は、想定していない例外でも契約の形で結果を返す
  pywinauto を差し替えて、画面なしで動かす（CI でも回る）。
  業務アプリでは、同じタイトルのウィンドウが二つある・同じ AutomationId の要素が二つある（一覧の行など）ことがよくある。
  pywinauto はそのとき、待つ（wait）の中から ElementAmbiguousError を投げる。
  どんな例外でも、それまでのステップを付けて aborted を返す。

  背景:
    前提 pywinauto を差し替えた本物の操作で立ち上げた runner

  シナリオ: 同じタイトルのウィンドウが二つあると、ステップを始めずに止める
    前提 同じタイトルのウィンドウが二つある
    もし ステップを "1 表示を読む" にして送る
    ならば 応答は 200
    かつ 結果は契約 "runner-result.schema.json" に通る
    かつ 結果は aborted で、ステップは空、error の code は "window_ambiguous"

  シナリオ: 同じ AutomationId の要素が二つあると、そのステップで止める
    前提 表示の要素が二つある
    もし ステップを "1 表示を読む 2" にして送る
    ならば 応答は 200
    かつ 結果は契約 "runner-result.schema.json" に通る
    かつ 結果は aborted で、error の code は "element_ambiguous"
    かつ ステップは 2 つで、0 は ok、1 は error

  シナリオ: ステップの途中で想定していない例外が出ても、それまでのステップを付けて止める
    前提 表示を読むと想定していない例外が出る
    もし ステップを "1 表示を読む 2" にして送る
    ならば 応答は 200
    かつ 結果は契約 "runner-result.schema.json" に通る
    かつ 結果は aborted で、error の code は "internal_error"
    かつ ステップは 2 つで、0 は ok、1 は error
    かつ error の message に例外の中身が入っている

  シナリオ: 起動の途中で想定していない例外が出ても、ステップを始めずに止める
    前提 ウィンドウを前に出すと想定していない例外が出る
    もし ステップを "1" にして送る
    ならば 応答は 200
    かつ 結果は契約 "runner-result.schema.json" に通る
    かつ 結果は aborted で、ステップは空、error の code は "internal_error"
