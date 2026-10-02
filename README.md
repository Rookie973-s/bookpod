# BookPod — Django + DRF + MySQL

HTML/CSS/JS frontend → REST API → Django/DRF → MySQL, with Django Admin as the control panel.

## 1. Set up

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt                      # mysqlclient needs MySQL client libs (see below)
cp .env.example .env                                 # then edit it
```

Create the database (MySQL 8):

```sql
CREATE DATABASE bookpod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'bookpod'@'localhost' IDENTIFIED BY 'a-strong-password';
GRANT ALL ON bookpod.* TO 'bookpod'@'localhost';
```

Put the same values in `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, …), then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_library        # optional: default topics + the 8 sample books/3 collections
python manage.py runserver
```

* Site: http://localhost:8000/  ·  Admin: http://localhost:8000/admin/  ·  API root: http://localhost:8000/api/books/

`mysqlclient` on Windows usually installs from a wheel. On Ubuntu: `sudo apt install default-libmysqlclient-dev build-essential pkg-config`.

## 2. Google Sign-In

1. Google Cloud Console → *APIs & Services* → *Credentials* → **Create OAuth client ID** → *Web application*.
2. Under **Authorized JavaScript origins** add `http://localhost:8000` (and your real https origin in production).
3. Copy the client ID into `.env` as `GOOGLE_CLIENT_ID`, restart the server.

The browser only sends Google's signed ID token to `POST /api/auth/google/`. Django verifies signature, expiry,
audience (your client ID), issuer and `email_verified`, then creates/finds the user and starts a normal Django
session. Without `GOOGLE_CLIENT_ID` the Sign in dialog tells you it isn't configured — it never fakes a login.

## 3. Managing the library (Django Admin)

* **Categories / topics** — name, colour, icon, order. They drive the Topics filters and the home-page tiles.
* **Books** — cover image upload, optional PDF/EPUB file, page count, preview snippet (shown on the open-book
  spread), table of contents (one chapter per line), featured and published switches, bulk publish/unpublish actions.
* **Collections** — pick books inline and set their order.
* **Shelf entries** — each reader's books and progress (for support/inspection).

Uploads go to `media/` (served by Django when `DJANGO_DEBUG=True`).

## 4. API

| Endpoint | Notes |
|---|---|
| `GET /api/books/` | `?category=<slug>` `?collection=<slug>` `?q=` `?featured=true` `?ordering=title\|-title\|newest` `?page=` `?page_size=` |
| `GET /api/books/<slug-or-id>/` | detail + related books + your own shelf entry (if signed in) |
| `GET /api/categories/` | topics with published-book counts |
| `GET /api/collections/` , `/api/collections/<slug>/` | collections with their books |
| `GET /api/my-books/?status=reading\|finished` | signed-in user's shelf only |
| `POST /api/my-books/` | `{"book_slug": "..."}` (idempotent) |
| `PATCH /api/my-books/<id>/` | `{"current_page": 43}` or `{"status": "finished"}` / `"reading"` (read again) |
| `DELETE /api/my-books/<id>/` | remove from shelf |
| `GET /api/auth/me/`, `POST /api/auth/google/`, `POST /api/auth/logout/`, `GET /api/auth/config/` | authentication |

Progress is stored as `current_page`; the percentage is always computed as `current_page / book.page_count × 100`
on the server. Reaching the last page (or pressing *Mark as finished*) sets the status to Finished and moves the
book to the Finished shelf. Every shelf query is filtered by `request.user`, so entries of other users return 404.

## 5. Tests

```bash
DB_ENGINE=sqlite python manage.py test library     # no MySQL needed for the test run
```

## 6. Production notes

Set `DJANGO_DEBUG=False`, a long `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
(e.g. `https://books.example.com`), run `python manage.py collectstatic`, and serve with gunicorn/uvicorn
behind HTTPS. Static files are handled by WhiteNoise; serve `MEDIA_ROOT` (uploads) from nginx or object storage.
