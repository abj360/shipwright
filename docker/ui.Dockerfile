FROM node:20-alpine AS build

WORKDIR /app
COPY ui/package.json ./
RUN npm install
COPY ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/ui.nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
