from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "BookPod administration"
admin.site.site_title = "BookPod admin"
admin.site.index_title = "Manage the library"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("library.api_urls")),
    path("", include("library.page_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
