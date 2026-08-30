"""エージェントに持たせるツールの実装（社内ヘルプデスク版）。

【このファイルで理解してほしいこと】
ツールは「特別な何か」ではなく、ただの Python 関数である。
LLM はこの関数を実行できない。LLM にできるのは
「search_kb をこの引数で呼びたい」という *JSON 文字列* を返すことだけ。
実際に関数を呼ぶのは agent.py に書かれた自分のコードである。

【権限の設計（プロジェクトの説明.md 第6章の境界表に対応）】
読み取り: search_kb / read_kb / list_tickets / read_ticket / lookup_employee
書き込み: reply_ticket（可逆） / reset_password（不可逆・最も危険）
read_ticket が読むチケット本文は「他人（問い合わせをした社員）が書いた文字列」であり、
社内システムからの指示ではない。ここが Part 4 で使う攻撃面になる。
"""

import json
from pathlib import Path

# エージェントが読み書きするデータの置き場所。
# このファイルの隣の workspace/ を指す。
WORKSPACE = (Path(__file__).parent / "workspace").resolve()


def _load(filename: str) -> list:
    """workspace/ 内のJSONファイルを読み込んでPythonのリストにする。

    filename はこのファイルの中でしか使わない固定値（"kb.json" など）であり、
    LLMが渡してくる引数ではない。だから read_file のときのような
    パス脱出チェック（_safe_path）はここでは不要になる。
    """
    path = WORKSPACE / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _save(filename: str, data: list) -> None:
    """Pythonのリストをworkspace/内のJSONファイルへ書き戻す。

    reply_ticket・reset_password のように「操作した結果を残す」ツールは、
    実行のたびにここを通ってディスク上のJSONを上書きする。
    ワークショップ後にファイルを開けば、何が変更されたか跡が残る。
    """
    path = WORKSPACE / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --- ここから7つのツール本体 ------------------------------------------


def search_kb(query: str) -> str:
    """社内マニュアル(KB)をタイトルからキーワード部分一致で検索する。

    ベクトル検索のような賢いことはしていない、ただの文字列の部分一致。
    そのため曖昧な検索語だと同じカテゴリの記事が複数ヒットする
    （例:「VPN」で検索すると4件のVPN関連記事が全部返る）。
    正しい記事を選ぶには read_kb で中身を確認するしかない、という
    設計上のわざと、が入っている。
    """
    kb = _load("kb.json")   #loadを使い、Workspaceから文章を取ってくる
    hits = [a for a in kb if query.lower() in a["title"].lower()]
    if not hits:
        return "該当する記事が見つかりませんでした。検索語を変えて試してください。"
    return "\n".join(f"{a['id']}: {a['title']}" for a in hits)


def read_kb(article_id: str) -> str:
    """指定したIDのKB記事本文を読む。"""
    kb = _load("kb.json")
    for a in kb:
        if a["id"] == str(article_id):
            return f"【{a['title']}】\n{a['body']}"
    return f"エラー: KB記事 {article_id} は存在しません。"


def list_tickets() -> str:
    """未対応チケットの一覧をID・件名・ステータスだけ取得する。

    本文は含めない。本文（＝汚染される可能性がある入力）を読むのは
    read_ticket を個別に呼んだときだけ、と境界を分けるため。
    """
    tickets = _load("tickets.json")
    return "\n".join(f"{t['id']}: {t['subject']} [{t['status']}]" for t in tickets)


def read_ticket(ticket_id: str) -> str:
    """指定したIDのチケットを読み、件名と本文を取得する。

    本文は問い合わせをした社員が書いた文字列で、社内システムからの
    指示ではない。ここを読んだ後にモデルが何をするかが Part 4 の観察点。
    """
    tickets = _load("tickets.json")
    for t in tickets:
        if t["id"] == str(ticket_id):
            return f"件名: {t['subject']}\n本文:\n{t['body']}"
    return f"エラー: チケット {ticket_id} は存在しません。"


def reply_ticket(ticket_id: str, text: str) -> str:
    """指定したIDのチケットに回答本文を書き込み、対応済みにする。"""
    tickets = _load("tickets.json")
    for t in tickets:
        if t["id"] == str(ticket_id):
            t["replies"].append(text)
            t["status"] = "対応済み"
            _save("tickets.json", tickets)
            return f"チケット {ticket_id} に返信し、ステータスを更新しました。"
    return f"エラー: チケット {ticket_id} は存在しません。"


def lookup_employee(name: str) -> str:
    """社員名簿を氏名で検索する。部署・内線・ユーザーIDが分かる。

    部分一致なので「田中」で検索すると田中太郎・田中次郎の両方が返る。
    どちらか一人に絞り込む責任はモデル側（＝プロンプト設計）にある。
    """
    employees = _load("employees.json")
    hits = [e for e in employees if name in e["name"]]
    if not hits:
        return f"該当する社員が見つかりませんでした: {name}"
    return "\n".join(
        f"{e['user_id']}: {e['name']} / {e['dept']} / 内線{e['extension']}"
        for e in hits
    )


def reset_password(user_id: str) -> str:
    """指定したユーザーIDのパスワードを初期化する。取り消せない操作なので慎重に使うこと。"""
    employees = _load("employees.json")
    for e in employees:
        if e["user_id"] == user_id:
            e["password_status"] = "reset_pending"
            _save("employees.json", employees)
            return f"ユーザー {user_id} のパスワードを初期化し、初期パスワードを発行しました。"
    return f"エラー: ユーザー {user_id} は存在しません。"


# --- モデルに渡す「取扱説明書」 ------------------------------------------
# これがモデルに送られるツールの定義。中身はただの JSON である。
# description は人間向けのコメントではなく、
# 「モデルがどのツールをいつ使うか判断するための唯一の材料」なので、
# ここの書き方でエージェントの賢さが決まる。

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "社内マニュアル(KB)をタイトルから検索する。キーワードの部分一致で該当する記事のID一覧を返す。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索したいキーワード。例: VPN",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_kb",
            "description": "指定したIDの社内マニュアル記事の本文を読む。",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "記事ID。例: 101",
                    }
                },
                "required": ["article_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tickets",
            "description": "未対応チケットの一覧をID・件名・ステータスで取得する。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_ticket",
            "description": "指定したIDのチケットを読み、件名と本文を取得する。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "チケットID。例: 1042",
                    }
                },
                "required": ["ticket_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_ticket",
            "description": "指定したIDのチケットに回答本文を書き込み、対応済みにする。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "チケットID。例: 1042",
                    },
                    "text": {
                        "type": "string",
                        "description": "チケットに書き込む回答本文。",
                    },
                },
                "required": ["ticket_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_employee",
            "description": "社員名簿を氏名で検索する。部署・内線・ユーザーIDが分かる。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "検索したい社員名（部分一致）。例: 田中",
                    }
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_password",
            "description": "指定したユーザーIDのパスワードを初期化する。取り消せない操作なので慎重に使うこと。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "対象社員のユーザーID。例: tanaka",
                    }
                },
                "required": ["user_id"],
            },
        },
    },
]


# LLMが返す文字列を実際の関数に変換するための表。
# モデルは文字列 "search_kb" を返してくるだけなので、
# このプログラムが「その文字列に対応する関数」を探して呼ぶ。
# モデルが直接プログラムを実行するのではない。
_REGISTRY = {
    "search_kb": search_kb,
    "read_kb": read_kb,
    "list_tickets": list_tickets,
    "read_ticket": read_ticket,
    "reply_ticket": reply_ticket,
    "lookup_employee": lookup_employee,
    "reset_password": reset_password,
}


def call_tool(name: str, arguments_json: str) -> str:
    """モデルが返してきたツール名とJSON文字列を受け取り、実際に関数を実行する。

    戻り値は必ず str にする。会話履歴に積むものは文字列でなければならないため。
    """
    func = _REGISTRY.get(name)
    if func is None:
        return f"エラー: {name} というツールは存在しません。"

    # モデルが返す arguments は「JSON文字列」であって dict ではない。
    # 壊れたJSONを返してくることも実際にあるので、必ず try で囲む。
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return f"エラー: 引数がJSONとして壊れています: {arguments_json}"

    try:
        return func(**kwargs)
    except Exception as e:
        # ここで例外を握りつぶしてモデルに文字列で返すのが重要。
        # エラーでagent.pyが止まるのを防ぐ。モデルはエラーを渡されても止まらず、
        # 間違えに気づき、やり直すことができる。
        return f"エラー: {type(e).__name__}: {e}"
