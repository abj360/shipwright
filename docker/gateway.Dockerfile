FROM node:20-alpine AS build

WORKDIR /app
COPY gateway/package.json ./
RUN npm install
COPY gateway ./
RUN npm run build

FROM node:20-alpine

WORKDIR /app
COPY --from=build /app/dist ./dist
COPY gateway/package.json ./
RUN npm install --omit=dev

RUN addgroup -S app && adduser -S app -G app
USER app

CMD ["node", "dist/server.js"]
