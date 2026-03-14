import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

const AccessibilityPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-amber-50/30 py-8 px-4" dir="rtl">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="חזרה"
          >
            <ArrowRight className="w-5 h-5 text-slate-600" />
          </button>
          <h1 className="text-2xl font-bold text-slate-900">הצהרת נגישות</h1>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6 md:p-8 space-y-6">
          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3">מחויבות לנגישות</h2>
            <p className="text-sm leading-relaxed text-slate-700">
              BrikOps מחויבת להנגשת האפליקציה והשירותים שלה לאנשים עם מוגבלויות, בהתאם לתקן הישראלי 5568
              (המבוסס על הנחיות WCAG 2.1 ברמת AA) ולתקנות שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות לשירות), התשע"ג-2013.
            </p>
            <p className="text-sm leading-relaxed text-slate-700 mt-2">
              אנו פועלים לשיפור הנגישות באופן שוטף ומשקיעים משאבים בהתאמת האפליקציה לשימוש נוח ושוויוני עבור כלל המשתמשים.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3">מצב הנגישות הנוכחי</h2>
            <p className="text-sm leading-relaxed text-slate-700">
              האפליקציה עומדת בחלק מדרישות תקן 5568. בוצעה סקירת נגישות קוד מקיפה במרץ 2026 וזוהו פערים שאנו עובדים על תיקונם.
            </p>
            <p className="text-sm leading-relaxed text-slate-700 mt-2">
              מה בוצע עד כה:
            </p>
            <ul className="list-disc list-inside text-sm text-slate-700 mt-1 space-y-1 mr-2">
              <li>האפליקציה מוגדרת בעברית עם כיוון טקסט מימין לשמאל (RTL) בכל הדפים</li>
              <li>רכיבי ממשק מרכזיים (דיאלוגים, תפריטים, בחירות) בנויים עם תמיכה מלאה בניווט מקלדת וקוראי מסך</li>
              <li>טפסים כוללים הודעות שגיאה מקושרות לשדות הרלוונטיים</li>
              <li>האפליקציה מאפשרת הגדלה (זום) ללא הגבלה</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3">מגבלות ידועות</h2>
            <p className="text-sm leading-relaxed text-slate-700 mb-2">
              להלן מגבלות נגישות ידועות שאנו עובדים על תיקונן:
            </p>
            <ul className="list-disc list-inside text-sm text-slate-700 space-y-2 mr-2">
              <li>חלק מהחלונות הקופצים באפליקציה טרם הונגשו במלואם לניווט מקלדת וקוראי מסך</li>
              <li>מדדי התקדמות (Progress bars) אינם מזוהים על ידי טכנולוגיות מסייעות</li>
              <li>חלק מהכפתורים המבוססים על אייקונים בלבד חסרים תיאור טקסטואלי לקוראי מסך</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3">פנייה בנושא נגישות</h2>
            <p className="text-sm leading-relaxed text-slate-700">
              נתקלתם בבעיית נגישות? נשמח לשמוע ולטפל. ניתן לפנות אלינו:
            </p>
            <ul className="text-sm text-slate-700 mt-2 space-y-2 mr-2">
              <li>
                דוא"ל:{' '}
                <a
                  href="mailto:support@brikops.com"
                  className="text-amber-600 hover:text-amber-700 underline font-medium"
                  dir="ltr"
                >
                  support@brikops.com
                </a>
              </li>
              <li>
                טלפון:{' '}
                <a
                  href="tel:+972-3-000-0000"
                  className="text-amber-600 hover:text-amber-700 underline font-medium"
                  dir="ltr"
                >
                  03-000-0000
                </a>
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3">תאריך סקירת נגישות אחרונה</h2>
            <p className="text-sm leading-relaxed text-slate-700">
              מרץ 2026
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3">מידע נוסף</h2>
            <p className="text-sm leading-relaxed text-slate-700">
              למידע נוסף על נגישות אינטרנט ותקני נגישות בישראל, ניתן לבקר באתר{' '}
              <a
                href="https://www.gov.il/he/departments/topics/website_accessibility"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-600 hover:text-amber-700 underline font-medium"
              >
                gov.il — נגישות אתרי אינטרנט
              </a>
              .
            </p>
          </section>

          <div className="border-t border-slate-200 pt-4 mt-6">
            <p className="text-xs text-slate-400">
              הצהרה זו עודכנה לאחרונה: מרץ 2026
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccessibilityPage;
