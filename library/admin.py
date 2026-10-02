from django.contrib import admin
from django.utils.html import format_html

from .models import Book, Category, Collection, CollectionBook, Profile, UserBook


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "color_swatch", "order", "book_total")
    list_editable = ("order",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Colour")
    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:16px;height:16px;border-radius:4px;'
            'background:{};vertical-align:middle"></span> {}', obj.color, obj.color,
        )

    @admin.display(description="Books")
    def book_total(self, obj):
        return obj.books.count()


@admin.action(description="Publish selected books")
def publish_books(modeladmin, request, queryset):
    modeladmin.message_user(request, f"{queryset.update(is_published=True)} book(s) published.")


@admin.action(description="Unpublish selected books")
def unpublish_books(modeladmin, request, queryset):
    modeladmin.message_user(request, f"{queryset.update(is_published=False)} book(s) unpublished.")


@admin.action(description="Mark selected books as featured")
def feature_books(modeladmin, request, queryset):
    modeladmin.message_user(request, f"{queryset.update(is_featured=True)} book(s) featured.")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("cover_thumb", "title", "author", "category", "page_count", "publication_date",
                    "is_featured", "is_published")
    list_display_links = ("cover_thumb", "title")
    list_editable = ("is_featured", "is_published")
    list_filter = ("is_published", "is_featured", "category", "book_type", "level")
    search_fields = ("title", "author", "isbn", "publisher", "description")
    date_hierarchy = "publication_date"
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("cover_preview", "created_at", "updated_at")
    actions = [publish_books, unpublish_books, feature_books]
    save_on_top = True
    fieldsets = (
        ("Basics", {"fields": ("title", "slug", "author", "category", "book_type", "level")}),
        ("Content", {"fields": ("description", "preview_text", "table_of_contents", "page_count")}),
        ("Files", {"fields": ("cover", "cover_preview", "file")}),
        ("Publication", {"fields": ("publication_date", "publisher", "isbn")}),
        ("Visibility", {"fields": ("is_published", "is_featured")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Cover")
    def cover_thumb(self, obj):
        if obj.cover:
            return format_html('<img src="{}" style="height:56px;width:38px;object-fit:cover;border-radius:3px">', obj.cover.url)
        return "—"

    @admin.display(description="Current cover")
    def cover_preview(self, obj):
        if obj and obj.cover:
            return format_html('<img src="{}" style="max-height:220px;border-radius:6px">', obj.cover.url)
        return "No cover uploaded yet."


class CollectionBookInline(admin.TabularInline):
    model = CollectionBook
    extra = 1
    autocomplete_fields = ("book",)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "book_total", "order", "is_featured", "is_published")
    list_editable = ("order", "is_featured", "is_published")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CollectionBookInline]

    @admin.display(description="Books")
    def book_total(self, obj):
        return obj.books.count()


@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    """Read mostly: shelves belong to users; admins can inspect or correct them."""

    list_display = ("user", "book", "status", "current_page", "progress", "date_started", "date_finished")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email", "book__title")
    autocomplete_fields = ("book",)
    raw_id_fields = ("user",)

    @admin.display(description="Progress")
    def progress(self, obj):
        return f"{obj.percentage}%"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "google_sub")
    search_fields = ("user__email", "user__username", "google_sub")
    raw_id_fields = ("user",)
