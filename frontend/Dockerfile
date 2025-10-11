FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=development

COPY frontend/package*.json ./
RUN npm install

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
