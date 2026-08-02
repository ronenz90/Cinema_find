# Cinema City Showtime Watcher (GitHub Pages + Worker + Actions)

מוגדר עבור: **ronenz90/Cinema_find**.

מערכת שרצה לגמרי בחינם, עם שלושה חלקים:

- **GitHub Pages** (`/docs`) - אתר סטטי מוגן סיסמה, עם שתי לשוניות:
  "הוספת מעקב" ו-"מעקבים פתוחים" (עריכה/מחיקה) - **פעולה מיידית**, בלי
  לאשר שום דבר ב-GitHub.
- **Cloudflare Worker** (`/worker`) - פרוקסי קטן וחינמי שמאמת את הסיסמה
  בצד שרת, קורא/כותב ישירות ל-`config/watches.json` דרך ה-GitHub API,
  ומספק לאתר גם את רשימת המעקבים בזמן אמת (בלי מטמון). נפרס אוטומטית
  ב-GitHub Actions בכל שינוי - אין צורך לערוך קוד ידנית ב-Cloudflare.
- **GitHub Actions** - כמה workflows: בדיקת זמנים כל 3 שעות, אינדוקס
  לילי של רשימת הסרטים, פריסת ה-Worker, ובדיקת מייל ידנית.

## תכונות

- **טווח שעות למעקב** - למשל רק הקרנות בין 19:00 ל-23:00. ברירת מחדל: כל היום.
- **מייל יעד לכל מעקב** - אפשר להשאיר ריק (יישלח לכתובת ברירת המחדל
  שהוגדרה כ-secret), או להזין כתובת ספציפית לאותו מעקב בלבד.
- **מעקבים פתוחים** - לשונית שמציגה את כל המעקבים הפעילים בזמן אמת
  (דרך ה-Worker, לא raw.githubusercontent.com - כדי להימנע מהשהיית
  מטמון), עם כפתורי עריכה (טווח שעות / מייל) ומחיקה. שינוי הסרט/הסניף/
  האולם עצמם דורש מחיקה והוספה מחדש.
- **רשימת סרטים מתעדכנת** - הטופס מציע השלמה אוטומטית (autocomplete
  עצמאי, לא `<datalist>` הדפדפן - לא אמין בנייד) מתוך `docs/movies.json`,
  שמתעדכן אוטומטית כל לילה מרשימת "עכשיו בקולנוע" באתר.
- **בחירה אמינה באתר סינמה סיטי** - הסקריפט לא "מדמה קליקים" על
  הדף (זה התברר כלא אמין - לחיצה יכולה "להצליח" ויזואלית מבלי שהאתר
  בפועל רושם את הבחירה), אלא **קורא ישירות לפונקציות הבחירה הפנימיות
  של Knockout.js** של האתר (`window.ticketsVM`) - בדיוק כפי שהאתר עצמו
  עושה בלחיצת עכבר. זה נמצא הרבה יותר יציב.
- **צילומי מסך לדיבוג** - כל ריצה (גם כשהיא נכשלת) שומרת צילום מסך של
  מצב הדף הסופי, ומעלה אותו כ-artifact בעמוד ה-Actions run, כדי לאבחן
  בעיות עתידיות בלי לנחש.

## למה יש צורך ב-Worker בכלל

GitHub Pages משרת קבצים סטטיים בלבד - כל קוד ה-JS שלו גלוי לכל מבקר
(View Source). כדי לאפשר לאתר לכתוב ל-repo **מיידית**, בלי טוקן חשוף
בדפדפן ובלי לחיצת אישור ידנית על issue, צריך רכיב קטן שמחזיק את הטוקן
**בצד שרת בלבד** - זה בדיוק תפקידו של ה-Worker. Cloudflare Workers חינמי
לגמרי לשימוש כזה (100,000 בקשות ביום במסגרת התוכנית החינמית).

## ⚠️ לגבי הגנת הסיסמה

יש **שתי שכבות**:
1. **בצד לקוח** (`docs/app.js`) - hash מוטמע, בשביל UX מיידי (הסתרת
   הטופס ממבקרים אקראיים). זו לא הגנה אמיתית לבדה.
2. **בצד שרת** (ה-Worker) - כל בקשת הוספה/עריכה/מחיקה כוללת את הסיסמה,
   וה-Worker מאמת אותה מול `PASSWORD_HASH` (secret בצד שרת, לא נגיש
   לדפדפן) **לפני** שהוא נוגע ב-repo. זו הגנה אמיתית - גם מי שקורא את
   קוד ה-JS ומנסה לקרוא ישירות ל-Worker בלי הסיסמה הנכונה, יקבל 401.

## הקמה שלב-אחר-שלב

### 1. יצירת ה-repo
צרו/ודאו repo **ציבורי** בשם `Cinema_find` תחת המשתמש `ronenz90`, עם כל
הקבצים (`.github/`, `docs/`, `worker/`, `scraper/`, `config/`, `state/`).

### 2. הפעלת GitHub Pages
Settings > Pages > Source: "Deploy from a branch" > Branch: `main`,
תיקייה: `/docs`. האתר יהיה זמין ב- `https://ronenz90.github.io/Cinema_find/`

### 3. יצירת טוקן GitHub מוגבל (עבור ה-Worker)
1. https://github.com/settings/personal-access-tokens/new (Fine-grained token)
2. **Repository access**: "Only select repositories" > `Cinema_find` בלבד.
3. **Permissions** > Repository permissions > **Contents**: "Read and write".
   שאר ההרשאות: No access (עקרון ההרשאה המינימלית).
4. צרו והעתיקו את הטוקן (מוצג פעם אחת בלבד).

### 4. פריסת ה-Cloudflare Worker (חד-פעמי - אחר כך הכל אוטומטי)
כל עדכון עתידי ל-`worker/index.js` ייפרס לבד ברגע שתשמרו אותו ב-GitHub
(גם מהאפליקציה או מהאתר בנייד).

**א. חשבון Cloudflare + פרטים חד-פעמיים**
1. הרשמו בחינם ב- https://dash.cloudflare.com
2. מצאו את ה-**Account ID** (מופיע בצד ימין של דף הבית של הדשבורד).
3. צרו API Token: Profile > API Tokens > Create Token > תבנית "Edit
   Cloudflare Workers". העתיקו אותו (מוצג פעם אחת).

**ב. הוספת 4 secrets ב-GitHub** (Settings > Secrets and variables > Actions):
- `CLOUDFLARE_API_TOKEN` - הטוקן מהשלב הקודם
- `CLOUDFLARE_ACCOUNT_ID` - ה-Account ID
- `WORKER_GITHUB_PAT` - הטוקן שיצרתם בשלב 3 למעלה
- `WORKER_PASSWORD_HASH` - ה-hash של סיסמת הכניסה (אותו ערך שכבר משולב
  ב-`docs/app.js` תחת `PASSWORD_HASH_SHA256`)

**ג. הרצה ראשונה**: Actions > Deploy Cloudflare Worker > Run workflow.
לאחר סיום מוצלח, ב-Cloudflare Dashboard > Workers & Pages >
`cinema-find-api` תמצאו את כתובת ה-Worker (`https://cinema-find-
api.<your-subdomain>.workers.dev`).

### 5. חיבור האתר ל-Worker
ב-`docs/app.js`, ודאו שהשורה מעודכנת עם כתובת ה-Worker האמיתית שלכם:
```javascript
const WORKER_URL = "https://cinema-find-api.<your-subdomain>.workers.dev";
```

### 6. הגדרת Secrets לשליחת מיילים (Gmail SMTP - חינמי, ל-GitHub Actions)
1. הפעילו אימות דו-שלבי בחשבון ה-Gmail ששולח.
2. צרו App Password ב- https://myaccount.google.com/apppasswords
3. ב-repo: Settings > Secrets and variables > Actions, הוסיפו:
   - `GMAIL_ADDRESS` - כתובת ה-Gmail ששולחת
   - `GMAIL_APP_PASSWORD` - ה-App Password (16 תווים, בלי רווחים)
   - `ALERT_RECIPIENT_EMAIL` - כתובת ברירת מחדל

### 7. בדיקה
- **בדיקת מייל**: Actions > Test email > Run workflow (בודק שה-Gmail
  secrets תקינים, בלי צורך במעקב אמיתי או שינוי זמנים).
- **הוספת מעקב**: גשו לאתר, הכניסו סיסמה, הוסיפו מעקב - אמור להתווסף
  מיידית, גם ללשונית "מעקבים פתוחים" וגם ל-`config/watches.json`.
- **בדיקת הסקרייפר**: Actions > Check Cinema City showtimes > Run
  workflow. בתום הריצה, גלילה למטה בעמוד ה-run מציגה artifact בשם
  `debug-screenshots` - שימושי לאבחון אם משהו משתבש.
- **רענון רשימת סרטים**: Actions > Index movie list > Run workflow.

## איך זה עובד בפועל

1. **הוספת/עריכת/מחיקת מעקב**: הטופס (או כפתורי "ערוך"/"מחק") שולחים
   בקשה ישירה ל-Worker, כולל הסיסמה. ה-Worker מאמת אותה, קורא את
   `config/watches.json` הנוכחי דרך GitHub API, מעדכן, וכותב בחזרה -
   הכל תוך שנייה או שתיים. גם טעינת הלשונית "מעקבים פתוחים" עוברת דרך
   ה-Worker (GET), כדי לקבל תמיד את הנתון העדכני ביותר בלי מטמון.
2. **בדיקה תקופתית**: `check-showtimes.yml` רץ כל 3 שעות, מריץ
   `scraper/cinema_watcher.py` (Playwright headless). עבור כל מעקב,
   הסקריפט בוחר קולנוע/אולם/סרט **ישירות דרך ה-view model הפנימי של
   האתר** (לא לחיצות DOM - זה התברר כלא אמין), קורא את התאריכים/שעות
   הזמינים, משווה ל-`state/state.json`, ומסנן לפי טווח השעות שהוגדר. אם
   יש שינוי רלוונטי - נשלח מייל נפרד לכתובת של אותו מעקב (או לברירת
   המחדל). הריצה הראשונה לכל מעקב חדש רק קובעת "נקודת ייחוס" - לא
   שולחת מייל.
3. **אינדוקס לילי**: `index-movies.yml` רץ כל לילה, שולף את רשימת "עכשיו
   בקולנוע" (HTML רגיל, בלי Playwright) וכותב ל-`docs/movies.json`.
4. **פריסת Worker**: `deploy-worker.yml` רץ בכל push שמשנה קבצים תחת
   `worker/`, ומפרסם אוטומטית לענן דרך Wrangler.

### קבצים שאינם בשימוש יותר (אופציונלי למחוק)
`process-watch-request.yml` ו-`scraper/parse_issue.py` היו הדרך הישנה
(מבוססת GitHub issues) לפני שהוספנו את ה-Worker. לא פעילים בזרימה
הרגילה - אפשר להשאיר (לא מזיקים) או למחוק לניקיון.

## מגבלות ידועות

- **תזמון**: cron ב-GitHub Actions הוא "best effort" ויכול להתעכב בכמה
  דקות. אם ה-repo לא פעיל 60 יום, GitHub משבית לוחות זמנים (Run
  workflow ידני מפעיל מחדש).
- **הסלקטורים/מבנה הנתונים**: מבוססים על מבנה האתר האמיתי נכון לעכשיו.
  שינוי עתידי באתר עשוי לדרוש עדכון ב-`scraper/cinema_watcher.py` -
  ה-artifact `debug-screenshots` (בכל ריצה) עוזר לאבחן במהירות.
- **עריכה חלקית**: דרך "מעקבים פתוחים" אפשר לערוך רק טווח שעות ומייל -
  לא את הסרט/סניף/אולם עצמם (למקרה כזה: מחקו והוסיפו מחדש).
- **טווח שעות**: ברמת דיוק של שעה עגולה (לא דקות), תומך גם ב"מעטפת"
  חצות (למשל 22 עד 2), אך לא בשני טווחים נפרדים לאותו מעקב.
- **סיסמה בזיכרון הדפדפן**: לאחר כניסה, הסיסמה נשמרת ב-sessionStorage
  (רק בטאב הנוכחי, נמחקת בסגירתו) כדי לשלוח אותה ל-Worker בכל פעולה.
  סביר לכלי אישי קטן כזה, אך שווה לדעת.

## מבנה הקבצים

```
.github/workflows/
  check-showtimes.yml         # cron - בדיקה + מיילים + צילומי מסך לדיבוג
  index-movies.yml            # cron לילי - מרענן את רשימת הסרטים
  deploy-worker.yml            # פריסת ה-Worker אוטומטית בכל שינוי
  test-email.yml                # ריצה ידנית - בדיקת שליחת מייל
  process-watch-request.yml     # legacy - לא בשימוש יותר, אפשר למחוק
docs/
  index.html                  # האתר הסטטי (GitHub Pages)
  app.js                       # הגנת סיסמה, טפסים, קריאות ל-Worker, autocomplete
  style.css
  movies.json                  # נכתב אוטומטית ע"י index-movies.yml
worker/
  index.js                     # Cloudflare Worker - מאמת סיסמה + כותב/קורא ל-repo
  wrangler.toml                  # קונפיגורציית פריסה
scraper/
  cinema_watcher.py             # הגרידה בפועל (VM-driven) + שליחת מיילים
  index_movies.py               # אינדוקס רשימת הסרטים
  test_email.py                  # שליחת מייל בדיקה
  parse_issue.py                  # legacy - לא בשימוש יותר, אפשר למחוק
  requirements.txt
config/
  watches.json                   # רשימת המעקבים הפעילים
state/
  state.json                      # תוצאות הריצה הקודמת (להשוואה)
```
