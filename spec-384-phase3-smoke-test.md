# #384 Phase 3 — הוספת smoke test ל-workflow

> אני לא יכול לדחוף שינויים ל-`.github/workflows/**` כי ה-PAT שלי בלי `workflow` scope.
> הספק הזה הוא שינוי יחיד: הוספת step שמאמת שהבאנדל שנבנה מכיל את `api.brikops.com`.
> זה מונע מצב שבו build שבור (בלי `REACT_APP_BACKEND_URL`) יועלה ל-Capgo וישבור login למשתמשים.

## משימה יחידה — עדכון workflow קיים

**קובץ לשנות:** `.github/workflows/deploy-frontend-capgo.yml`

**מה להוסיף:** step חדש בין שלב "Build frontend" לשלב "Upload bundle to Capgo".

**לפני (מצב נוכחי, שורות ~25-37):**

```yaml
      - name: Build frontend
        working-directory: frontend
        env:
          REACT_APP_BACKEND_URL: ${{ vars.REACT_APP_BACKEND_URL }}
          REACT_APP_GOOGLE_CLIENT_ID: ${{ vars.REACT_APP_GOOGLE_CLIENT_ID }}
          REACT_APP_GIT_SHA: ${{ github.sha }}
        run: yarn build

      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production -b "1.0.${{ github.run_number }}"
```

**אחרי:**

```yaml
      - name: Build frontend
        working-directory: frontend
        env:
          REACT_APP_BACKEND_URL: ${{ vars.REACT_APP_BACKEND_URL }}
          REACT_APP_GOOGLE_CLIENT_ID: ${{ vars.REACT_APP_GOOGLE_CLIENT_ID }}
          REACT_APP_GIT_SHA: ${{ github.sha }}
        run: yarn build

      - name: Smoke test — verify backend URL baked into bundle
        working-directory: frontend
        run: |
          if ! grep -rq "api.brikops.com" build/static/js/; then
            echo "::error::Built bundle does NOT contain 'api.brikops.com'. REACT_APP_BACKEND_URL was probably not set. Refusing to upload a broken bundle to Capgo."
            exit 1
          fi
          echo "Smoke test passed: backend URL is present in bundle."

      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production -b "1.0.${{ github.run_number }}"
```

ההבדל היחיד: הוספת step בשם "Smoke test — verify backend URL baked into bundle" בין Build ל-Upload.

## DO NOT

- ❌ לא לשנות את שלבי Build או Upload עצמם.
- ❌ לא לשנות את שם ה-workflow, ה-`on:`, ה-`paths:`, או Setup Node.
- ❌ לא לגעת ב-`-b` flag או ב-channel.
- ❌ לא להריץ את ה-workflow בעצמך.

## VERIFY

1. `grep -n "Smoke test" .github/workflows/deploy-frontend-capgo.yml` — מחזיר שורה אחת.
2. `grep -n "api.brikops.com" .github/workflows/deploy-frontend-capgo.yml` — מחזיר לפחות שורה אחת (מה-grep בתוך ה-step).
3. `git diff HEAD~1 HEAD -- .github/workflows/deploy-frontend-capgo.yml` — מראה רק הוספת step אחד.

## דווח לי כשסיימת

- commit SHA.
- פלט של `git diff HEAD~1 HEAD --stat`.
