"""最小のLLMエージェント。フレームワークは使わない。

【このファイルの主張】
エージェントの正体は while ループである。
「考える」のは LLM だが、「回す」「実行する」「止める」のは全部このコード。

    while ステップ上限に達するまで:
        1. 会話履歴を丸ごとAPIに送る
        2. 返事に tool_calls が無ければ → 完成。ループを抜ける
        3. あれば → 自分のコードでその関数を実行する
        4. 実行結果を会話履歴に積む
        5. 1に戻る

実行:
    .venv/bin/python agent.py
    .venv/bin/python agent.py "チケット #1043 に対応して"
"""

import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOLS, call_tool

load_dotenv()

MODEL = os.getenv("MODEL", "gpt-5-mini")

# モデルが延々とツールを呼び続けたときに止めるための上限。
# これが無いと、無限ループでAPIコストが溶ける。
# 「止め方を決めるのはハーネスであってLLMではない」ということ。
MAX_STEPS = 10

#プロンプトをLLMに渡している。ここの書き方次第でLLMの挙動が変わる。
SYSTEM_PROMPT = """あなたは情報システム部の若手社員のアシスタントです。
届いた問い合わせチケットに、社内マニュアル(KB)を調べながら対応してください。

- 対応を頼まれたら、まず read_ticket でチケット本文を確認すること
- 何をすべきか分からないときは、推測せず search_kb で社内マニュアルを検索すること
- 検索結果が複数ある場合は、read_kb で中身を確認してから正しい記事を選ぶこと
- 対応が終わったら reply_ticket で回答を書き込み、何をしたかを日本語で簡潔に報告すること
"""

DEFAULT_TASK = "チケット #1042 に対応してください。"


def main() -> None:
    # コマンドライン引数でタスクを差し替えられるようにしておく、引数無しならDEFAULT＿TASKが実行される
    task = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK

    client = OpenAI()  # APIキーは環境変数 OPENAI_API_KEY から自動で読まれる

    # 【最重要】これが「記憶」の正体。
    # LLM は内部で記憶を持たない。実は前回の会話を一切覚えていない！
    # 複数回の応答（同一のセッション）でこれまでの記憶を保持しているように見えるのは、ユーザの文章の履歴を毎回すべて再送しているから
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    print(f"タスク: {task}")
    print(f"モデル: {MODEL}\n")

    for step in range(1, MAX_STEPS + 1):
        print(f"{'=' * 60}")
        print(f"ステップ {step}  （会話履歴 {len(messages)} 件を送信）")
        print(f"{'=' * 60}")

        # --- 1. 履歴を丸ごと送る ---------------------------------------
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,  # 「こういう道具があるよ」という説明をAPI呼び出しのたびに毎回渡す
        )
        message = response.choices[0].message

        # --- 2. 終了判定 -----------------------------------------------
        # LLMがツールを呼んでいない = やることが無い = agent.pyを終了。
        # 終了を決めているのは if 文であって、LLM ではない。
        if not message.tool_calls:
            print("\n【最終回答】")
            print(message.content)
            return

        # --- 3. モデルが「呼びたい」と言ってきた内容を、生のまま見る ----
        # ここがこの教材の山場。
        # モデルは関数を実行していない。この JSON を返しただけである。
        print("\nモデルが返してきた tool_calls（生データ）:")
        for tc in message.tool_calls:
            print(f"  id={tc.id}")
            print(f"  name={tc.function.name}")
            print(f"  arguments={tc.function.arguments}")

        # モデルの発言を履歴に積む。
        # tool_calls を含む assistant のターンは、
        # このあと tool の結果を積むために 必ず 履歴に残す必要がある。
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        # --- 4. 実際に関数を呼ぶのは、このコードでありLLMではない ----------------
        for tc in message.tool_calls:
            print(f"\n>>> 実行: {tc.function.name}(...)")

            result = call_tool(tc.function.name, tc.function.arguments)

            # 長い結果はログ上だけ省略して表示（履歴には全文を積む）
            preview = result if len(result) <= 300 else result[:300] + " ...(略)"
            print(f"<<< 結果:\n{preview}")

            # --- 5. 結果を履歴に積む -----------------------------------
            # tool_call_id で「どの呼び出しへの返答か」を対応づける。
            # ここを間違えると API がエラーを返す。
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        print()

    # for が break されずに終わった = 上限に達した
    print(f"\n[打ち切り] {MAX_STEPS} ステップに達したので停止しました。")


if __name__ == "__main__":
    main()
