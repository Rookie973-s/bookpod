from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Book


@ensure_csrf_cookie
def catalog(request):
    return render(request, "index.html")


@ensure_csrf_cookie
def collections(request):
    return render(request, "collections.html")


@ensure_csrf_cookie
def topics(request):
    return render(request, "topics.html")


@ensure_csrf_cookie
def my_shelf(request):
    return render(request, "myshelf.html")


@ensure_csrf_cookie
def book_detail(request, slug):
    # 404 for unknown / unpublished books; the page itself loads data from /api/books/<slug>/.
    book = get_object_or_404(Book.objects.select_related("category"), slug=slug, is_published=True)
    return render(request, "book.html", {"book": book})
