#!/usr/bin/env bash
# پشتیبان‌گیری از دیتابیس و فایل‌های آپلودشده
set -euo pipefail

cd "$(dirname "$0")"
set -a; . ./.env; set +a

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="backups/$STAMP"
mkdir -p "$OUT"

echo "==> پشتیبان دیتابیس (فایل‌های آپلودشده هم داخل دیتابیس‌اند)"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-accounting}" -d "${POSTGRES_DB:-accounting}" \
  | gzip > "$OUT/database.sql.gz"

echo
echo "پشتیبان ساخته شد: $OUT"
du -sh "$OUT"/* | sed 's/^/  /'
cat <<TXT

برای بازگردانی:
  gunzip -c $OUT/database.sql.gz | docker compose exec -T db psql -U ${POSTGRES_USER:-accounting} -d ${POSTGRES_DB:-accounting}
TXT
