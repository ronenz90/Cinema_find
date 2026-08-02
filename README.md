# Cinema City Showtime Watcher (GitHub Pages + Actions)

מוגדר עבור: **ronenz90/Cinema_find**, סיסמת כניסה: זו שנבחרה (ה-hash כבר
משולב ב-`docs/app.js`).

מערכת שרצה לגמרי בתוך GitHub, בחינם:

- **GitHub Pages** (`/docs`) - אתר סטטי מוגן סיסמה, עם שתי לשוניות:
  "הוספת מעקב" ו-"מעקבים פתוחים" (עריכה/מחיקה).
- **GitHub Actions** - שלושה workflows:
  1. `check-showtimes.yml` - כל 3 שעות: בודק כל מעקב, שולח מייל אם נוספו
     תאריכים/שעות (בטווח השעות שהוגדר), לכתובת שנבחרה (או ברירת מחדל).
  2. `process-watch-request.yml` - מטפל ב-issues שנפתחים מהאתר: הוספה,
     עריכה או מחיקה של מעקב.
  3. `index-movies.yml` - כל לילה מרענן את רשימת הסרטים להשלמה אוטומטית
     בטופס (`docs/movies.json`), כדי שתמיד תשקף את הסרטים שמוקרנים כרגע.

## תכונות

- **טווח שעות למעקב** - למשל רק הקרנות בין 19:00 ל-23:00. ברירת מחדל: כל היום.
- **מייל יעד לכל מעקב** - אפשר להשאיר ריק (יישלח לכתובת ברירת המחדל
  שהוגדרה כ-secret), או להזין כתובת ספציפית לאותו מעקב בלבד.
- **מעקבים פתוחים** - לשונית שמציגה את כל המעקבים הפעילים (נטענת ישירות
  מ-`config/watches.json` דרך raw.githubusercontent.com), עם כפתורי
  עריכה (טווח שעות / מייל) ומחיקה. שינוי הסרט/הסניף/האולם עצמם דורש
  מחיקה והוספה מחדש.
- **רשימת סרטים מתעדכנת** - הטופס מציע autocomplete מתוך `docs/movies.json`,
  שמתעדכן אוטומטית כל לילה מרשימת "עכשיו בקולנוע" באתר.

## למה זה בנוי ככה (ולא "רק" GitHub Pages)

GitHub Pages משרת קבצים סטטיים בלבד - לא יכול להריץ קוד, לגרד אתרים, או
לשלוח מיילים. GitHub Actions (באותו repo, בחינם ל-repos ציבוריים) הוא
המנוע שמריץ את הבדיקות והעדכונים בפועל.

## ⚠️ לגבי הגנת הסיסמה

הסיסמה **לא** נשמרת כטקסט גלוי - רק ה-hash שלה (SHA-256) מוטמע ב-
`docs/app.js`. זה מונע מסקרנים אקראיים לגלות אותה בקוד המקור, אבל **זו
לא הגנה קריפטוגרפית אמיתית**: מי שרואה את קוד המקור (כל אחד יכול, כי זה
אתר סטטי פומבי) יכול תיאורטית לנסות לפצח את ה-hash (brute-force / rainbow
table) במיוחד אם הסיסמה נפוצה. הסיכון בפועל נמוך: גם אם מישהו "יעקוף"
את המסך, כל מה שהוא יכול לעשות הוא לפתוח/לערוך/למחוק בקשות מעקב - לא
לגשת למידע רגיש.

## הקמה שלב-אחר-שלב

### 1. יצירת ה-repo
1. צרו repo **ציבורי** בשם `Cinema_find` תחת המשתמש `ronenz90` (כך
   שה-URLs שכבר משולבים בקוד יתאימו). אם תרצו שם/משתמש אחר, עדכנו את
   `GITHUB_OWNER`/`GITHUB_REPO` בראש `docs/app.js`.
2. העלו את כל הקבצים מהתיקייה הזו (כולל `.github/`, `docs/`, `scraper/`,
   `config/`, `state/`).

### 2. הפעלת GitHub Pages
1. Settings > Pages.
2. Source: "Deploy from a branch". Branch: `main`, תיקייה: `/docs`.
3. תוך דקה-שתיים האתר יהיה זמין ב-
   `https://ronenz90.github.io/Cinema_find/`

### 3. יצירת שלוש תוויות (labels)
Issues > Labels > New label, בדיוק כך (אותיות קטנות, מקפים):
- `watch-request`
- `watch-edit`
- `watch-delete`

### 4. הגדרת Secrets לשליחת מיילים (Gmail SMTP - חינמי)
1. הפעילו אימות דו-שלבי בחשבון ה-Gmail ששולח (חובה ליצירת App Password).
2. צרו App Password ב- https://myaccount.google.com/apppasswords
3. Settings > Secrets and variables > Actions > New repository secret,
   הוסיפו:
   - `GMAIL_ADDRESS` - כתובת ה-Gmail ששולחת
   - `GMAIL_APP_PASSWORD` - ה-App Password (16 תווים, בלי רווחים)
   - `ALERT_RECIPIENT_EMAIL` - כתובת ברירת מחדל (בשימוש כשלא מוזנת כתובת
     ספציפית למעקב מסוים)

### 5. בדיקה
- גשו לאתר, הכניסו סיסמה, הוסיפו מעקב לדוגמה.
- לחיצה על "הוסף מעקב" פותחת issue מוכן ב-GitHub - לחצו "Submit new issue".
- תוך רגע ה-issue אמור להיסגר עם תגובת אישור, וה-מעקב יופיע בלשונית
  "מעקבים פתוחים" וב-`config/watches.json`.
- להרצה מיידית בלי לחכות לקרון: Actions > Check Cinema City showtimes >
  Run workflow.
- כנ"ל לרענון מיידי של רשימת הסרטים: Actions > Index movie list > Run workflow.

## איך זה עובד בפועל

1. **הוספת מעקב**: הטופס בונה issue עם `cinema/hall_type/movie/hour_from/
   hour_to/[email]` בגוף ההודעה, ומתייג `watch-request`.
2. **עריכה/מחיקה**: הלשונית "מעקבים פתוחים" טוענת את `watches.json`
   הנוכחי (כולל ה-`id` הפנימי של כל מעקב), ומאפשרת לפתוח issue מתויג
   `watch-edit` (עם `id` + טווח שעות/מייל חדשים) או `watch-delete` (עם
   `id` בלבד).
3. **עיבוד**: `process-watch-request.yml` רץ על כל issue חדש, בודק איזו
   תווית יש לו, ומריץ את `scraper/parse_issue.py --action add/edit/delete`
   בהתאם. משם commit חזרה ל-repo, תגובה, וסגירת ה-issue.
4. **בדיקה תקופתית**: `check-showtimes.yml` רץ כל 3 שעות, מריץ
   `scraper/cinema_watcher.py` (Playwright headless), עובר על כל מעקב,
   משווה ל-`state/state.json`, ומסנן לפי טווח השעות שהוגדר. אם יש שינוי
   רלוונטי - נשלח מייל נפרד לכתובת של אותו מעקב (או לברירת המחדל).
   הריצה הראשונה לכל מעקב חדש רק קובעת "נקודת ייחוס" - לא שולחת מייל.
5. **אינדוקס לילי**: `index-movies.yml` רץ כל לילה, שולף את רשימת "עכשיו
   בקולנוע" (HTML רגיל, בלי Playwright - הכרטיסים האלה נטענים מהשרת,
   בניגוד לווידג'ט ההזמנה עצמו) וכותב ל-`docs/movies.json`.

## מגבלות ידועות

- **תזמון**: cron ב-GitHub Actions הוא "best effort" ויכול להתעכב בכמה
  דקות. אם ה-repo לא פעיל 60 יום, GitHub משבית לוחות זמנים (Run
  workflow ידני מפעיל מחדש).
- **הסלקטורים**: מבוססים על מבנה ה-HTML האמיתי נכון לעכשיו. שינוי עתידי
  באתר עשוי לדרוש עדכון ב-`scraper/cinema_watcher.py`.
- **עריכה חלקית**: דרך הלשונית "מעקבים פתוחים" אפשר לערוך רק טווח שעות
  ומייל - לא את הסרט/סניף/אולם עצמם (למקרה כזה: מחקו והוסיפו מחדש).
- **טווח שעות**: ברמת דיוק של שעה עגולה (לא דקות), ותומך גם ב"מעטפת"
  חצות (למשל 22 עד 2), אך לא בשני טווחים נפרדים לאותו מעקב.
- **הגנת סיסמה**: כאמור למעלה - בסיסית, לא קריפטוגרפית אמיתית.

## מבנה הקבצים

```
.github/workflows/
  check-showtimes.yml        # cron - בדיקה + מיילים
  process-watch-request.yml  # מגיב ל-issues (הוספה/עריכה/מחיקה)
  index-movies.yml           # cron לילי - מרענן את רשימת הסרטים
docs/
  index.html                 # האתר הסטטי (GitHub Pages)
  app.js                      # הגנת סיסמה, טפסים, ניהול מעקבים
  style.css
  movies.json                 # נכתב אוטומטית ע"י index-movies.yml
scraper/
  cinema_watcher.py           # הגרידה בפועל + שליחת מיילים
  parse_issue.py              # add/edit/delete על watches.json
  index_movies.py             # אינדוקס רשימת הסרטים
  requirements.txt
config/
  watches.json                 # רשימת המעקבים הפעילים
state/
  state.json                    # תוצאות הריצה הקודמת (להשוואה)
```
