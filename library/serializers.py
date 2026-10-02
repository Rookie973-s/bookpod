from rest_framework import serializers

from .models import Book, Category, Collection, UserBook


class CategorySerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "icon", "color", "book_count"]


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "color"]


class BookListSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    cover = serializers.ImageField(read_only=True, use_url=True)
    type = serializers.CharField(source="book_type", read_only=True)
    has_file = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id", "slug", "title", "author", "description", "cover", "category", "type", "level",
            "page_count", "publication_date", "is_featured", "has_file", "file_url",
        ]

    def get_has_file(self, obj):
        return bool(obj.file)

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class MyEntrySerializer(serializers.ModelSerializer):
    """The signed-in user's own shelf state for one book (no nested book)."""

    total_pages = serializers.IntegerField(read_only=True)
    percentage = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserBook
        fields = ["id", "status", "current_page", "total_pages", "percentage", "date_started", "date_finished"]


class BookDetailSerializer(BookListSerializer):
    table_of_contents = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()
    my_entry = serializers.SerializerMethodField()

    class Meta(BookListSerializer.Meta):
        fields = BookListSerializer.Meta.fields + [
            "preview_text", "table_of_contents", "publisher", "isbn", "related", "my_entry",
            "created_at", "updated_at",
        ]

    def get_table_of_contents(self, obj):
        return obj.chapters

    def get_related(self, obj):
        """Same category first, then newest from elsewhere, up to five."""
        published = Book.objects.filter(is_published=True).exclude(pk=obj.pk).select_related("category")
        same = list(published.filter(category=obj.category)[:5])
        if len(same) < 5:
            others = published.exclude(category=obj.category)[: 5 - len(same)]
            same.extend(others)
        return BookListSerializer(same, many=True, context=self.context).data

    def get_my_entry(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        entry = UserBook.objects.filter(user=request.user, book=obj).select_related("book").first()
        return MyEntrySerializer(entry).data if entry else None


class CollectionSerializer(serializers.ModelSerializer):
    books = serializers.SerializerMethodField()
    book_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ["id", "slug", "title", "description", "is_featured", "book_count", "books"]

    def _books(self, obj):
        return [
            cb.book
            for cb in obj.collectionbook_set.select_related("book__category").all()
            if cb.book.is_published
        ]

    def get_books(self, obj):
        return BookListSerializer(self._books(obj), many=True, context=self.context).data

    def get_book_count(self, obj):
        return len(self._books(obj))


class UserBookSerializer(serializers.ModelSerializer):
    book = BookListSerializer(read_only=True)
    book_id = serializers.PrimaryKeyRelatedField(
        source="book", queryset=Book.objects.filter(is_published=True), write_only=True, required=False
    )
    book_slug = serializers.SlugRelatedField(
        source="book", slug_field="slug", queryset=Book.objects.filter(is_published=True),
        write_only=True, required=False,
    )
    total_pages = serializers.IntegerField(read_only=True)
    percentage = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserBook
        fields = [
            "id", "book", "book_id", "book_slug", "status", "current_page", "total_pages",
            "percentage", "date_started", "date_finished", "updated_at",
        ]
        read_only_fields = ["date_started", "date_finished", "updated_at"]
        extra_kwargs = {"status": {"required": False}, "current_page": {"required": False}}

    def validate(self, attrs):
        if self.instance is None:
            if "book" not in attrs:
                raise serializers.ValidationError({"book_slug": "Provide book_slug or book_id."})
            book = attrs["book"]
        else:
            if "book" in attrs:
                raise serializers.ValidationError({"book": "A shelf entry's book cannot be changed."})
            book = self.instance.book
        page = attrs.get("current_page")
        if page is not None and book.page_count and page > book.page_count:
            raise serializers.ValidationError(
                {"current_page": f"This book has {book.page_count} pages."}
            )
        return attrs

    def create(self, validated_data):
        entry = UserBook(user=self.context["request"].user, book=validated_data["book"])
        entry.apply_progress(validated_data.get("current_page"), validated_data.get("status"))
        entry.save()
        return entry

    def update(self, instance, validated_data):
        instance.apply_progress(validated_data.get("current_page"), validated_data.get("status"))
        instance.save()
        return instance
