FROM node:20-alpine AS build

WORKDIR /app
COPY ui/package.json ./
RUN npm install
COPY ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/ui.nginx.conf.template /etc/nginx/templates/default.conf.template
# Substitute only the token, so nginx's own $uri/$host survive envsubst.
ENV NGINX_ENVSUBST_FILTER=GATEWAY_TOKEN

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
