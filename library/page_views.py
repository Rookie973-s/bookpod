from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from . import seo
from .models import Book, Category, Collection


@ensure_csrf_cookie
def catalog(request):
    graph = [seo.organization(request), seo.website(request)]
    return render(request, "index.html", {"seo": seo.build(request, path="/", graph=graph)})


@ensure_csrf_cookie
def collections(request):
    page = seo.build(
        request,
        title="Collections — Curated Reading Lists | BookPod",
        description="Guided reading paths: hand-picked collections of related books, guides and study materials on BookPod.",
        path="/collections/",
    )
    return render(request, "collections.html", {"seo": page})


@ensure_csrf_cookie
def topics(request):
    slug = request.GET.get("category", "").strip()
    category = Category.objects.filter(slug=slug).first() if slug else None
    path = "/topics/"
    title = "Topics — Browse Books by Subject | BookPod"
    description = "Browse BookPod by topic: programming and technology, creative media, Bible study, tutorials and more."
    if category:
        path = f"/topics/?category={category.slug}"
        title = f"{category.name} — Books & Study Materials | BookPod"
        description = category.description or f"Books, guides and study materials about {category.name} on BookPod."
    # Search-result pages (?q=) are endless near-duplicates: let people use them, keep them out of Google.
    robots = "noindex, follow" if request.GET.get("q", "").strip() else None
    page = seo.build(request, title=title, description=description, path=path, robots=robots)
    return render(request, "topics.html", {"seo": page})


@ensure_csrf_cookie
def my_shelf(request):
    # Personal page (different for every reader): not for search results.
    page = seo.build(request, title="My Books & Progress | BookPod", path="/my-shelf/", robots="noindex, follow")
    return render(request, "myshelf.html", {"seo": page})


@ensure_csrf_cookie
def book_detail(request, slug):
    # 404 for unknown / unpublished books; the page itself loads richer data from /api/books/<slug>/.
    book = get_object_or_404(Book.objects.select_related("category"), slug=slug, is_published=True)
    path = reverse("book-detail", args=[book.slug])
    url = seo.site_url(request) + path
    cover = seo.absolute(request, book.cover.url) if book.cover else ""
    extra = []
    if book.isbn:
        extra.append(("book:isbn", book.isbn))
    if book.publication_date:
        extra.append(("book:release_date", book.publication_date.isoformat()))
    extra.append(("book:tag", book.category.name))
    description = book.description
    if len(" ".join(description.split())) < 110:
        description += f" A {book.page_count}-page {book.get_book_type_display().lower()} in {book.category.name} on BookPod."
    page = seo.build(
        request,
        title=seo.clip(f"{book.title} by {book.author}", 58) + " | BookPod",
        description=description,
        path=path,
        og_type="book",
        image=cover,
        image_alt=f"Cover of {book.title} by {book.author}" if cover else None,
        graph=seo.book_graph(request, book, url, cover),
        extra=extra,
    )
    return render(request, "book.html", {"book": book, "seo": page})


# --- robots.txt, sitemap.xml, favicon -------------------------------------------------------------

def robots_txt(request):
    base = seo.site_url(request)
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "# /api/ is deliberately NOT blocked: the pages load their content from it, and Google has to",
        "# be able to fetch it to see that content. API responses carry 'X-Robots-Tag: noindex' instead.",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ])
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    from xml.sax.saxutils import escape

    base = seo.site_url(request)
    rows = [(f"{base}/", None, "daily", "1.0"),
            (f"{base}/collections/", None, "weekly", "0.7"),
            (f"{base}/topics/", None, "weekly", "0.7")]
    for cat in Category.objects.all():
        rows.append((f"{base}/topics/?category={cat.slug}", None, "weekly", "0.6"))
    for b in Book.objects.filter(is_published=True).only("slug", "updated_at"):
        rows.append((base + reverse("book-detail", args=[b.slug]), b.updated_at.date().isoformat(), "monthly", "0.8"))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, freq, prio in rows:
        parts.append("<url><loc>%s</loc>%s<changefreq>%s</changefreq><priority>%s</priority></url>" % (
            escape(loc), f"<lastmod>{lastmod}</lastmod>" if lastmod else "", freq, prio))
    parts.append("</urlset>")
    return HttpResponse("\n".join(parts), content_type="application/xml; charset=utf-8")
