FROM node:20-alpine

WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package*.json ./
RUN npm ci

COPY . .
# Bakes production bundle; after changing React/CSS run: docker compose build frontend --no-cache
RUN npm run build

EXPOSE 4173
CMD ["npm", "run", "preview:host", "--", "--host", "0.0.0.0", "--port", "4173"]
