FROM node:22-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

ARG API_URL=http://api.localhost
ENV VITE_API_URL=$API_URL

RUN npm run build

FROM nginx:alpine

RUN addgroup -g 1001 appuser && adduser -u 1001 -G appuser -D appuser

COPY --chown=1001:1001 --from=builder /build/dist /usr/share/nginx/html

RUN printf 'server {\n\
    listen 3000;\n\
    location / {\n\
        root /usr/share/nginx/html;\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

# nginx runs as the non-root appuser, so every path the master process writes
# (cache temp dirs, logs, pid file) must be owned by that user or it fails to
# start with "mkdir() /var/cache/nginx/... failed (13: Permission denied)".
RUN chown -R 1001:1001 /var/cache/nginx /var/log/nginx \
    && touch /var/run/nginx.pid \
    && chown 1001:1001 /var/run/nginx.pid

COPY <<'ENTRYPOINT' /docker-entrypoint.d/90-map-api-url.sh
#!/bin/sh
if [ -n "$API_URL" ]; then
  find /usr/share/nginx/html -name '*.js' -exec \
    sed -i "s|http://api.localhost|$API_URL|g" {} +
fi
ENTRYPOINT
RUN chmod +x /docker-entrypoint.d/90-map-api-url.sh

EXPOSE 3000

USER 1001

CMD ["nginx", "-g", "daemon off;"]
