FROM node:22.15.0-alpine AS installer

RUN apk add --update python3 py3-setuptools make g++ chromium && rm -rf /var/cache/apk/*

WORKDIR /frontend
COPY package*.json /frontend/
RUN npm ci
COPY . /frontend/

# A browser is needed for automated tests
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/lib/chromium/

FROM node:22.15.0-alpine AS builder
WORKDIR /frontend
COPY --from=installer /frontend /frontend

RUN npx ng build

FROM nginx:1.28-alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /frontend/dist/ /usr/share/nginx/html/
COPY scripts/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
