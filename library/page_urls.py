from django.urls import path

from . import page_views

urlpatterns = [
    path("", page_views.catalog, name="catalog"),
    path("collections/", page_views.collections, name="collections"),
    path("topics/", page_views.topics, name="topics"),
    path("my-shelf/", page_views.my_shelf, name="my-shelf"),
    path("book/<slug:slug>/", page_views.book_detail, name="book-detail"),
]
