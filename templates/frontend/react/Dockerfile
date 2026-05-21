FROM node:22-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

RUN addgroup -g 1001 appuser && adduser -u 1001 -G appuser -D appuser

COPY --from=builder /build/dist /usr/share/nginx/html

RUN echo 'server { \
    listen 3000; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

USER 1001

CMD ["nginx", "-g", "daemon off;"]
