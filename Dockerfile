# یک ایمیج برای کل برنامه: فرانت ساخته می‌شود و بک‌اند خودش آن را سرو می‌کند.
# یک کانتینر، یک پورت (PORT، پیش‌فرض ۸۰۰۰)، فقط یک وابستگی: Postgres.

# ---- مرحلهٔ ۱: ساخت فرانت ----
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- مرحلهٔ ۲: بک‌اند + خروجی فرانت ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 STATIC_DIR=/srv/static
WORKDIR /srv

# postgresql-client برای pg_dump — پشتیبان‌گیری از داخل خود برنامه
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /app/dist /srv/static

RUN chmod +x entrypoint.sh \
 && mkdir -p /data && chmod 777 /data

EXPOSE 8000
CMD ["./entrypoint.sh"]
