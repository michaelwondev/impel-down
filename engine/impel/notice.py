"""차단 시 브라우저에 돌려주는 안내 페이지."""
import html
from datetime import datetime
from typing import Optional

MESSAGE = "정신 차리고 중요한 일에 집중하세요."
_DAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Impel Down</title>
<style>
  html, body { height: 100%; margin: 0; }
  body { display: flex; align-items: center; justify-content: center; background: #111; color: #eee;
         font-family: -apple-system, "Apple SD Gothic Neo", sans-serif; text-align: center; }
  main { padding: 32px; }
  .msg { font-size: 20px; font-weight: 600; margin-bottom: 18px; }
  .title { font-size: 15px; opacity: .85; }
  .next { font-size: 14px; opacity: .7; margin-top: 6px; }
  .host { font-size: 12px; opacity: .45; margin-top: 22px; font-family: ui-monospace, Menlo, monospace; }
</style>
</head>
<body>
<main>
{{body}}
</main>
</body>
</html>
"""


def format_next_open(t: datetime) -> str:
    return "%s %02d:00" % (_DAYS_KO[t.weekday()], t.hour)


def render(title: str, next_open: Optional[datetime], host: str) -> str:
    lines = [
        '<div class="msg">%s</div>' % html.escape(MESSAGE),
        '<div class="title">%s</div>' % html.escape(title),
    ]
    if next_open is not None:
        lines.append('<div class="next">다음 열림 %s</div>' % html.escape(format_next_open(next_open)))
    lines.append('<div class="host">%s</div>' % html.escape(host))
    return _TEMPLATE.replace("{{body}}", "\n".join(lines))
