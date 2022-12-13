FROM node:16 AS installer

RUN apt update && apt -y upgrade && \
    apt install -y bash git

# Prepare app directory
WORKDIR /home/node/app
COPY package*.json /home/node/app/

# set up local user to avoid running as root
RUN chown -R node:node /home/node/app
USER node

# Install our packages
RUN npm ci
COPY --chown=node:node . /home/node/app/

# Build app
FROM node:16 as builder

ARG env=production
WORKDIR /home/node/app
COPY --from=installer /home/node/app /home/node/app

RUN npx ng build --configuration=${env}

FROM nginx:1.22.0-alpine

RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /home/node/app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
