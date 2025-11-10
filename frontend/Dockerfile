# Lightweight Node base for Next.js dev server.
FROM node:20-alpine

# Mirror local project structure for bind mounts.
WORKDIR /app

ENV NODE_ENV=development \
    PORT=3000

# Preinstall dependencies so `npm run dev` starts instantly in compose.
COPY frontend/package*.json ./
RUN npm install

# Run Next.js with explicit host/port so Docker networking works out of the box.
CMD ["sh", "-c", "npm install && npm run dev -- --hostname 0.0.0.0 --port ${PORT:-3000}"]
