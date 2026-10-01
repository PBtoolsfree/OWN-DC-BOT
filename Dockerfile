# Build frontend
FROM node:22-alpine AS web-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci || npm install
COPY web/ .
RUN npm run build

# Build backend
FROM node:22-alpine AS backend-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# Production image
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production

# Copy backend dependencies
COPY package*.json ./
RUN npm ci --only=production || npm install --production

# Copy built backend
COPY --from=backend-builder /app/dist ./dist

# Copy built frontend
COPY --from=web-builder /app/web/dist ./web/dist

# Ensure data directory exists with correct permissions
RUN mkdir -p /app/data && chown -R node:node /app/data

USER node
EXPOSE 3000

CMD ["npm", "start"]
