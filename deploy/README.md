# BrikOps Cloud Deployment Guide

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  Cloudflare Pages   │────▶│  AWS App Runner       │────▶│  MongoDB     │
│  (Frontend SPA)     │     │  (Backend API)        │     │  Atlas       │
│  brikops.com        │     │  api.brikops.com      │     └──────────────┘
└─────────────────────┘     │                       │
                            │                       │────▶┌──────────────┐
                            │                       │     │  S3 Bucket   │
                            └──────────────────────┘     │  brikops-    │
                                                         │  prod-files  │
                                                         └──────────────┘
```

---

## Cloudflare Pages Settings

| Setting              | Value                                         |
|----------------------|-----------------------------------------------|
| Framework preset     | Create React App                              |
| Root directory       | `frontend`                                    |
| Build command        | `yarn build`                                  |
| Build output         | `build`                                       |
| Node version         | 18                                            |

### Cloudflare Pages Environment Variables

| Variable                  | Staging                              | Production                  |
|---------------------------|--------------------------------------|-----------------------------|
| `REACT_APP_BACKEND_URL`   | `https://api-staging.brikops.com`    | `https://api.brikops.com`   |
| `CI`                      | `true`                               | `true`                      |

### SPA Routing

The file `frontend/public/_redirects` handles SPA fallback:
```
/* /index.html 200
```
This is automatically included in the build output.

---

## AWS App Runner Settings

| Setting              | Value                             |
|----------------------|-----------------------------------|
| Source               | ECR image (from `backend/Dockerfile`) |
| Port                 | `8080`                            |
| Health check path    | `/health`                         |
| Health check interval| 10s                               |
| Health check timeout | 5s                                |
| Healthy threshold    | 1                                 |
| Unhealthy threshold  | 5                                 |
| CPU                  | 1 vCPU                            |
| Memory               | 2 GB                              |
| Min instances        | 1                                 |
| Max instances        | 4                                 |

### Docker Build

```bash
cd backend
docker build -t brikops-api .
docker tag brikops-api:latest <account>.dkr.ecr.<region>.amazonaws.com/brikops-api:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/brikops-api:latest
```

### Startup Command

Set by Dockerfile CMD:
```
uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2 --no-access-log
```
App Runner sets `PORT` automatically.

---

## Backend Environment Variables

### Required (app will not start without these)

| Variable              | Description                    | Example                       |
|-----------------------|--------------------------------|-------------------------------|
| `APP_ID`              | Application identifier         | `brikops-prod`                |
| `APP_MODE`            | Runtime mode                   | `prod`                        |
| `JWT_SECRET`          | JWT signing key (min 32 chars) | `<secret>`                    |
| `JWT_SECRET_VERSION`  | JWT secret version string      | `v1`                          |
| `MONGO_URL`           | MongoDB Atlas connection string| `mongodb+srv://...`           |
| `DB_NAME`             | Database name                  | `contractor_ops`              |

### File Storage (S3)

| Variable                  | Description                | Example              |
|---------------------------|----------------------------|----------------------|
| `FILES_STORAGE_BACKEND`   | Storage mode               | `s3`                 |
| `AWS_S3_BUCKET`           | S3 bucket name             | `brikops-prod-files` |
| `AWS_REGION`              | AWS region                 | `eu-central-1`       |
| `AWS_ACCESS_KEY_ID`       | AWS access key             | `<key>`              |
| `AWS_SECRET_ACCESS_KEY`   | AWS secret key             | `<secret>`           |

### CORS & Hosting

| Variable          | Description                          | Staging                                       | Production                                    |
|-------------------|--------------------------------------|-----------------------------------------------|-----------------------------------------------|
| `CORS_ORIGINS`    | Allowed origins (comma-separated)    | `https://staging.brikops.com`                 | `https://brikops.com,https://www.brikops.com` |
| `ALLOWED_HOSTS`   | Trusted hosts (comma-separated)      | `*.awsapprunner.com,staging.brikops.com`      | `api.brikops.com,*.awsapprunner.com`          |
| `PUBLIC_APP_URL`  | Canonical URL for redirects          | _(leave empty for staging)_                   | `https://api.brikops.com`                     |

### WhatsApp (Meta Cloud API)

| Variable                  | Description             | Value            |
|---------------------------|-------------------------|------------------|
| `WHATSAPP_ENABLED`        | Enable WhatsApp         | `true`           |
| `WA_ACCESS_TOKEN`         | Meta API token          | `<token>`        |
| `WA_PHONE_NUMBER_ID`      | WhatsApp phone ID       | `<id>`           |
| `WA_TEMPLATE_NEW_DEFECT`  | Defect template name    | `<template>`     |
| `WA_TEMPLATE_INVITE`      | Invite template name    | `<template>`     |
| `META_APP_SECRET`         | Meta app secret         | `<secret>`       |
| `WA_WEBHOOK_VERIFY_TOKEN` | Webhook verification    | `<token>`        |

### SMS (Twilio Fallback)

| Variable                       | Description              | Value       |
|--------------------------------|--------------------------|-------------|
| `SMS_ENABLED`                  | Enable SMS               | `true`      |
| `SMS_MODE`                     | SMS mode                 | `live`      |
| `TWILIO_ACCOUNT_SID`           | Twilio account SID       | `<sid>`     |
| `TWILIO_AUTH_TOKEN`            | Twilio auth token        | `<token>`   |
| `TWILIO_FROM_NUMBER`           | Twilio sender number     | `<number>`  |
| `TWILIO_MESSAGING_SERVICE_SID` | Twilio messaging SVC     | `<sid>`     |

### OTP & Auth

| Variable              | Description                    | Value              |
|-----------------------|--------------------------------|--------------------|
| `OTP_PROVIDER`        | OTP delivery channel           | `whatsapp`         |
| `OWNER_PHONE`         | Owner phone number             | `<phone>`          |
| `SUPER_ADMIN_PHONES`  | SA phones (comma-separated)    | `<phone1>,<phone2>`|
| `ENABLE_QUICK_LOGIN`  | Demo login buttons             | `false`            |
| `ENABLE_DEBUG_ENDPOINTS` | Debug API endpoints          | `false`            |

### Email (Step-up Auth)

| Variable          | Description       | Value              |
|-------------------|-------------------|--------------------|
| `STEPUP_CHANNEL`  | Step-up method    | `email`            |
| `STEPUP_EMAIL`    | Step-up recipient | `<email>`          |
| `SMTP_HOST`       | SMTP server       | `smtp.gmail.com`   |
| `SMTP_PORT`       | SMTP port         | `587`              |
| `SMTP_USER`       | SMTP username     | `<user>`           |
| `SMTP_PASS`       | SMTP password     | `<pass>`           |

### Optional

| Variable                       | Default  | Description                |
|--------------------------------|----------|----------------------------|
| `ENABLE_ONBOARDING_V2`         | `false`  | Onboarding V2 flow         |
| `ENABLE_AUTO_TRIAL`            | `true`   | Auto-create trial on signup|
| `JWT_EXPIRATION_HOURS`         | `720`    | JWT token lifetime         |
| `AWS_S3_PRESIGNED_URL_EXPIRES` | `900`    | Presigned URL TTL (sec)    |

---

## Notes

- **S3 presigned URLs** are origin-independent. Files uploaded via the backend return presigned S3 URLs directly to the browser — no CORS issue when frontend moves to Cloudflare Pages.
- **Backend does not serve frontend** when `frontend/build/` is absent (which it will be inside the Docker image). It logs `[SPA] Frontend build not found, API-only mode` and runs API-only.
- **Health endpoint** at `GET /health` returns `{"status": "ok"}` — no auth required, no DB dependency.
- **Canonical redirect** only activates when `PUBLIC_APP_URL` is set. Leave it empty for staging to avoid redirect loops.
- **TrustedHostMiddleware** only activates when `ALLOWED_HOSTS` is set and `APP_MODE=prod`. Leave unset for staging.
