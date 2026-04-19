# התקנת UI/UX Pro Max Skill

ה-skill מוכן. צריך להעתיק אותו לתיקיית ה-skills של Cowork.

## מצא את תיקיית ה-skills

פתח Terminal על המק והרץ:

```bash
for d in ~/.claude/skills ~/Library/Application\ Support/Claude/skills ~/Documents/Claude/skills; do
  [ -d "$d" ] && echo "✓ $d" && ls "$d" | head -3
done
```

אחד מהמסלולים יראה את הרשימה של ה-skills שלך (brikops-*).
זה המסלול הנכון — שמור אותו בראש.

## העתק את ה-skill

החלף `<SKILLS_DIR>` במסלול שמצאת:

```bash
cp -r "/Users/$USER/Documents/Claude/workspace/brikops-new/ui-ux-pro-max-v2/ui-ux-pro-max" <SKILLS_DIR>/
```

אם המסלול של Cowork שלך הוא `~/.claude/skills/`, הפקודה תהיה:

```bash
cp -r ~/Documents/Claude/workspace/brikops-new/ui-ux-pro-max-v2/ui-ux-pro-max ~/.claude/skills/
```

(תצטרך לוודא את המסלול של תיקיית workspace של Cowork על המק שלך — אולי זה נקרא אחרת אצלך)

## בדיקה

```bash
python3 <SKILLS_DIR>/ui-ux-pro-max/scripts/search.py "fintech crypto" --design-system
```

אם רואים פלט — זה עובד. סגור ופתח את Cowork וה-skill יהיה זמין.
