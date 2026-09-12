FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# نام میزبان و پورت بک‌اند — قابل تغییر با متغیر محیطی در زمان اجرا
ENV BACKEND_HOST=backend BACKEND_PORT=8000 NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
