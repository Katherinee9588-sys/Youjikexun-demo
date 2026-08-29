# ---- Stage 1: build the frontend ----
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend serves the SPA + API ----
FROM python:3.11-slim
WORKDIR /app

# Install Python deps (no secrets needed here)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source + built frontend into static/
COPY backend/ ./
COPY --from=frontend /build/dist ./static

# Railway injects LLM_*/ASR_* env vars at runtime; the app reads them via os.getenv.
EXPOSE 8000
CMD ["sh", "-c", "PYTHONPATH=/app uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
