import json
import re

from django.test import TestCase, override_settings

from .models import Book, Category


@override_settings(SITE_URL="https://bookpod.example.com")
class SeoTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Programming & Technology", description="Code and ML.")
        self.book = Book.objects.create(
            title="Python <Fundamentals> & More", author="Richfield A.", category=self.cat, page_count=214,
            description="A grounded, practical introduction to Python for learners with no prior background, "
                        "covering variables through file handling and small projects.",
            isbn="9781234567890", publisher="BookPod Press",
        )
        self.hidden = Book.objects.create(title="Secret", author="X", category=self.cat, page_count=5,
                                          description="d", is_published=False)

    def head(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_home_has_complete_meta_and_jsonld(self):
        html = self.head("/")
        self.assertIn('<link rel="canonical" href="https://bookpod.example.com/">', html)
        self.assertIn('property="og:image" content="https://bookpod.example.com/static/images/og-default.jpg"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn('property="og:type" content="website"', html)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        types = {n["@type"] for n in data["@graph"]}
        self.assertEqual(types, {"Organization", "WebSite"})
        self.assertEqual(html.count("<title>"), 1)

    def test_book_page_meta_is_specific_and_escaped(self):
        html = self.head(f"/book/{self.book.slug}/")
        self.assertIn("Python &lt;Fundamentals&gt; &amp; More by Richfield A. | BookPod", html)
        self.assertNotIn("<Fundamentals>", html.split("</head>")[0].replace("&lt;Fundamentals&gt;", ""))
        self.assertIn(f'<link rel="canonical" href="https://bookpod.example.com/book/{self.book.slug}/">', html)
        self.assertIn('property="og:type" content="book"', html)
        self.assertIn('property="book:isbn" content="9781234567890"', html)
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("<Fundamentals>", ld)               # cannot break out of the script tag
        graph = json.loads(ld)["@graph"]
        book = next(n for n in graph if n["@type"] == "Book")
        self.assertEqual((book["numberOfPages"], book["isbn"], book["author"]["name"]), (214, "9781234567890", "Richfield A."))
        self.assertTrue(any(n["@type"] == "BreadcrumbList" for n in graph))

    def test_book_page_has_server_rendered_content(self):
        self.book.table_of_contents = "Intro\nVariables"
        self.book.save()
        html = self.head(f"/book/{self.book.slug}/")
        self.assertIn("Programming &amp; Technology · Book", html)
        self.assertIn("<li><span class=\"n\">2</span>Variables</li>", html)

    def test_short_description_gets_padded_for_search_snippets(self):
        b = Book.objects.create(title="Tiny", author="A", category=self.cat, page_count=10, description="Short.")
        self.assertIn("A 10-page book in Programming &amp; Technology on BookPod.", self.head(f"/book/{b.slug}/"))

    def test_noindex_for_private_and_search_pages(self):
        self.assertIn('content="noindex, follow"', self.head("/my-shelf/"))
        self.assertIn('content="noindex, follow"', self.head("/topics/?q=python"))
        self.assertIn("index, follow", self.head("/topics/"))

    def test_category_page_gets_own_title_and_canonical(self):
        html = self.head(f"/topics/?category={self.cat.slug}")
        self.assertIn("Programming &amp; Technology — Books &amp; Study Materials | BookPod", html)
        self.assertIn(f'href="https://bookpod.example.com/topics/?category={self.cat.slug}"', html)

    def test_robots_txt(self):
        r = self.client.get("/robots.txt")
        text = r.content.decode()
        self.assertEqual(r["Content-Type"].split(";")[0], "text/plain")
        self.assertIn("Sitemap: https://bookpod.example.com/sitemap.xml", text)
        self.assertIn("Disallow: /admin/", text)
        self.assertNotIn("Disallow: /api", text)             # Google needs the API to render the pages

    def test_sitemap_lists_published_books_only(self):
        r = self.client.get("/sitemap.xml")
        xml = r.content.decode()
        self.assertEqual(r["Content-Type"].split(";")[0], "application/xml")
        self.assertIn(f"https://bookpod.example.com/book/{self.book.slug}/", xml)
        self.assertNotIn(self.hidden.slug, xml)
        self.assertIn("<loc>https://bookpod.example.com/topics/?category=", xml.replace("&amp;", "&"))
        import xml.dom.minidom
        xml.dom.minidom.parseString(r.content)                # well-formed XML

    def test_api_and_admin_are_noindex(self):
        self.assertEqual(self.client.get("/api/books/")["X-Robots-Tag"], "noindex")
        self.assertIn("noindex", self.client.get("/admin/login/")["X-Robots-Tag"])
        self.assertNotIn("X-Robots-Tag", self.client.get("/"))

    def test_favicon_redirects(self):
        r = self.client.get("/favicon.ico")
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r["Location"].endswith("favicon.ico"))

    def test_verification_tags_only_when_configured(self):
        self.assertNotIn("google-site-verification", self.head("/"))
        with override_settings(GOOGLE_SITE_VERIFICATION="abc123", BING_SITE_VERIFICATION="def456"):
            html = self.head("/")
            self.assertIn('name="google-site-verification" content="abc123"', html)
            self.assertIn('name="msvalidate.01" content="def456"', html)
