FROM node:20.18.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build
FROM nginx:1.27.5-alpine
# API_HOST: hostname of the backend API. Default "api" matches the
# docker-compose service name; on Render set API_HOST to the backend
# service URL hostname (e.g. sunpower-backend.onrender.com, no https://).
ENV API_HOST=api
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
