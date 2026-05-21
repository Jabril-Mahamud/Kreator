FROM node:22-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm install

COPY tsconfig.json ./
COPY src/ src/
RUN npm run build

FROM node:22-alpine

RUN addgroup -g 1001 appuser && adduser -u 1001 -G appuser -D appuser

WORKDIR /home/appuser
COPY --from=builder /build/dist ./dist
COPY --from=builder /build/node_modules ./node_modules
COPY --from=builder /build/package.json ./

USER 1001

EXPOSE 8000

CMD ["node", "dist/index.js"]
