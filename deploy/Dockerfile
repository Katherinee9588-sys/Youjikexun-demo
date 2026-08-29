# Youjikexun demo — single-server deploy (nginx + uvicorn)
# Build:  docker build -t youjikexun .
# Run:    docker run -d -p 80:80 --env-file backend/.env --name youjikexun youjikexun

FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/dist ./static
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*
EXPOSE 80
CMD ["sh", "-c", "nginx & PYTHONPATH=/app uvicorn app.main:app --host 127.0.0.1 --port 8000"]
