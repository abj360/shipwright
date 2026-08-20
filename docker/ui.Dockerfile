FROM node:20-alpine AS build

WORKDIR /app
COPY ui/package.json ./
RUN npm install
COPY ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
