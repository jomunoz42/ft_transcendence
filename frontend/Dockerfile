FROM node:22-bookworm-slim

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

EXPOSE 5173

ENV VITE_API_PROXY_TARGET=http://backend:8000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
