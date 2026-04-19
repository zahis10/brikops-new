# התקנת UI/UX Pro Max Skill

## שלב 1 — מצא את תיקיית ה-skills של Cowork

פתח Terminal על המק והרץ:

```bash
ls -la ~/Library/Application\ Support/Claude/skills/ 2>/dev/null || \
ls -la ~/.claude/skills/ 2>/dev/null || \
ls -la ~/Documents/Claude/skills/ 2>/dev/null
```

אחת מהן תראה את רשימת ה-skills שלך (brikops-code-reviewer, brikops-qa-tester וכו').
זו התיקייה הנכונה.

## שלב 2 — העתק את ה-skill

(החלף את `<SKILLS_DIR>` במסלול מהשלב הקודם)

```bash
cp -r ~/Documents/Claude/workspace/brikops-new/ui-ux-pro-max-skill-install/ui-ux-pro-max <SKILLS_DIR>/
```

למשל אם המסלול הוא `~/.claude/skills/`:
```bash
cp -r ~/Documents/Claude/workspace/brikops-new/ui-ux-pro-max-skill-install/ui-ux-pro-max ~/.claude/skills/
```

## שלב 3 — ודא שהותקן

```bash
ls <SKILLS_DIR>/ui-ux-pro-max/
# צריך לראות: SKILL.md, data/, scripts/
```

## שלב 4 — בדיקה ש-Python עובד

```bash
python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "dashboard saas" --domain style -n 2
```

אם רואים פלט — זה עובד. פתח מחדש את Cowork וה-skill יופיע ברשימה.

## שימוש

ב-Cowork תוכל לכתוב למשל:
- "תן לי design system לאפליקציית fintech"
- "תבדוק את ה-UX של הדף הזה"
- "מה הסגנון המתאים ל-SaaS productivity app?"

וה-skill יופעל אוטומטית.
