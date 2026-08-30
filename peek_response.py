"""API のレスポンスを丸ごと覗くだけのスクリプト。ループは回さない。"""

import os

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOLS

load_dotenv()

client = OpenAI()

response = client.chat.completions.create(
    model=os.getenv("MODEL", "gpt-5-mini"),
    messages=[
        {"role": "system", "content": "あなたはファイル操作エージェントです。"},
        {"role": "user", "content": "workspace に何のファイルがあるか調べて"},
    ],
    tools=TOOLS,
)

print("=" * 70)
print("【1】response の型")
print("=" * 70)
print(type(response))

print()
print("=" * 70)
print("【2】response 全体を JSON にしたもの（これが返ってきた中身の全部）")
print("=" * 70)
print(response.model_dump_json(indent=2, exclude_none=True))

print()
print("=" * 70)
print("【3】よく使うフィールドだけ抜き出す")
print("=" * 70)
print(f"response.id             = {response.id}")
print(f"response.model          = {response.model}")
print(f"len(response.choices)   = {len(response.choices)}")

choice = response.choices[0]
print(f"choice.finish_reason    = {choice.finish_reason}")
print(f"choice.message.role     = {choice.message.role}")
print(f"choice.message.content  = {choice.message.content!r}")
print(f"choice.message.tool_calls は {type(choice.message.tool_calls)}")

if choice.message.tool_calls:
    tc = choice.message.tool_calls[0]
    print(f"  tc.id                 = {tc.id}")
    print(f"  tc.type               = {tc.type}")
    print(f"  tc.function.name      = {tc.function.name}")
    print(f"  tc.function.arguments = {tc.function.arguments!r}")
    print(f"  arguments の型        = {type(tc.function.arguments)}")

print()
print("=" * 70)
print("【4】usage = 課金の実体")
print("=" * 70)
print(response.usage.model_dump_json(indent=2, exclude_none=True))
