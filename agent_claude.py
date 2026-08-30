"""agent.py の Anthropic (Claude) 版。開発・検証用。

【なぜこのファイルがあるか】
当日の教材は OpenAI API 前提（agent.py）。だが研究室の共有キーが届くまで
何も動かせないので、手元の CLAUDE_API_KEY で先に検証するためのもの。

【agent.py と見比べてほしいこと】
ループの構造は 1 ミリも変わらない。

    while 上限まで:
        履歴を全部送る → ツールを呼びたがっているか？
        → いなければ終了 / いれば自分のコードで実行して履歴に積む

違うのは「APIの方言」だけ。具体的には次の5点で、それ以外は同じ:

    | 論点             | OpenAI                       | Anthropic                        |
    |------------------|------------------------------|----------------------------------|
    | ツール定義の形   | {"type":"function",          | {"name", "description",          |
    |                  |  "function":{...}}           |  "input_schema"}                 |
    | system の渡し方  | messages の1件目             | 独立した system 引数             |
    | 終了判定         | message.tool_calls が空か    | stop_reason == "end_turn"        |
    | 引数の型         | JSON文字列（自分でparse）    | dict（parse済み）                |
    | 結果の返し方     | role="tool" を1件ずつ        | role="user" に tool_result をまとめて |

「エージェント＝whileループ」であってフレームワークでもSDKでもない、
というのは、この2ファイルを並べると一番はっきりする。

実行:
    .venv/bin/python agent_claude.py
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

# ツールの「中身」は完全に使い回せる。
# list_files() も read_file() もただのPython関数であって、
# どのLLMベンダーを使うかとは何の関係もない。
# 作り直しが必要なのは下の TOOLS（モデルに渡すスキーマ）だけ。
from tools import call_tool

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
MAX_STEPS = 10

SYSTEM_PROMPT = """あなたはファイル操作エージェントです。
作業ディレクトリの中でツールを使って仕事を進めてください。

- どんなファイルがあるか分からないときは、まず list_files を呼ぶこと
- 推測で答えず、必ず read_file で中身を確認すること
- 仕事が終わったら、何をしたかを日本語で簡潔に報告すること
"""

DEFAULT_TASK = (
    "作業ディレクトリの売上データを調べて、"
    "売上が最も多かった月とその金額を answer.txt に書き込んでください。"
)

# --- ツール定義（Anthropic 方言）----------------------------------------
# tools.py の TOOLS と中身は同一。入れ物の形だけが違う。
# OpenAI:    {"type": "function", "function": {"name":..., "parameters": {...}}}
# Anthropic: {"name": ..., "input_schema": {...}}       ← 一段フラット
TOOLS = [
    {
        "name": "list_files",
        "description": "作業ディレクトリにあるファイル名の一覧を取得する。どんなファイルがあるか分からないときは、まずこれを呼ぶ。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": "作業ディレクトリにあるファイルの中身を読む。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "読みたいファイル名。例: sales.csv",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "write_file",
        "description": "作業ディレクトリにファイルを書き込む。既に存在する場合は上書きする。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "書き込むファイル名。例: answer.txt",
                },
                "content": {
                    "type": "string",
                    "description": "ファイルに書き込む内容。",
                },
            },
            "required": ["filename", "content"],
        },
    },
]


def build_client() -> anthropic.Anthropic:
    """CLAUDE_API_KEY を読む。

    注意: Anthropic SDK が自動で見にいく環境変数は ANTHROPIC_API_KEY であって
    CLAUDE_API_KEY ではない。今回は CLAUDE_API_KEY という名前で持っているので、
    明示的に読んで渡す。どちらの名前でも動くようにしてある。
    """
    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "エラー: APIキーが設定されていません。\n"
            "  .env を開いて CLAUDE_API_KEY= の右側にキーを貼ってください。\n"
            "  （sk-ant- で始まる文字列。.env が無ければ cp .env.example .env）"
        )
    return anthropic.Anthropic(api_key=api_key)


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK

    client = build_client()

    # 「記憶」の正体は agent.py と同じ。ただのリスト。
    # ただし Anthropic では system はこのリストに入れず、独立した引数で渡す。
    messages = [{"role": "user", "content": task}]

    print(f"タスク: {task}")
    print(f"モデル: {MODEL}\n")

    for step in range(1, MAX_STEPS + 1):
        print("=" * 60)
        print(f"ステップ {step}  （会話履歴 {len(messages)} 件を送信）")
        print("=" * 60)

        # --- 1. 履歴を丸ごと送る ---------------------------------------
        # ここで tool_runner という便利なヘルパーもSDKにはあるが、
        # 使うとループが隠れてしまい教材の目的が消えるので、あえて手で回す。
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # --- 2. 終了判定 -----------------------------------------------
        # OpenAI版は「tool_calls が空か」で見たが、こちらは stop_reason を見る。
        # 判定しているのが if 文である点は変わらない。
        if response.stop_reason != "tool_use":
            print("\n【最終回答】")
            for block in response.content:
                if block.type == "text":
                    print(block.text)
            print(f"\n(stop_reason={response.stop_reason})")
            return

        # --- 3. モデルが返してきた tool_use を生のまま見る ---------------
        # ここが山場。モデルは関数を実行していない。この構造体を返しただけ。
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        print("\nモデルが返してきた tool_use（生データ）:")
        for block in tool_uses:
            print(f"  id={block.id}")
            print(f"  name={block.name}")
            print(f"  input={block.input}")  # OpenAIと違い dict でパース済み

        # モデルの発言をそのまま履歴に積む。
        # response.content をまるごと積むのが重要。
        # text だけ抜き出して積むと thinking ブロック等が欠落して壊れる。
        messages.append({"role": "assistant", "content": response.content})

        # --- 4. 実際に関数を呼ぶのは、ここ。自分のコード ----------------
        tool_results = []
        for block in tool_uses:
            print(f"\n>>> 実行: {block.name}(...)")

            # tools.py の call_tool は JSON文字列を受け取る作りなので、
            # dict を文字列に戻して渡す。OpenAI版と実装を共有するための橋渡し。
            result = call_tool(block.name, json.dumps(block.input))

            preview = result if len(result) <= 300 else result[:300] + " ...(略)"
            print(f"<<< 結果:\n{preview}")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,  # どの呼び出しへの返答かを対応づける
                    "content": result,
                }
            )

        # --- 5. 結果を履歴に積む ---------------------------------------
        # OpenAI版は role="tool" を1件ずつ積んだが、
        # Anthropic は role="user" に全部まとめて入れる。
        # 複数まとめて返さないと、モデルが並列ツール呼び出しをやめてしまう。
        messages.append({"role": "user", "content": tool_results})

        print()

    print(f"\n[打ち切り] {MAX_STEPS} ステップに達したので停止しました。")


if __name__ == "__main__":
    main()
