# Survey System (Судалгааны систем)

Flask application for collecting employer and intern-student satisfaction surveys, with a secured
admin area for reviewing, filtering and exporting the results.

## What's inside

| Area | Implementation |
|---|---|
| **Architecture** | Application factory (`app/__init__.py`), blueprints (`main`, `surveys`, `auth`, `admin`), config classes driven by environment variables, services layer for queries/stats/export |
| **Validation** | Flask-WTF/WTForms with Mongolian messages; whitelisted choices, 1–5 ratings, length/format checks, honeypot field |
| **Database** | Flask-SQLAlchemy + Flask-Migrate (Alembic). Survey tables are unchanged from the prototype |
| **Security** | CSRF on every POST, scrypt password hashing, roles (`admin` / `analyst`), session hardening, login rate limiting, strict CSP + security headers, open-redirect protection, spreadsheet-formula-injection protection in exports |
| **Admin** | **Edit both surveys' questions from the browser**, dashboard (totals, 7/30-day counts, average scores, answer distributions, 14-day timeline), searchable/filterable/sortable/paginated lists, response detail, CSV + Excel export that honours the active filters |
| **UI** | Dependency-free responsive CSS, mobile nav, big tap-target rating scale, live progress bar, loading spinners, dismissible alert banners, inline field errors, error pages |
| **Production** | `.env` configuration, Gunicorn config, Dockerfile + compose file, `/healthz` endpoint |

## Project layout

```
wsgi.py                  entry point (gunicorn wsgi:app)
app/
  __init__.py            create_app(): config, extensions, blueprints, error pages
  config.py              Development / Production / Testing configuration
  extensions.py          db, migrate, csrf, login, limiter, oauth
  models.py              User, EmployerSurvey, StudentSurvey, AdminDataEntry, SurveyConfig
  questions.py           DEFAULT survey definitions (admins' edits are layered on top, see below)
  forms.py               WTForms (survey forms are built per request from the current questions)
  security.py            redirect + password-policy helpers
  blueprints/            main.py, surveys.py, auth.py, admin.py
  services/              queries.py (search/filter), stats.py (dashboard), export.py (CSV/XLSX),
                         survey_config.py (question-editing rules, no DB), survey_store.py (loads/saves them)
  templates/ static/     UI
migrations/              Alembic environment + versions/
tests/                   pytest suite
Dockerfile, docker-compose.yml, gunicorn.conf.py, docker-entrypoint.sh
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env                                   # Windows: copy .env.example .env
#   APP_ENV=development works without a SECRET_KEY; production requires one.

flask --app wsgi db upgrade                            # creates instance/surveys.db
flask --app wsgi create-user you@example.com --role admin     # prompts for a password (min. 12 chars)
flask --app wsgi run --debug                           # http://127.0.0.1:5000
```

### Keep the data from the old prototype

The old `instance/surveys.db` already has the three original tables, so tell Alembic they exist
instead of re-creating them, then apply the new migration (adds `users` + indexes):

```bash
cp instance/surveys.db instance/surveys.db.bak
flask --app wsgi db stamp 0001_initial_schema
flask --app wsgi db upgrade
```

## Users and roles

| Role | Can do |
|---|---|
| `admin` | Everything: dashboard, lists, export, **delete responses**, **manage JSON data** |
| `analyst` | Read-only: dashboard, search/filter, detail, export |

```bash
flask --app wsgi create-user analyst@example.com --role analyst --name "Dulmaa"
flask --app wsgi set-password someone@example.com
flask --app wsgi deactivate-user someone@example.com
flask --app wsgi list-users
```

**Google sign-in (optional).** Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and add
`https://YOUR-DOMAIN/auth/google/callback` as an authorised redirect URI. Addresses listed in
`ADMIN_EMAILS` get an admin account on first sign-in; anyone else must already have an active
account. Only Google accounts with a *verified* email are accepted. The login page shows the Google
button only when credentials are configured.

## Configuration (`.env`)

See `.env.example` for every variable. The important ones:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `production` (default), `testing` |
| `SECRET_KEY` | **Required in production**, ≥ 32 chars; the app refuses to start without it |
| `DATABASE_URL` | Default SQLite in `instance/`. PostgreSQL: `postgresql://…` + `pip install "psycopg[binary]"` |
| `SESSION_COOKIE_SECURE` | Keep `true` behind HTTPS. Only set `false` to test over `http://localhost` |
| `TRUSTED_PROXY_COUNT` | `1` behind nginx so client IPs, https and the Google redirect URI are right |
| `RATELIMIT_STORAGE_URI` | `memory://` is per-process; use Redis (`redis://…`, `pip install redis`) with several workers |
| `SURVEY_RATE_LIMIT` | Submissions per IP. A school lab shares one IP, so keep it generous |
| `APP_TIMEZONE` | Display/export timezone (data is stored in UTC) |

## Changing the surveys

### From the browser (admins)

**Админ самбар → Асуулга засах** (admin role only). For the employer and the student survey you can:

* reword any rating question, **add** new ones, **reorder** them, and **hide / show** them;
* add, rename, reorder or hide a whole group (section) of rating questions, and edit its scale hint;
* change the survey title;
* reword the fixed questions (company name, phone, ...) and edit the choices of the dropdown ones
  (aimag/city, legal form, employee count, ...);
* **reset** a survey to the defaults in `questions.py`.

Changes are saved in the database and apply to the public form immediately. Things worth knowing:

* **Why the database and not `questions.py`?** On Render the file system is ephemeral and the app is
  rebuilt from GitHub on every deploy, so a file edited at runtime would silently vanish. Edits are
  stored in the `survey_configs` table (Neon) instead.
* **Hiding never deletes data.** Answers to a hidden question stay in the database and reappear if it is
  shown again. Questions are never hard-deleted from the editor.
* **New questions are 1-5 ratings.** Their answers are stored in the `extra_answers` JSON column of the
  response table (no schema change per question) and appear in the dashboard, response detail,
  by-major page and CSV/Excel export like the original ones.
* **Changing what a question means** makes old and new answers incomparable. Add a new question instead.
* **Dropdown choices:** old responses keep the text they were saved with (and stay filterable in the admin
  list). The answer the by-major page counts as positive (e.g. "Тийм") cannot be removed, and each choice
  must fit the database column (e.g. gender is 20 characters).
* Question numbers such as "2.1.3." are part of the question text; renumber them yourself when you reorder.
* Once you edit the rating questions of a survey, the database copy wins for that survey: questions you
  later add to `questions.py` do not appear there until you reset it.
* A respondent who opened the form before an admin added a question will be asked to answer it on submit.

### In code (developers)

`app/questions.py` holds the **defaults**: what a fresh install shows and what *reset* restores.

* **Add a rating question in code:** append a `Question(field, label, short)` to a group. The `field` must
  be a column on the model (e.g. the unused `soft_1…7`, `tech_1…5`, `quality_1…2` columns on
  `StudentSurvey`), otherwise add the column to `app/models.py` and run
  `flask --app wsgi db migrate -m "add question"` then `flask --app wsgi db upgrade`.
  (Questions added from the browser need none of this.)
* **Change default answer choices:** edit the tuples at the top of the file.

## Results by major (мэргэжил)

`/admin/majors` (button **Мэргэжлээр харах** on the dashboard) shows both surveys grouped by major:

* **Student survey** - the free-text `major` answer. **Employer survey** - the new required question
  *"1.12 Танай байгууллагад ямар мэргэжлийн суралцагчид дадлага хийж байна вэ?"* (`intern_majors`,
  several majors separated by comma or new line).
* Spellings are grouped case- and whitespace-insensitively; different wording ("Гагнуур" vs
  "Гагнуурчин") stays separate, so keep the typed names consistent.
* An employer that lists several majors is counted under each of them. Its 1-5 ratings describe its
  graduates as a whole (the survey does not ask per major), so every listed major shares that rating.
* Employer rows saved before the question existed have no major; the page reports how many were left out.
* Each major links to the filtered response list (`?major=...`), and both tables export to CSV/Excel.

Existing databases need the new column: `flask --app wsgi db upgrade` (Docker applies it on start).
The grouping code lives in `app/services/majors.py` and has no Flask/database imports.

## Tests

```bash
pytest
```

Covers validation, CSRF, login/RBAC, the question editor (`tests/test_survey_config.py` for the rules,
`tests/test_questions_admin.py` end to end), open-redirect protection, search/filter/pagination, exports
(including formula-injection), JSON-data management, and that the migrations build exactly the schema
the models describe.

## Deployment

### Docker (simplest)

```bash
cp .env.example .env        # set APP_ENV=production, SECRET_KEY, TRUSTED_PROXY_COUNT=1, ...
docker compose up -d --build
docker compose exec web flask create-user you@example.com --role admin
```

The container applies migrations on start (this is how a deploy to Render + Neon creates the
`survey_configs` table and the `extra_answers` columns), runs Gunicorn as a non-root user, and exposes a health
check at `/healthz`. The SQLite file lives in the `survey_data` volume.

### Without Docker

```bash
pip install -r requirements.txt
export APP_ENV=production SECRET_KEY=... 
flask --app wsgi db upgrade
gunicorn -c gunicorn.conf.py wsgi:app
```

Example systemd unit (`/etc/systemd/system/survey.service`):

```ini
[Unit]
Description=Survey system
After=network.target

[Service]
User=survey
WorkingDirectory=/srv/survey
EnvironmentFile=/srv/survey/.env
ExecStart=/srv/survey/.venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### nginx in front (TLS)

```nginx
server {
    listen 443 ssl;
    server_name survey.example.mn;
    # ssl_certificate / ssl_certificate_key ...
    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Set `TRUSTED_PROXY_COUNT=1`. Static files are served by Gunicorn, which is fine at this scale.

### Operations checklist

* **Backups:** the database holds respondents' names, phones and emails. SQLite runs in WAL mode, so
  don't just copy the file while the app is running; use
  `sqlite3 instance/surveys.db ".backup /backups/surveys-$(date +%F).db"`.
* **Schema changes:** edit `models.py` → `flask db migrate -m "..."` → review the generated file → `flask db upgrade`.
* **Lock dependencies:** after a successful install run `pip freeze > requirements.lock` and build from it.
* **Multiple replicas:** run migrations once (`RUN_MIGRATIONS=0` on all but one) and use Redis for rate limits.

## Security notes

* All POST routes are CSRF-protected (logout and delete are POST-only). Sessions are cookie-based:
  `HttpOnly`, `SameSite=Lax`, `Secure` in production, 2-hour lifetime, cleared and re-issued on login.
* Passwords use Werkzeug's salted scrypt; the login form returns one generic error for unknown email,
  wrong password and disabled account, and burns equal time for unknown emails.
* CSP is `default-src 'self'` with no inline scripts/styles - keep it that way (use `static/js/app.js`).
* Not included (reasonable next steps): account lockout / 2FA for admins, an audit-log table
  (actions are currently written to the application log), and a privacy/consent notice on the
  survey pages, which you should add if respondents' contact details are collected.
