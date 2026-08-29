#!/usr/bin/env bash
# Youjikexun demo — one-shot deploy on a fresh Alibaba Cloud lightweight server.
# Tested on Ubuntu 22.04 / Debian 12. Run as root.
#
# Usage:
#   scp -r deploy/ backend/ frontend/ root@<SERVER_IP>:/opt/youjikexun/
#   ssh root@<SERVER_IP> "cd /opt/youjikexun && bash deploy/deploy.sh"
set -euo pipefail

APP_DIR="/opt/youjikexun"
cd "$APP_DIR"

echo "=== [1/5] Install system packages ==="
apt-get update -qq
apt-get install -y -qq nginx python3 python3-pip python3-venv nodejs npm curl

echo "=== [2/5] Python backend ==="
python3 -m venv .venv
. .venv/bin/activate
pip install --quiet -r backend/requirements.txt

echo "=== [3/5] Frontend build ==="
cd frontend
npm install --silent
npm run build
cd "$APP_DIR"

echo "=== [4/5] Environment ==="
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "!!! Created backend/.env from template. EDIT IT and add your API keys, then restart."
fi

echo "=== [5/5] systemd services + nginx ==="
# Backend service
cat > /etc/systemd/system/youjikexun.service <<UNIT
[Unit]
Description=Youjikexun FastAPI backend
After=network.target

[Service]
WorkingDirectory=$APP_DIR/backend
Environment=PYTHONPATH=$APP_DIR/backend
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

# Nginx: serve built frontend + reverse-proxy /api
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/youjikexun <<CONF
server {
    listen 80;
    server_name _;
    root $APP_DIR/frontend/dist;
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 90s;
    }
}
CONF
ln -sf /etc/nginx/sites-available/youjikexun /etc/nginx/sites-enabled/youjikexun

systemctl daemon-reload
systemctl enable --now youjikexun
systemctl restart youjikexun
nginx -t && systemctl restart nginx

echo ""
echo "=== DONE ==="
echo "Backend:  systemctl status youjikexun"
echo "Frontend: http://<SERVER_IP>"
echo "API docs: http://<SERVER_IP>/api/docs"
echo ""
echo "If backend/.env was just created, edit it with your LLM/ASR keys then:"
echo "  systemctl restart youjikexun"
