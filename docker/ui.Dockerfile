FROM node:20-alpine

WORKDIR /app
COPY ui/package.json ./
RUN npm install
COPY ui ./
RUN npm run build

RUN addgroup -S app && adduser -S app -G app
USER app

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
