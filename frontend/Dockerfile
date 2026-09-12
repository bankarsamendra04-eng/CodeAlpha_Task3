# ==============================================================================
# AI Music Studio — Frontend Dockerfile
# Multi-stage build: Node.js Vite build -> Minimal Nginx Alpine production image.
# ==============================================================================

# Stage 1: Build static React bundle
FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies with caching
COPY package*.json ./
RUN npm ci

# Build production assets
COPY . .
RUN npm run build

# Stage 2: Serve static bundle via Nginx
FROM nginx:alpine

# Copy build artifacts
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy reverse-proxy Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -q -O - http://localhost/ || exit 1

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
