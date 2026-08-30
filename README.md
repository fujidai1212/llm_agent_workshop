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
| `LLMAgent_Workshop.ipynb` | **生成物。手で編集しない。** Colab 配布用ノートブック |
| `build_colab.py` | 上記 `.ipynb` を `agent.py` / `tools.py` / `workspace/` から組み立てる |
| `プロジェクトの説明.md` | 教材の設計方針・意思決定の記録（講師用） |

## ノートブックの更新手順

`.ipynb` は生成物です。内容を変えるときは**必ずソース側を直してから**再生成してください。

```bash
.venv/bin/python build_colab.py   # LLMAgent_Workshop.ipynb を上書き
git add -A && git commit -m "..." && git push
```

- コードを直したい → `agent.py` / `tools.py` / `workspace/*.json`
- 説明文・課題文を直したい → `build_colab.py` の「ここから教材の台本」以降

## ライセンス・注意

`workspace/` のデータはすべて架空です。`reset_password` は JSON を書き換えるだけで、実害はありません。
`.env`（API キー）は `.gitignore` 済み。**絶対にコミットしないこと。**
