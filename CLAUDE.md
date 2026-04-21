# BrikOps — שיטת עבודה לעדכונים

## שורה תחתונה — 2 מצבים בלבד:

### 1. שינוי קוד רגיל (דפים, טקסטים, באגים, לוגיקה)
```
ברפליט: ./deploy.sh --prod
```
זהו. Capgo מעלה OTA אוטומטית, הטלפונים מתעדכנים לבד. לא צריך מק, לא Xcode, לא כלום.

### 2. שינוי native (דרוש ./ship.sh, לא רק ./deploy.sh)

**כל אחד מהקבצים/התיקיות הבאים דורש שגם תריץ `./ship.sh` אחרי ה-`./deploy.sh --prod`:**
- `frontend/capacitor.config.json` — הגדרות פלטפורמה, פלאגינים, channels
- כל מה שתחת `frontend/ios/` — Podfile, Info.plist, Swift, xcconfig, Assets.xcassets
- כל מה שתחת `frontend/android/` — build.gradle, AndroidManifest.xml, Java/Kotlin, res/
- `frontend/package.json` **אם** הוספת או הסרת פלאגין של Capacitor/Capgo
- עדכון `versionCode` / `versionName`

**למה?** כי הקבצים האלה נצרכים ע"י האפליקציה המקומפלת שכבר מותקנת אצלך באייפון/אנדרואיד. עדכון שלהם לא מועבר דרך Capgo OTA — הם דורשים בניה חדשה של האפליקציה + התקנה חדשה.

**סימן זהירות:** אם ערכת אחד מהקבצים האלה ושכחת להריץ `./ship.sh`, האייפון שלך יישאר על הגרסה הישנה לנצח — בשקט, בלי שגיאה. `./deploy.sh --prod` מאז Wave 2d מזהה שינויים כאלה ומדפיס אזהרה צהובה (`NATIVE CHANGES DETECTED`), אבל לא חוסם את ה-push.

```
במק טרמינל:
cd ~/brikops-new
./ship.sh
```

הסקריפט עושה הכל לבד:
- מסנכרן גיט (pull+push) — דואג שהמק מעודכן מול רפליט
- מזהה מה השתנה (iOS / Android / שניהם)
- פותח **רק** את ה-IDE שצריך (Xcode או Android Studio או שניהם)
- אם אין שינוי native — לא פותח כלום, פשוט יוצא

שם אני עושה Archive → Upload. וזהו.

## כללים ברזל:
- אסור לערבב קומיטים ידניים במק עם ./deploy ברפליט — `ship.sh` מטפל בהכל.
- אם השתנו רק קבצים ב-`frontend/src/` או `public/` → **לא צריך native build**. Capgo מטפל.
- אייקונים / capacitor plugins / גרסה → **כן native**.
