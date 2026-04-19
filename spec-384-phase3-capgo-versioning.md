# #384 Phase 3 — Capgo bundle versioning

> Run #1 של ה-workflow עבר (`e4554b1`). Run #2 נפל כי Capgo דחה bundle עם אותו version (`0.1.0` מ-package.json) — Capgo דורש version ייחודי לכל העלאה.
> הספק הזה הוא תיקון יחיד: הוספת `--bundle-version` ל-Capgo upload.

## משימה יחידה — עדכון workflow קיים

**קובץ לשנות:** `.github/workflows/deploy-frontend-capgo.yml`

**שינוי בשלב אחד בלבד — שלב "Upload bundle to Capgo" (שורות 33-37 הקיימות):**

**לפני:**

```yaml
      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production
```

**אחרי:**

```yaml
      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production --bundle-version "1.0.${{ github.run_number }}"
```

הההבדל היחיד: הוספת `--bundle-version "1.0.${{ github.run_number }}"` בסוף שורת ה-`run`.

## DO NOT

- ❌ לא לשנות את ה-`on:`, `paths:`, או שאר ה-steps.
- ❌ לא לשנות את שם הקובץ.
- ❌ לא לגעת ב-`package.json` או להוסיף bump version לפרונט.
- ❌ לא להריץ את ה-workflow בעצמך.
- ❌ לא לשנות את מספר הגרסה ב-`versionCode`/`versionName` ב-Android.

## VERIFY

1. `grep -n "bundle-version" .github/workflows/deploy-frontend-capgo.yml` — מחזיר שורה אחת עם `github.run_number`.
2. `git diff HEAD~1 HEAD -- .github/workflows/deploy-frontend-capgo.yml` — מראה שינוי של שורה אחת בלבד (ה-`run:` בשלב ה-upload).
3. אף קובץ אחר לא שונה.

## דווח לי כשסיימת

- commit SHA של השינוי.
- פלט של `git diff HEAD~1 HEAD --stat` (מאשר קובץ אחד שונה).

לאחר הדיווח — אדחוף שינוי קטן ב-`frontend/**` ונראה ש-Run #3 יעלה גרסה `1.0.3` ויעבור בהצלחה.
