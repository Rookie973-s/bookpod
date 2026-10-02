from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views, views

router = DefaultRouter()
router.register("books", views.BookViewSet, basename="book")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("collections", views.CollectionViewSet, basename="collection")
router.register("my-books", views.MyBooksViewSet, basename="my-book")

urlpatterns = [
    path("stats/", views.StatsView.as_view(), name="stats"),
    path("auth/config/", auth_views.AuthConfigView.as_view(), name="auth-config"),
    path("auth/me/", auth_views.MeView.as_view(), name="auth-me"),
    path("auth/google/", auth_views.GoogleLoginView.as_view(), name="auth-google"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="auth-logout"),
    path("", include(router.urls)),
]
