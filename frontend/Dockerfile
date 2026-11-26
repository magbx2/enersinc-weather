# syntax=docker/dockerfile:1
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# One-shot build service: publish the immutable bundle to the shared volume
# and leave a marker the backend entrypoint requires.
CMD ["sh", "-c", "rm -rf /out/* /out/.build-complete && cp -r dist/. /out/ && touch /out/.build-complete"]
