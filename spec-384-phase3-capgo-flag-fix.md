# #384 Phase 3 — תיקון דגל Capgo CLI

> Run #3 נפל כי `--bundle-version` לא דגל תקין ב-Capgo CLI.
> הדגל הנכון הוא `-b` (ראה https://github.com/Cap-go/CLI).
> זה ספק של שינוי אחד: החלפת `--bundle-version` ב-`-b`.

## משימה יחידה — עדכון workflow קיים

**קובץ לשנות:** `.github/workflows/deploy-frontend-capgo.yml`

**שלב:** "Upload bundle to Capgo"

**לפני:**

```yaml
      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production --bundle-version "1.0.${{ github.run_number }}"
```

**אחרי:**

```yaml
      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production -b "1.0.${{ github.run_number }}"
```

ההבדל היחיד: `--bundle-version` → `-b`.

## DO NOT

- ❌ לא לשנות כלום חוץ מהשורה הזאת.
- ❌ לא לגעת ב-`on:`, `paths:`, steps אחרים.
- ❌ לא לשנות את `1.0.${{ github.run_number }}`.
- ❌ לא להריץ את ה-workflow.

## VERIFY

1. `grep -n " -b " .github/workflows/deploy-frontend-capgo.yml` — מחזיר שורה אחת עם `-b "1.0.${{ github.run_number }}"`.
2. `grep -n "bundle-version" .github/workflows/deploy-frontend-capgo.yml` — אפס שורות.
3. `git diff HEAD~1 HEAD -- .github/workflows/deploy-frontend-capgo.yml` — מראה שינוי של שורה אחת בלבד.

## דווח לי כשסיימת

- commit SHA.
- פלט של `git diff HEAD~1 HEAD --stat`.

אחרי הדיווח — אדחוף שינוי קטן ב-`frontend/**` ונראה ש-Run #4 עובר.
