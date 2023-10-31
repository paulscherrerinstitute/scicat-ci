FROM node:16 AS installer

WORKDIR /frontend
COPY package*.json /frontend/
RUN npm ci
COPY . /frontend/
# A browser is needed for automated tests
RUN apt-get update && apt-get install -y chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/lib/chromium/

FROM node:16 AS builder
WORKDIR /frontend
COPY --from=installer /frontend /frontend

RUN npx ng build

FROM nginx:1.12-alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /frontend/dist/ /usr/share/nginx/html/
COPY scripts/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
