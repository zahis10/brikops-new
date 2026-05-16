# REPLIT TASK — תיקון באג Excel Import: "1.0" במקום "1"

## הבעיה

בייבוא דיירים מExcel, המערכת קוראת מספרי בניין/דירה כ-`1.0`, `2.0`, `3.0` במקום `1`, `2`, `3`. תוצאה: 198 שגיאות "בניין '1.0' לא נמצא בפרויקט", אי אפשר לייבא.

באקסל הרגיל המספרים נראים `1`, `2`, `3` — אבל בפועל הם מאוחסנים כ-`number` (float) ב-XLSX. openpyxl קורא אותם כ-`float`, ו-`str(1.0)` = `"1.0"` ולא `"1"`.

## שורש הבעיה

קובץ: `backend/contractor_ops/import_router.py`

### באג #1 — פונקציה `_str_val` (שורה 229)

```python
def _str_val(val):
    if val is None:
        return ""
    return str(val).strip()  # ← str(1.0) = "1.0"
```

זו הפונקציה המרכזית שכל המערכת משתמשת בה לקריאת ערכים מ-Excel. הtה לא מטפלת בהבדל בין int-as-float (1.0) לבין float אמיתי (1.5).

### באג #2 — `_validate_row` שורה 282-289

```python
for key in row:
    if key in ('source_row', 'handover_date', 'tenant_phone', 'tenant_phone_2'):
        continue
    if isinstance(row[key], (int, float)):
        row[key] = str(row[key])  # ← אותה בעיה — str(1.0) = "1.0"
    elif row[key] is None:
        row[key] = ""
    else:
        row[key] = str(row[key]).strip()
```

לולאה שמזהה int/float ומבצעת המרה חיצונית ל-string, בלי לבדוק `.is_integer()`.

## התיקון

### שינוי 1 — `_str_val` (שורה 229-232)

```python
def _str_val(val):
    if val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))   # 1.0 → "1"  (לא "1.0")
    return str(val).strip()
```

זה מטפל ב-`1.0`, `2.0`, `3.0` ומחזיר `"1"`, `"2"`, `"3"`.

ערכי float אמיתיים (`1.5`, `42.7`) ממשיכים לעבור כרגיל.

### שינוי 2 — `_validate_row` (שורה 282-289)

עדיף להפנות את הלולאה להשתמש ב-`_str_val` במקום לחזור על הלוגיקה. כך שינוי עתידי ב-`_str_val` יישאר במקום אחד:

```python
for key in row:
    if key in ('source_row', 'handover_date', 'tenant_phone', 'tenant_phone_2'):
        continue
    row[key] = _str_val(row[key])
```

זה מחליף 7 שורות בשורה אחת ונותן את אותה תוצאה (אפילו טובה יותר — כי עכשיו טפול שונה ל-`1.0` עובד).

## השפעה

הבאג השפיע על:
- `building` — מספר בניין ("1.0" לא נמצא)
- `apartment` — מספר דירה (אם מאוחסן כ-number ב-Excel)
- `tenant_id` — תעודת זהות (אם הופיע כ-number)
- כל שדה אחר שהמשתמש הקליד כמספר באקסל

אחרי התיקון, כל השדות יקבלו את הצורה הנקייה: `"1"` במקום `"1.0"`.

## VERIFY

לאחר deploy ל-staging:

1. השתמש בקובץ ה-Excel של 277 הדיירים שזהי ניסה לייבא
2. הזן אותו שוב במסך "ייבוא נתוני רוכשים"
3. **תוצאה צפויה:** 198 שגיאות "בניין '1.0' לא נמצא" → 0 שגיאות מסוג זה
4. השורות אמורות להופיע כ-`תקינות` (ירוק) במקום `שגיאות` (אדום)

בנוסף בדיקת unit-test פנימית:

```python
# תוסיף לבדיקה ידנית:
assert _str_val(1.0) == "1"
assert _str_val(2) == "2"
assert _str_val(1.5) == "1.5"
assert _str_val("בניין 1") == "בניין 1"
assert _str_val(None) == ""
```

## DO NOT

- אל תשנה את `_normalize_building_name` — היא תקינה
- אל תשנה את `_normalize_unit_no` — היא תקינה  
- אל תיגע ב-`_parse_date` — שם הbug של `.is_integer()` כבר מטופל בצורה אחרת (serial number to date)
- אל תוסיף stripping ל-handover_date / tenant_phone — הם מעובדים בצורה ייחודית

## Standing rule

Replit עורך קבצים בלבד. לא commit, לא push, לא deploy.

אחרי Build → אני אריץ `./deploy.sh --stag` ב-Shell של Replit. אחרי אימות ב-staging → `./deploy.sh --prod`.

## Commit message

```
import_router: fix int-as-float reading from Excel (1.0 → 1)

openpyxl reads integer cells as Python float (1 → 1.0). Previously
str(val) produced "1.0" which broke building/apartment lookup against
DB values stored as "1". Now _str_val detects int-valued floats and
converts via int first. Refactored _validate_row to use _str_val
instead of duplicating the conversion logic.

Fixes: 198/277 rows failing import with "בניין '1.0' לא נמצא בפרויקט"
```

מצופה זמן: 5-10 דקות. שינוי קטן בקובץ אחד, קל לבדיקה.
