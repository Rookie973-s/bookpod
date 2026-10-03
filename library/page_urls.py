from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView

from . import page_views

urlpatterns = [
    path("", page_views.catalog, name="catalog"),
    path("collections/", page_views.collections, name="collections"),
    path("topics/", page_views.topics, name="topics"),
    path("my-shelf/", page_views.my_shelf, name="my-shelf"),
    path("book/<slug:slug>/", page_views.book_detail, name="book-detail"),
    path("robots.txt", page_views.robots_txt, name="robots"),
    path("sitemap.xml", page_views.sitemap_xml, name="sitemap"),
    # Browsers and Google ask for /favicon.ico by default.
    path("favicon.ico", RedirectView.as_view(url=static("images/favicon.ico"), permanent=True)),
]
