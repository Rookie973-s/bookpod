from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Book, Category, Collection, CollectionBook, UserBook

User = get_user_model()


def make_book(title, category, pages=100, **kw):
    return Book.objects.create(title=title, author="A. Writer", description="Desc " + title,
                               category=category, page_count=pages, **kw)


class BaseCase(TestCase):
    def setUp(self):
        self.prog = Category.objects.create(name="Programming", color="#2F4858", icon="code")
        self.fic = Category.objects.create(name="Fiction", color="#7B3F61", icon="fiction")
        self.py = make_book("Python 101", self.prog, 100)
        self.js = make_book("JS Basics", self.prog, 50)
        self.novel = make_book("A Novel", self.fic, 300, is_featured=True)
        self.hidden = make_book("Secret Draft", self.prog, 10, is_published=False)
        self.client = APIClient(enforce_csrf_checks=False)


class CatalogApiTests(BaseCase):
    def test_list_returns_only_published(self):
        r = self.client.get("/api/books/")
        self.assertEqual(r.status_code, 200)
        titles = {b["title"] for b in r.json()["results"]}
        self.assertEqual(titles, {"Python 101", "JS Basics", "A Novel"})
        self.assertEqual(r.json()["count"], 3)

    def test_filter_by_category_slug(self):
        r = self.client.get("/api/books/?category=programming")
        self.assertEqual({b["title"] for b in r.json()["results"]}, {"Python 101", "JS Basics"})

    def test_search_and_featured(self):
        self.assertEqual(self.client.get("/api/books/?q=novel").json()["count"], 1)
        self.assertEqual(self.client.get("/api/books/?featured=true").json()["results"][0]["title"], "A Novel")

    def test_detail_by_slug_and_id_with_related(self):
        r = self.client.get(f"/api/books/{self.py.slug}/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["page_count"], 100)
        self.assertEqual(data["related"][0]["title"], "JS Basics")   # same category first
        self.assertNotIn(self.py.slug, [b["slug"] for b in data["related"]])
        self.assertNotIn("Secret Draft", [b["title"] for b in data["related"]])
        self.assertIsNone(data["my_entry"])
        self.assertEqual(self.client.get(f"/api/books/{self.py.pk}/").json()["slug"], self.py.slug)

    def test_unpublished_detail_is_404(self):
        self.assertEqual(self.client.get(f"/api/books/{self.hidden.slug}/").status_code, 404)

    def test_categories_have_counts(self):
        data = {c["slug"]: c for c in self.client.get("/api/categories/").json()}
        self.assertEqual(data["programming"]["book_count"], 2)   # unpublished not counted
        self.assertEqual(data["fiction"]["book_count"], 1)

    def test_collection_orders_books_and_hides_unpublished(self):
        coll = Collection.objects.create(title="Starter")
        CollectionBook.objects.create(collection=coll, book=self.js, order=0)
        CollectionBook.objects.create(collection=coll, book=self.py, order=1)
        CollectionBook.objects.create(collection=coll, book=self.hidden, order=2)
        data = self.client.get("/api/collections/starter/").json()
        self.assertEqual([b["title"] for b in data["books"]], ["JS Basics", "Python 101"])
        self.assertEqual(data["book_count"], 2)
        filtered = self.client.get("/api/books/?collection=starter").json()["results"]
        self.assertEqual([b["title"] for b in filtered], ["JS Basics", "Python 101"])

    def test_cover_upload_is_served_through_api(self):
        png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
               b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")
        with self.settings(MEDIA_ROOT="/tmp/bookpod-test-media"):
            self.py.cover.save("c.png", SimpleUploadedFile("c.png", png), save=True)
            url = self.client.get(f"/api/books/{self.py.slug}/").json()["cover"]
        self.assertTrue(url.endswith(".png") and "/media/covers/" in url)


class ShelfApiTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.alice = User.objects.create_user("alice", "alice@example.com")
        self.bob = User.objects.create_user("bob", "bob@example.com")

    def test_requires_login(self):
        self.assertIn(self.client.get("/api/my-books/").status_code, (401, 403))
        self.assertIn(self.client.post("/api/my-books/", {"book_slug": self.py.slug}).status_code, (401, 403))

    def test_add_progress_and_percentage(self):
        self.client.force_authenticate(self.alice)
        r = self.client.post("/api/my-books/", {"book_slug": self.py.slug}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()["status"], r.json()["percentage"]), ("reading", 0))
        entry_id = r.json()["id"]
        r = self.client.patch(f"/api/my-books/{entry_id}/", {"current_page": 43}, format="json")
        self.assertEqual((r.json()["current_page"], r.json()["total_pages"], r.json()["percentage"]), (43, 100, 43))
        # adding the same book again is idempotent
        again = self.client.post("/api/my-books/", {"book_id": self.py.pk}, format="json")
        self.assertEqual((again.status_code, again.json()["id"]), (200, entry_id))
        self.assertEqual(UserBook.objects.filter(user=self.alice).count(), 1)

    def test_last_page_or_finish_moves_to_finished(self):
        self.client.force_authenticate(self.alice)
        e = self.client.post("/api/my-books/", {"book_slug": self.py.slug, "current_page": 60}, format="json").json()
        r = self.client.patch(f"/api/my-books/{e['id']}/", {"current_page": 100}, format="json").json()
        self.assertEqual((r["status"], r["percentage"]), ("finished", 100))
        self.assertIsNotNone(r["date_finished"])
        e2 = self.client.post("/api/my-books/", {"book_slug": self.js.slug}, format="json").json()
        r2 = self.client.patch(f"/api/my-books/{e2['id']}/", {"status": "finished"}, format="json").json()
        self.assertEqual((r2["status"], r2["current_page"], r2["total_pages"]), ("finished", 50, 50))
        listing = lambda s: self.client.get(f"/api/my-books/?status={s}").json()
        self.assertEqual(len(listing("finished")), 2)
        self.assertEqual(len(listing("reading")), 0)

    def test_read_again_resets(self):
        self.client.force_authenticate(self.alice)
        e = self.client.post("/api/my-books/", {"book_slug": self.js.slug, "status": "finished"}, format="json").json()
        r = self.client.patch(f"/api/my-books/{e['id']}/", {"status": "reading"}, format="json").json()
        self.assertEqual((r["status"], r["current_page"], r["date_finished"]), ("reading", 0, None))

    def test_page_beyond_total_rejected(self):
        self.client.force_authenticate(self.alice)
        e = self.client.post("/api/my-books/", {"book_slug": self.js.slug}, format="json").json()
        r = self.client.patch(f"/api/my-books/{e['id']}/", {"current_page": 999}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_users_cannot_see_or_change_each_others_shelves(self):
        self.client.force_authenticate(self.alice)
        e = self.client.post("/api/my-books/", {"book_slug": self.py.slug, "current_page": 10}, format="json").json()
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get("/api/my-books/").json(), [])
        self.assertEqual(self.client.get(f"/api/my-books/{e['id']}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/my-books/{e['id']}/", {"current_page": 99}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/my-books/{e['id']}/").status_code, 404)
        self.assertEqual(UserBook.objects.get(pk=e["id"]).current_page, 10)

    def test_detail_exposes_only_my_entry(self):
        self.client.force_authenticate(self.alice)
        self.client.post("/api/my-books/", {"book_slug": self.py.slug, "current_page": 25}, format="json")
        self.assertEqual(self.client.get(f"/api/books/{self.py.slug}/").json()["my_entry"]["percentage"], 25)
        self.client.force_authenticate(self.bob)
        self.assertIsNone(self.client.get(f"/api/books/{self.py.slug}/").json()["my_entry"])

    def test_delete_removes_from_shelf(self):
        self.client.force_authenticate(self.alice)
        e = self.client.post("/api/my-books/", {"book_slug": self.py.slug}, format="json").json()
        self.assertEqual(self.client.delete(f"/api/my-books/{e['id']}/").status_code, 204)
        self.assertEqual(UserBook.objects.count(), 0)


@override_settings(GOOGLE_CLIENT_ID="test-client-id.apps.googleusercontent.com")
class GoogleAuthTests(BaseCase):
    CLAIMS = {"iss": "https://accounts.google.com", "sub": "1234567890", "email": "Reader@Example.com",
              "email_verified": True, "given_name": "Ada", "family_name": "Reader", "picture": "https://x/y.png"}

    def post(self, claims=None, side_effect=None, credential="tok"):
        with mock.patch("library.auth_views.verify_google_credential", return_value=claims, side_effect=side_effect):
            return self.client.post("/api/auth/google/", {"credential": credential}, format="json")

    def test_valid_token_creates_user_and_session(self):
        r = self.post(dict(self.CLAIMS))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["email"], "reader@example.com")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(self.client.get("/api/auth/me/").json()["user"]["email"], "reader@example.com")
        # second sign-in reuses the same account
        self.client.post("/api/auth/logout/")
        self.assertIsNone(self.client.get("/api/auth/me/").json()["user"])
        self.post(dict(self.CLAIMS))
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_token_rejected(self):
        r = self.post(side_effect=ValueError("bad"))
        self.assertEqual(r.status_code, 401)
        self.assertEqual(User.objects.count(), 0)

    def test_unverified_email_rejected(self):
        r = self.post(dict(self.CLAIMS, email_verified=False))
        self.assertEqual(r.status_code, 401)

    def test_wrong_issuer_rejected(self):
        self.assertEqual(self.post(dict(self.CLAIMS, iss="https://evil.example")).status_code, 401)

    def test_missing_credential(self):
        r = self.client.post("/api/auth/google/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_csrf_enforced_on_login(self):
        strict = APIClient(enforce_csrf_checks=True)
        with mock.patch("library.auth_views.verify_google_credential", return_value=dict(self.CLAIMS)):
            r = strict.post("/api/auth/google/", {"credential": "tok"}, format="json")
        self.assertEqual(r.status_code, 403)

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_unconfigured_returns_503(self):
        self.assertEqual(self.client.post("/api/auth/google/", {"credential": "x"}, format="json").status_code, 503)
        self.assertIsNone(self.client.get("/api/auth/config/").json()["google_client_id"])


class PageTests(BaseCase):
    def test_pages_render(self):
        for url in ["/", "/collections/", "/topics/", "/my-shelf/", f"/book/{self.py.slug}/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertNotContains(r, "Bookmarks")
            self.assertNotContains(r, "Publish")
        self.assertEqual(self.client.get(f"/book/{self.hidden.slug}/").status_code, 404)
        self.assertEqual(self.client.get("/book/nope/").status_code, 404)

    def test_seed_command_is_idempotent(self):
        from django.core.management import call_command
        with self.settings(MEDIA_ROOT="/tmp/bookpod-test-media"):
            call_command("seed_library", verbosity=0)
            call_command("seed_library", verbosity=0)
        self.assertEqual(Book.objects.filter(slug="python-fundamentals").count(), 1)
        self.assertEqual(Collection.objects.count(), 3)
        self.assertTrue(Book.objects.get(slug="python-fundamentals").cover)
