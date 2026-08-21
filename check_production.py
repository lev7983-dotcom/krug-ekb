"""Read-only KRUG production readiness check. Never prints secret values."""
import os
import re
import sys
from urllib.parse import urlparse, parse_qs


def value(name):
    return (os.environ.get(name) or "").strip()


checks = []


def check(ok, title, fix):
    checks.append((bool(ok), title, fix))


token = value("BOT_TOKEN") or value("KRUG_BOT_TOKEN")
webhook_secret = value("TELEGRAM_WEBHOOK_SECRET")
public_url = value("PUBLIC_URL")
database_url = value("DATABASE_URL")
database = urlparse(database_url)
sslmode = parse_qs(database.query).get("sslmode", [""])[0].lower()
admins = [item.strip() for item in value("ADMIN_TELEGRAM_IDS").split(",") if item.strip()]

check(bool(re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{30,}", token)), "Новый Telegram-токен установлен", "Создайте новый токен через BotFather и сохраните только в секретах хостинга.")
check(len(webhook_secret) >= 32 and webhook_secret != token, "Независимый webhook-секрет установлен", "Создайте отдельную случайную строку длиной не менее 32 символов.")
check(public_url.startswith("https://") and bool(urlparse(public_url).netloc), "PUBLIC_URL использует HTTPS", "Укажите полный HTTPS-адрес приложения.")
check(database.scheme in {"postgres", "postgresql"} and bool(database.hostname), "Подключена PostgreSQL-база", "Добавьте DATABASE_URL российской PostgreSQL-базы.")
check(sslmode in {"require", "verify-ca", "verify-full"}, "Шифрование подключения к базе обязательно", "Добавьте к DATABASE_URL параметр sslmode=require или более строгий.")
check(value("DATA_RESIDENCY_RF_CONFIRMED") == "1", "Хранение персональных данных в РФ подтверждено", "Сначала документально проверьте регион основной БД, резервных копий, журналов и фотографий, затем установите 1.")
check(bool(value("LEGAL_OPERATOR_NAME")), "Указан оператор персональных данных", "Заполните настоящее ФИО/название оператора и при наличии ИНН.")
check(bool(value("LEGAL_OPERATOR_ADDRESS")), "Указан адрес оператора", "Заполните действительный почтовый адрес оператора.")
check(bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value("LEGAL_OPERATOR_EMAIL"))), "Указана рабочая почта оператора", "Добавьте адрес, на котором принимаются обращения о персональных данных.")
check(bool(admins) and all(item.isdigit() for item in admins), "Назначен владелец-администратор", "Добавьте Telegram ID владельца в ADMIN_TELEGRAM_IDS.")
check(value("KRUG_ALLOW_DEV_AUTH") != "1", "Тестовый вход отключён", "Удалите KRUG_ALLOW_DEV_AUTH или установите 0.")

print("КРУГ — проверка готовности production")
for ok, title, fix in checks:
    print(f"[{'OK' if ok else 'НУЖНО'}] {title}")
    if not ok:
        print(f"        {fix}")

failed = sum(not ok for ok, _, _ in checks)
print(f"\nРезультат: {len(checks) - failed}/{len(checks)} обязательных технических пунктов.")
if database_url:
    print("Важно: расположение базы невозможно доказать по строке подключения; сохраните подтверждение российского региона от провайдера.")
sys.exit(1 if failed else 0)
