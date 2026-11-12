#!/usr/bin/env bash
set -euo pipefail
read -rp 'GCP project ID: ' PROJECT_ID
read -rp 'Public GitHub repository HTTPS URL: ' REPO_URL
[[ "$PROJECT_ID" =~ ^[a-z][a-z0-9-]{4,61}[a-z0-9]$ ]] || exit 1
[[ "$REPO_URL" =~ ^https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$ ]] || exit 1
ZONE=us-central1-a
REGION=us-central1
gcloud config set project "$PROJECT_ID"
gcloud services enable compute.googleapis.com
if ! gcloud compute networks describe oqim-network >/dev/null 2>&1; then
  gcloud compute networks create oqim-network --subnet-mode=auto
fi
if ! gcloud compute firewall-rules describe oqim-web >/dev/null 2>&1; then
  gcloud compute firewall-rules create oqim-web --network=oqim-network --allow=tcp:80,tcp:443 --target-tags=oqim-web
fi
if ! gcloud compute firewall-rules describe oqim-ssh-iap >/dev/null 2>&1; then
  gcloud compute firewall-rules create oqim-ssh-iap --network=oqim-network --allow=tcp:22 --source-ranges=35.235.240.0/20 --target-tags=oqim-web
fi
if ! gcloud compute addresses describe oqim-ip --region="$REGION" >/dev/null 2>&1; then
  gcloud compute addresses create oqim-ip --region="$REGION"
fi
IP=$(gcloud compute addresses describe oqim-ip --region="$REGION" --format='value(address)')
gcloud compute instances create oqim-server --zone="$ZONE" --machine-type=e2-small --network=oqim-network --tags=oqim-web --address="$IP" --image-family=debian-12 --image-project=debian-cloud --boot-disk-size=20GB --boot-disk-type=pd-balanced --no-boot-disk-auto-delete --no-service-account --no-scopes --metadata="repo-url=$REPO_URL" --metadata-from-file="startup-script=$(dirname "$0")/startup.sh"
printf '\nhttps://%s.sslip.io\n' "$IP"
printf 'Startup usually takes several minutes. Inspect: gcloud compute ssh oqim-server --zone=%s --tunnel-through-iap --command="sudo journalctl -u google-startup-scripts.service --no-pager"\n' "$ZONE"
printf 'Password: gcloud compute ssh oqim-server --zone=%s --tunnel-through-iap --command="sudo cat /etc/oqim.env"\n' "$ZONE"
