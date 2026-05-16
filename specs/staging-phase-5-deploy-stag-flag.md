# #425 — Hotfix: deploy.sh --stag flag + staging GitHub workflow

## What & Why

Phase 5 of the staging environment setup. Add `./deploy.sh --stag` flag so Zahi can deploy code changes to staging EB env (`Brikops-api-staging-env`) before promoting to prod.

Workflow goal:

    edit code → push → ./deploy.sh --stag → manually test → ./deploy.sh --prod

Without this, every code change goes straight to prod (current state). Staging is now functional (Phase 1-4 done) but there's no scripted deploy path to it.

---

## Files to change

### 1. `deploy.sh` — add `--stag` mode

Extend the existing arg parser and branch-check logic to support a third mode: "stag" (staging).

#### Change a — Move `FRONTEND_BACKEND_URL` default to AFTER arg parsing

OLD line 9:

```
FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api.brikops.com}"
```

DELETE that line. ADD AFTER the `done` of the arg parser loop (~line 19):

```
if [[ "$MODE" == "stag" ]]; then
  FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api-staging.brikops.com}"
else
  FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api.brikops.com}"
fi
```

#### Change b — Add `--stag` to arg parser (~line 14)

OLD:

```
--prod|--force) MODE="prod"; shift ;;
```

ADD AFTER:

```
--stag|--staging) MODE="stag"; shift ;;
```

#### Change c — Add staging branch check (~line 22, right after the prod branch check)

OLD:

```
if [[ "$MODE" == "prod" && "$branch" != "main" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to 'main' to deploy."
  exit 1
fi
```

ADD AFTER:

```
if [[ "$MODE" == "stag" && "$branch" != "staging" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to 'staging' to deploy to staging."
  exit 1
fi
```

#### Change d — Update "What will deploy" URLs (~lines 138-139)

OLD:

```
if [[ $frontend_changed -eq 1 ]]; then echo "  - Frontend (Cloudflare Pages -> https://app.brikops.com)"; fi
if [[ $backend_changed -eq 1 ]]; then echo "  - Backend  (GitHub Actions -> https://api.brikops.com)"; fi
```

REPLACE WITH:

```
if [[ $frontend_changed -eq 1 ]]; then
  if [[ "$MODE" == "stag" ]]; then
    echo "  - Frontend (Cloudflare Pages -> https://staging.brikops-new.pages.dev)"
  else
    echo "  - Frontend (Cloudflare Pages -> https://app.brikops.com)"
  fi
fi
if [[ $backend_changed -eq 1 ]]; then
  if [[ "$MODE" == "stag" ]]; then
    echo "  - Backend  (GitHub Actions -> https://api-staging.brikops.com)"
  else
    echo "  - Backend  (GitHub Actions -> https://api.brikops.com)"
  fi
fi
```

#### Change e — Update dry-run help text (~line 152-159)

OLD:

```
if [[ "$MODE" != "prod" ]]; then
  echo "Dry-run only. To deploy:"
  echo "  ./deploy.sh --prod"
  echo "  ./deploy.sh --prod \"my commit message\""
  echo "  ./deploy.sh --prod --yes          # skip confirmation"
  echo "  ./deploy.sh --prod --skip-checks  # skip preflight"
  exit 0
fi
```

REPLACE WITH:

```
if [[ "$MODE" != "prod" && "$MODE" != "stag" ]]; then
  echo "Dry-run only. To deploy:"
  echo "  ./deploy.sh --prod              # production (must be on main branch)"
  echo "  ./deploy.sh --stag              # staging    (must be on staging branch)"
  echo "  ./deploy.sh --prod \"my message\"  # with commit message"
  echo "  ./deploy.sh --prod --yes         # skip confirmation"
  echo "  ./deploy.sh --prod --skip-checks # skip preflight"
  exit 0
fi
```

#### Change f — Update confirm prompt (~line 209)

OLD:

```
if [[ "$YES" != "1" ]]; then
  read -rp "Deploy to production? (y/N): " confirm
  if [[ "${confirm,,}" != "y" ]]; then
    echo "Cancelled."
    exit 0
  fi
fi
```

REPLACE WITH:

```
if [[ "$YES" != "1" ]]; then
  if [[ "$MODE" == "stag" ]]; then
    read -rp "Deploy to STAGING? (y/N): " confirm
  else
    read -rp "Deploy to production? (y/N): " confirm
  fi
  if [[ "${confirm,,}" != "y" ]]; then
    echo "Cancelled."
    exit 0
  fi
fi
```

#### Change g — Update DEPLOY SUMMARY URLs (~lines 268-272)

OLD:

```
echo " Where to check:"
echo "   Backend:   https://github.com/zahis10/brikops-new/actions"
echo "   Frontend:  Cloudflare Pages dashboard → app.brikops.com"
echo "   Health:    https://api.brikops.com/health"
```

REPLACE WITH:

```
echo " Where to check:"
echo "   Backend:   https://github.com/zahis10/brikops-new/actions"
if [[ "$MODE" == "stag" ]]; then
  echo "   Frontend:  https://staging.brikops-new.pages.dev"
  echo "   Health:    https://api-staging.brikops.com/health"
else
  echo "   Frontend:  https://app.brikops.com (Cloudflare Pages)"
  echo "   Health:    https://api.brikops.com/health"
fi
```

---

### 2. NEW file: `.github/workflows/deploy-backend-staging.yml`

Create a new workflow file that mirrors `deploy-backend.yml` but for staging:

```yaml
name: Deploy Backend to Elastic Beanstalk (Staging)

on:
  push:
    branches: [staging]
    paths:
      - 'backend/**'
      - '.platform/**'

permissions:
  id-token: write
  contents: read

env:
  AWS_REGION: eu-central-1
  ECR_REPO: brikops-api
  EB_APP: brikops-api
  EB_ENV: Brikops-api-staging-env

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG -t $ECR_REGISTRY/$ECR_REPO:staging-latest backend/
          docker push $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPO:staging-latest

      - name: Generate Dockerrun.aws.json
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cat > Dockerrun.aws.json <<EOF
          {
            "AWSEBDockerrunVersion": "1",
            "Image": {
              "Name": "$ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG",
              "Update": "true"
            },
            "Ports": [
              {
                "ContainerPort": 8080
              }
            ]
          }
          EOF

      - name: Create deploy bundle
        run: zip -r deploy.zip Dockerrun.aws.json .platform/

      - name: Deploy to Elastic Beanstalk (Staging)
        env:
          VERSION_LABEL: staging-${{ github.sha }}
        run: |
          BUCKET=$(aws elasticbeanstalk create-storage-location --query S3Bucket --output text)
          aws s3 cp deploy.zip s3://$BUCKET/$EB_APP/deploy-$VERSION_LABEL.zip
          aws elasticbeanstalk create-application-version \
            --application-name $EB_APP \
            --version-label $VERSION_LABEL \
            --source-bundle S3Bucket=$BUCKET,S3Key=$EB_APP/deploy-$VERSION_LABEL.zip
          aws elasticbeanstalk update-environment \
            --application-name $EB_APP \
            --environment-name $EB_ENV \
            --version-label $VERSION_LABEL
          echo "Staging deployment started: $VERSION_LABEL"
```

#### Differences from `deploy-backend.yml`:

- name: "(Staging)" suffix
- branches: [staging] (not main)
- EB_ENV: `Brikops-api-staging-env` (not `Brikops-api-env`)
- Docker tag: `staging-latest` (not `latest`)
- VERSION_LABEL prefix: `staging-${sha}` (so EB version labels are clearly distinguishable from prod)

---

## Out of scope

- DO NOT modify `deploy-frontend-capgo.yml` — Capgo OTA stays on main only. Staging is web-only for now (mobile staging testing is a separate phase).
- DO NOT modify any GitHub secrets or vars — `AWS_ROLE_ARN` already has perms for both EB envs (verified by Phase 1 deploy success).
- DO NOT touch any backend code (config.py, routers, etc.).
- DO NOT touch any frontend code (.env files, components, etc.).

---

## VERIFY

1. `bash -n deploy.sh` — syntax check, must pass with no output
2. `./deploy.sh` (no flag) on `main` branch → should print dry-run help text mentioning BOTH `--prod` AND `--stag`
3. `./deploy.sh --stag` on `main` branch → should fail with `Switch to 'staging' to deploy to staging`
4. `./deploy.sh --prod` on `staging` branch → should fail with `Switch to 'main' to deploy`
5. `git checkout staging && ./deploy.sh` (no flag) → dry-run, no error
6. `git diff --stat` → only `deploy.sh` and `.github/workflows/deploy-backend-staging.yml` changed
7. YAML lint the new workflow file: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-backend-staging.yml'))"` (no exception)

---

## review.txt

After all VERIFY steps pass, write `review.txt` with:

- Rollback SHA (current HEAD before changes)
- Full diff of `deploy.sh`
- Full content of new `deploy-backend-staging.yml`
- All 7 VERIFY outputs
- Commit message: `feat(deploy): add --stag flag + staging GitHub workflow`
- End with `AWAITING ZAHI APPROVAL — DO NOT DEPLOY`

---

## Deploy after approval

Zahi will run `./deploy.sh --prod` from main branch — even though these changes ENABLE the staging path, the FILES live on main and need to be deployed to prod first (deploy.sh + workflow file are repo-wide, not per-branch).

After main has the new deploy.sh + workflow:

1. `git checkout staging`
2. `git merge main` (to bring deploy.sh + workflow into staging)
3. `git push origin staging`

Then `./deploy.sh --stag` will work from staging branch.
