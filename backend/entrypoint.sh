#!/bin/sh
set -e
echo "==> اجرای مهاجرت‌های دیتابیس"
alembic upgrade head
echo "==> کاشت دادهٔ اولیه (دسته‌ها و قوانین)"
python -m app.seeds.run
echo "==> اجرای سرور"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
