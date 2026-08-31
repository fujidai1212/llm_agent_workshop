# LLMエージェントを自分で作る（3時間ワークショップ）

フレームワーク（LangChain / LangGraph / Agents SDK）を**一切使わず**、
LLMエージェントの正体が `for` ループであることを手を動かして確かめる教材です。
題材は社内ヘルプデスクのアシスタント。最後にプロンプトインジェクションで実際に乗っ取られます。

## Colab で開く（参加者はこちら）

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fujidai1212/llm_agent_workshop/blob/main/LLMAgent_Workshop.ipynb)

インストール作業は不要です。開いたら**最初に「ドライブにコピーを保存」**を押してください。
押さないと編集内容が保存されません。API キーは当日配布されたものを、ノートブック内の入力欄に貼り付けます。

## ローカルで動かす（講師・開発用）

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # OPENAI_API_KEY を書く
.venv/bin/python agent.py "チケット #1042 に対応してください。"
```

## ファイル構成

| ファイル | 内容 |
|---|---|
| `agent.py` | エージェント本体。会話履歴を再送し、tool_calls を実行し、上限で止めるループ |
| `tools.py` | エージェントに持たせる7つのツール（関数 / スキーマ / レジストリの3点セット） |
| `workspace/` | 社内マニュアル24件・チケット16件・社員名簿18名 |
| `LLMAgent_Workshop.ipynb` | **編集する正のファイル。** Colab 配布用ノートブック（課題文もここにある） |
| `プロジェクトの説明.md` | 教材の設計方針・意思決定の記録（講師用） |

## ノートブックの更新手順

`.ipynb` を直接編集します（Cursor / VS Code / Colab のどれでもよい）。生成スクリプトはありません。

- **説明文・課題文を直す / 課題を足す** → `.ipynb` のセルをそのまま編集・追加する
- **コードを直す** → `agent.py` / `tools.py` / `workspace/*.json` を直し、
  **ノートブックの該当セルにも同じ内容を反映する**

ノートブック側でコードが入っているのは次の3セルだけです（セル番号は0始まり）。

| セル | 中身 | 対応するファイル |
|---|---|---|
| 6 | `#@title 【実行するだけ】データを配置する` | `workspace/kb.json` / `tickets.json` / `employees.json` |
| 10 | `%%writefile tools.py` | `tools.py` 全文 |
| 12 | `%%writefile agent.py` | `agent.py` 全文 |

この3セルとローカルの `.py` がずれると、**講師の手元と参加者の Colab で違うコードが動きます。**
`.py` を直したときは必ずセルにも反映してください。

```bash
git add -A && git commit -m "..." && git push
```

## ライセンス・注意

`workspace/` のデータはすべて架空です。`reset_password` は JSON を書き換えるだけで、実害はありません。
`.env`（API キー）は `.gitignore` 済み。**絶対にコミットしないこと。**
