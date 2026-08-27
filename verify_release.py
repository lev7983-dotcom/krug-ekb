"""Read-only check that Render serves one coherent KRUG release."""
import argparse
import json
import re
import sys
from urllib.request import Request, urlopen


def read(url):
    request = Request(url, headers={"User-Agent": "KRUG-release-check/1"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8"), response.status


parser = argparse.ArgumentParser(description="Проверить рабочую версию КРУГ")
parser.add_argument("--base", default="https://krug-ekb.onrender.com")
parser.add_argument("--expected", default="", help="Например: v109")
parser.add_argument("--commit", default="", help="Первые 7–8 символов Git-коммита")
args = parser.parse_args()
base = args.base.rstrip("/")

try:
    health_text, health_status = read(f"{base}/api/health")
    html, html_status = read(f"{base}/index.html?release-check=1")
    health = json.loads(health_text)
except Exception as error:
    print(f"[ОШИБКА] Сервер не ответил: {type(error).__name__}")
    sys.exit(1)

asset_match = re.search(r'app\.js\?v=(\d+)', html)
release = str(health.get("release") or "")
commit = str(health.get("commit") or "")
html_release = f"v{asset_match.group(1)}" if asset_match else ""
telegram = health.get("telegram") or {}
checks = [
    (health_status == 200 and health.get("ok") is True, "API отвечает"),
    (html_status == 200 and bool(html_release), "HTML отвечает и содержит версию"),
    (release == html_release, f"API и HTML совпадают: {release or 'нет версии'}"),
    (not args.expected or release == args.expected, f"Ожидаемая версия: {args.expected or release}"),
    (not args.commit or commit.startswith(args.commit), f"Ожидаемый коммит: {args.commit or commit or 'не указан'}"),
    (telegram.get("api_ok") is True, "Telegram API подключён"),
    (telegram.get("webhook_ok") is True, "Telegram webhook подключён"),
]

print("КРУГ — проверка рабочего релиза")
for ok, title in checks:
    print(f"[{'OK' if ok else 'ОШИБКА'}] {title}")
print(f"Версия: {release or '—'} · HTML: {html_release or '—'} · commit: {commit or '—'} · uptime: {health.get('uptime_seconds', '—')} сек.")
sys.exit(0 if all(ok for ok, _ in checks) else 1)
