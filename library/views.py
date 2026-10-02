from django.db.models import Count, Q
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Book, Category, Collection, UserBook
from .serializers import (
    BookDetailSerializer, BookListSerializer, CategorySerializer, CollectionSerializer,
    UserBookSerializer,
)


def published_books():
    return Book.objects.filter(is_published=True).select_related("category")


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/categories/ — topics, each with its published-book count."""

    serializer_class = CategorySerializer
    lookup_field = "slug"
    pagination_class = None

    def get_queryset(self):
        return Category.objects.annotate(
            book_count=Count("books", filter=Q(books__is_published=True))
        ).order_by("order", "name")


class BookViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/books/                  list (published only)
        ?category=<slug>  ?collection=<slug>  ?q=<text>  ?featured=true  ?ordering=title|-title|newest
    GET /api/books/<slug-or-id>/     detail (with related books and the user's own shelf entry)
    """

    lookup_field = "slug"
    lookup_value_regex = r"[-\w]+"

    def get_serializer_class(self):
        return BookDetailSerializer if self.action == "retrieve" else BookListSerializer

    def get_queryset(self):
        qs = published_books()
        params = self.request.query_params

        category = params.get("category")
        if category:
            qs = qs.filter(category__slug=category)

        collection = params.get("collection")
        if collection:
            qs = qs.filter(collectionbook__collection__slug=collection, collectionbook__collection__is_published=True)
            qs = qs.order_by("collectionbook__order", "collectionbook__id")

        q = params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(author__icontains=q) | Q(description__icontains=q)
                | Q(category__name__icontains=q)
            )

        if params.get("featured", "").lower() in {"1", "true", "yes"}:
            qs = qs.filter(is_featured=True)

        ordering = params.get("ordering")
        if ordering in {"title", "-title"}:
            qs = qs.order_by(ordering)
        elif ordering == "newest":
            qs = qs.order_by("-publication_date", "-created_at")
        return qs

    def get_object(self):
        # Accept the numeric id as well as the slug.
        lookup = self.kwargs[self.lookup_field]
        qs = self.get_queryset()
        obj = qs.filter(pk=int(lookup)).first() if lookup.isdigit() else None
        if obj is None:
            obj = qs.filter(slug=lookup).first()
        if obj is None:
            from django.http import Http404
            raise Http404
        self.check_object_permissions(self.request, obj)
        return obj


class CollectionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/collections/ and /api/collections/<slug>/"""

    serializer_class = CollectionSerializer
    lookup_field = "slug"
    pagination_class = None

    def get_queryset(self):
        return Collection.objects.filter(is_published=True).order_by("order", "title")


class StatsView(APIView):
    """GET /api/stats/ — headline numbers for the catalog home page."""

    def get(self, request):
        return Response({
            "books": Book.objects.filter(is_published=True).count(),
            "collections": Collection.objects.filter(is_published=True).count(),
            "topics": Category.objects.count(),
        })


class MyBooksViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """
    The signed-in user's shelf. Every query is scoped to request.user, so one user can
    never read or change another user's entries.

    GET    /api/my-books/?status=reading|finished
    POST   /api/my-books/            {"book_slug": "..."} (or "book_id"), optional current_page/status
    PATCH  /api/my-books/<id>/       {"current_page": 43} or {"status": "finished"}
    DELETE /api/my-books/<id>/
    """

    serializer_class = UserBookSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = UserBook.objects.filter(user=self.request.user, book__is_published=True).select_related("book__category")
        wanted = self.request.query_params.get("status")
        if wanted in UserBook.Status.values:
            qs = qs.filter(status=wanted)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        existing = UserBook.objects.filter(
            user=request.user, book=serializer.validated_data["book"]
        ).first()
        if existing:  # idempotent: adding twice just returns the entry
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        entry = serializer.save()
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)
