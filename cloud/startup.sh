#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io git curl openssl
systemctl enable --now docker
REPO_URL=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/attributes/repo-url)
IP=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
if [ ! -d /opt/oqim/.git ]; then
  git clone --depth=1 "$REPO_URL" /opt/oqim
fi
if [ ! -f /etc/oqim.env ]; then
  umask 077
  printf 'ADMIN_PASSWORD=%s\nSECRET_KEY=%s\nCOOKIE_SECURE=1\nTRUST_PROXY=1\n' "$(openssl rand -hex 12)" "$(openssl rand -hex 32)" > /etc/oqim.env
fi
mkdir -p /var/lib/oqim
chown 10001:10001 /var/lib/oqim
docker build -t oqim:local /opt/oqim
docker network inspect oqim >/dev/null 2>&1 || docker network create oqim
docker run --rm --env-file=/etc/oqim.env -v /var/lib/oqim:/data oqim:local flask --app app:create_app seed
if ! docker container inspect oqim-app >/dev/null 2>&1; then
  docker run -d --name=oqim-app --restart=unless-stopped --network=oqim --env-file=/etc/oqim.env -v /var/lib/oqim:/data oqim:local
else
  docker start oqim-app
fi
printf '%s.sslip.io {\n reverse_proxy oqim-app:8080\n}\n' "$IP" > /etc/oqim.Caddyfile
if ! docker container inspect oqim-proxy >/dev/null 2>&1; then
  docker run -d --name=oqim-proxy --restart=unless-stopped --network=oqim -p 80:80 -p 443:443 -v /etc/oqim.Caddyfile:/etc/caddy/Caddyfile:ro -v oqim-caddy-data:/data -v oqim-caddy-config:/config caddy:2
else
  docker start oqim-proxy
fi
