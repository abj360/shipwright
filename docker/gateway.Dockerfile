FROM node:20-alpine

WORKDIR /app
COPY gateway/package.json ./
RUN npm install
COPY gateway ./
RUN npm run build

RUN addgroup -S app && adduser -S app -G app
USER app

CMD ["node", "dist/server.js"]
