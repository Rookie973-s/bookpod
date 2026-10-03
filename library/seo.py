"""
Search-engine and social-share metadata (title, description, canonical URL, Open Graph,
Twitter card, JSON-LD). Every page view builds one `seo` dict and base.html prints it.
"""
import json

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.safestring import mark_safe

SITE_NAME = "BookPod"
DEFAULT_TITLE = "BookPod — Online Library of Books, Guides & Study Materials"
DEFAULT_DESCRIPTION = (
    "BookPod is an online library of original books, guides, lessons and study materials "
    "in programming, creative media, Bible study and more. Browse by topic and read online."
)


def site_url(request):
    """Public address of the site, no trailing slash. SITE_URL (env) wins; else the request's own."""
    if settings.SITE_URL:
        return settings.SITE_URL
    return f"{request.scheme}://{request.get_host()}"


def absolute(request, url):
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return "https:" + url
    return site_url(request) + (url if url.startswith("/") else "/" + url)


def static_abs(request, name):
    return absolute(request, staticfiles_storage.url(name))


def clip(text, limit=155):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:.-—")
    return cut + "…"


def jsonld(data):
    """Serialise for a <script type="application/ld+json"> tag without any chance of breaking out of it."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(raw)


def build(request, *, title=None, description=None, path="/", og_type="website", image=None,
          image_alt=None, robots=None, graph=None, twitter_card="summary_large_image", extra=None):
    base = site_url(request)
    default_image = static_abs(request, "images/og-default.jpg")
    return {
        "title": title or DEFAULT_TITLE,
        "description": clip(description or DEFAULT_DESCRIPTION),
        "canonical": base + path,
        "og_type": og_type,
        "image": image or default_image,
        "image_alt": image_alt or "BookPod — a place for ideas worth keeping",
        "has_default_image": not image,
        "twitter_card": twitter_card if not image else "summary",
        "robots": robots,  # None = default (index, follow)
        "jsonld": jsonld({"@context": "https://schema.org", "@graph": graph}) if graph else None,
        "extra": extra or [],  # extra (property, content) pairs, e.g. book:isbn
        "site_name": SITE_NAME,
        "google_verification": settings.GOOGLE_SITE_VERIFICATION,
        "bing_verification": settings.BING_SITE_VERIFICATION,
        "favicon_192": static_abs(request, "images/favicon-192.png"),
    }


def organization(request):
    base = site_url(request)
    return {
        "@type": "Organization",
        "@id": base + "/#organization",
        "name": SITE_NAME,
        "url": base + "/",
        "logo": static_abs(request, "images/favicon-512.png"),
    }


def website(request):
    base = site_url(request)
    return {
        "@type": "WebSite",
        "@id": base + "/#website",
        "name": SITE_NAME,
        "url": base + "/",
        "inLanguage": "en",
        "publisher": {"@id": base + "/#organization"},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": base + "/topics/?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    }


def book_graph(request, book, url, image):
    base = site_url(request)
    node = {
        "@type": "Book",
        "@id": url + "#book",
        "name": book.title,
        "url": url,
        "author": {"@type": "Person", "name": book.author},
        "description": clip(book.description, 300),
        "inLanguage": "en",
        "genre": book.category.name,
    }
    if image:
        node["image"] = image
    if book.page_count:
        node["numberOfPages"] = book.page_count
    if book.publication_date:
        node["datePublished"] = book.publication_date.isoformat()
    if book.isbn:
        node["isbn"] = book.isbn
    if book.publisher:
        node["publisher"] = {"@type": "Organization", "name": book.publisher}
    crumbs = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": book.category.name,
             "item": f"{base}/topics/?category={book.category.slug}"},
            {"@type": "ListItem", "position": 3, "name": book.title, "item": url},
        ],
    }
    return [node, crumbs]
