# Cinema City Showtime Watcher (GitHub Pages + Actions)

מוגדר עבור: **ronenz90/Cinema_find**, סיסמת כניסה: זו שנבחרה (ה-hash כבר
משולב ב-`docs/app.js`).

מערכת שרצה לגמרי בחינם, עם שלושה חלקים:

- **GitHub Pages** (`/docs`) - אתר סטטי מוגן סיסמה, עם שתי לשוניות:
  "הוספת מעקב" ו-"מעקבים פתוחים" (עריכה/מחיקה) - **פעולה מיידית, בלי
  לאשר שום דבר ב-GitHub**.
- **Cloudflare Worker** (`/worker`) - פרוקסי קטן וחינמי שמאמת את הסיסמה
  בצד שרת וכותב ישירות ל-`config/watches.json` דרך ה-GitHub API, בלי
  לחשוף שום טוקן לדפדפן.
- **GitHub Actions** - שני workflows: בדיקת זמנים כל 3 שעות + אינדוקס
  לילי של רשימת הסרטים.

## למה יש צורך ב-Worker בכלל

GitHub Pages משרת קבצים סטטיים בלבד - כל קוד ה-JS שלו גלוי לכל מבקר
(View Source). כדי לאפשר לאתר לכתוב ל-repo **מיידית**, בלי טוקן חשוף
בדפדפן ובלי לחיצת אישור ידנית על issue, צריך רכיב קטן שמחזיק את הטוקן
**בצד שרת בלבד** - זה בדיוק תפקידו של ה-Worker. Cloudflare Workers חינמי
לגמרי לשימוש כזה (100,000 בקשות ביום במסגרת התוכנית החינמית).

## ⚠️ לגבי הגנת הסיסמה

הפעם יש **שתי שכבות**:
1. **בצד לקוח** (`docs/app.js`) - hash מוטמע, בשביל UX מיידי (הסתרת
   הטופס ממבקרים אקראיים). זו לא הגנה אמיתית לבדה.
2. **בצד שרת** (ה-Worker) - כל בקשת הוספה/עריכה/מחיקה כוללת את הסיסמה,
   וה-Worker מאמת אותה מול `PASSWORD_HASH` (secret בצד שרת, לא נגיש
   לדפדפן) **לפני** שהוא נוגע ב-repo. זו הגנה אמיתית - גם מי שקורא את
   קוד ה-JS ומנסה לקרוא ישירות ל-Worker בלי הסיסמה הנכונה, יקבל 401.

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

### 3. יצירת טוקן GitHub מוגבל (עבור ה-Worker)
1. https://github.com/settings/personal-access-tokens/new (Fine-grained token)
2. **Repository access**: "Only select repositories" > בחרו את `Cinema_find` בלבד.
3. **Permissions** > Repository permissions > **Contents**: "Read and write".
   השאירו את כל שאר ההרשאות ללא גישה (No access) - עקרון ההרשאה
   המינימלית.
4. צרו את הטוקן, והעתיקו אותו (הוא יוצג פעם אחת בלבד).

### 4. פריסת ה-Cloudflare Worker (חד-פעמי - אחר כך הכל אוטומטי)

כדי שלא תצטרך לערוך קוד ישירות באתר Cloudflare (לא נוח בנייד), הקמנו
פריסה אוטומטית: מרגע שתסיים את ההגדרה החד-פעמית כאן, כל עדכון עתידי
ל-`worker/index.js` ייפרס לבד ברגע שתשמור אותו ב-GitHub (גם מהאפליקציה
או מהאתר בנייד - שם יש עורך טקסט נוח בהרבה).

**א. יצירת חשבון Cloudflare + פרטים חד-פעמיים**
1. הרשמו בחינם ב- https://dash.cloudflare.com
2. מצאו את ה-**Account ID** שלכם - הוא מופיע בצד ימין של דף הבית של
   הדשבורד (או תחת Workers & Pages).
3. צרו API Token: https://dash.cloudflare.com/profile/api-tokens >
   Create Token > תבנית "Edit Cloudflare Workers" > המשיכו וצרו.
   העתיקו את הטוקן (מוצג פעם אחת).

**ב. הוספת 4 secrets ב-GitHub** (Settings > Secrets and variables > Actions):
- `CLOUDFLARE_API_TOKEN` - הטוקן מהשלב הקודם
- `CLOUDFLARE_ACCOUNT_ID` - ה-Account ID
- `WORKER_GITHUB_PAT` - הטוקן שיצרתם בשלב 3 למעלה (הרשאת Contents
  Read/write על ה-repo הזה בלבד)
- `WORKER_PASSWORD_HASH` - אותו hash שכבר משולב ב-`docs/app.js`:
  `071dc4f6efd2db563e4daa5d444ac4ba803095191af2ad51a01b3dca1f4fbde2`

**ג. הרצה ראשונה**
Actions > Deploy Cloudflare Worker > Run workflow. אחרי שהוא מסתיים
בהצלחה (עיגול ירוק), לכו ל-Cloudflare Dashboard > Workers & Pages >
`cinema-find-api` כדי להעתיק את כתובת ה-Worker (`https://cinema-find-
api.<your-subdomain>.workers.dev`).

**מכאן והלאה**: כל שינוי עתידי ב-`worker/index.js` (למשל דרך עריכת הקובץ
ישירות ב-GitHub באתר/באפליקציה, ואז Commit) יגרום לפריסה אוטומטית מחדש -
בלי לגעת ב-Cloudflare שוב.

### 5. חיבור האתר ל-Worker
ב-`docs/app.js`, עדכנו:
```javascript
const WORKER_URL = "https://cinema-find-api.<your-subdomain>.workers.dev";
```
והעלו את הקובץ המעודכן ל-repo.

### 6. הגדרת Secrets לשליחת מיילים (Gmail SMTP - חינמי, ל-GitHub Actions)
1. הפעילו אימות דו-שלבי בחשבון ה-Gmail ששולח (חובה ליצירת App Password).
2. צרו App Password ב- https://myaccount.google.com/apppasswords
3. ב-repo: Settings > Secrets and variables > Actions > New repository secret:
   - `GMAIL_ADDRESS` - כתובת ה-Gmail ששולחת
   - `GMAIL_APP_PASSWORD` - ה-App Password (16 תווים, בלי רווחים)
   - `ALERT_RECIPIENT_EMAIL` - כתובת ברירת מחדל

### 7. בדיקה
- גשו לאתר, הכניסו סיסמה, הוסיפו מעקב לדוגמה - **הוא אמור להתווסף מיידית**,
  בלי לעבור דרך GitHub בכלל.
- בדקו שהוא מופיע בלשונית "מעקבים פתוחים" וב-`config/watches.json`.
- לבדיקת המייל: Actions > Test email > Run workflow.
- להרצה מיידית של הבדיקה האמיתית: Actions > Check Cinema City showtimes >
  Run workflow.
- לרענון מיידי של רשימת הסרטים: Actions > Index movie list > Run workflow.

## איך זה עובד בפועל

1. **הוספת/עריכת/מחיקת מעקב**: הטופס (או כפתורי "ערוך"/"מחק") שולחים
   בקשה ישירה ל-Worker, כולל הסיסמה. ה-Worker מאמת אותה, קורא את
   `config/watches.json` הנוכחי דרך GitHub API, מעדכן, וכותב בחזרה - הכל
   בתוך שנייה או שתיים, בלי GitHub issues ובלי לחיצת אישור.
2. **בדיקה תקופתית**: `check-showtimes.yml` רץ כל 3 שעות, מריץ
   `scraper/cinema_watcher.py` (Playwright headless), עובר על כל מעקב,
   משווה ל-`state/state.json`, ומסנן לפי טווח השעות שהוגדר. אם יש שינוי
   רלוונטי - נשלח מייל נפרד לכתובת של אותו מעקב (או לברירת המחדל).
   הריצה הראשונה לכל מעקב חדש רק קובעת "נקודת ייחוס" - לא שולחת מייל.
3. **אינדוקס לילי**: `index-movies.yml` רץ כל לילה, שולף את רשימת "עכשיו
   בקולנוע" (HTML רגיל, בלי Playwright) וכותב ל-`docs/movies.json`.

### קבצים שאינם בשימוש יותר (אופציונלי למחוק)

`process-watch-request.yml` ו-`scraper/parse_issue.py` היו הדרך הישנה
(מבוססת GitHub issues) לפני שהוספנו את ה-Worker. הם לא פעילים יותר בזרימה
הרגילה - אפשר להשאיר אותם (לא מזיקים) או למחוק אותם לניקיון.

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
- **סיסמה בזיכרון הדפדפן**: לאחר כניסה, הסיסמה נשמרת ב-sessionStorage
  (רק בטאב הנוכחי, נמחקת בסגירתו) כדי שאפשר יהיה לשלוח אותה ל-Worker
  בכל פעולה. זה נוח אך משמעו שהסיסמה יושבת כטקסט גלוי בזיכרון הדפדפן
  באותה הפעלה - סביר לכלי אישי קטן כזה, אך שווה לדעת.

## מבנה הקבצים

```
.github/workflows/
  check-showtimes.yml         # cron - בדיקה + מיילים
  index-movies.yml            # cron לילי - מרענן את רשימת הסרטים
  test-email.yml               # ריצה ידנית - בדיקת שליחת מייל
  deploy-worker.yml             # פריסת ה-Worker אוטומטית בכל שינוי
  process-watch-request.yml    # legacy - לא בשימוש יותר, אפשר למחוק
docs/
  index.html                  # האתר הסטטי (GitHub Pages)
  app.js                       # הגנת סיסמה, טפסים, קריאות ל-Worker
  style.css
  movies.json                  # נכתב אוטומטית ע"י index-movies.yml
worker/
  index.js                     # Cloudflare Worker - מאמת סיסמה + כותב ל-repo
  wrangler.toml                 # קונפיגורציה לפריסה אוטומטית
scraper/
  cinema_watcher.py            # הגרידה בפועל + שליחת מיילים
  index_movies.py              # אינדוקס רשימת הסרטים
  test_email.py                 # שליחת מייל בדיקה
  parse_issue.py                 # legacy - לא בשימוש יותר, אפשר למחוק
  requirements.txt
config/
  watches.json                   # רשימת המעקבים הפעילים
state/
  state.json                      # תוצאות הריצה הקודמת (להשוואה)
```
