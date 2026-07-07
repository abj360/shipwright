FROM node:20-alpine

WORKDIR /app
COPY gateway/package.json ./
RUN npm install
COPY gateway ./
RUN npm run build

CMD ["node", "dist/server.js"]
