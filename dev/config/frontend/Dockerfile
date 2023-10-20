FROM node:16 AS installer

# A browser is needed for automated tests
RUN apt-get update && apt-get install -y chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/lib/chromium/

WORKDIR /frontend
COPY package*.json /frontend/

RUN npm ci

EXPOSE 4200
CMD ["node serve"]