from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

hex_color = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a hex colour such as #2F4858.")


def _unique_slug(model, value, instance_pk=None, max_length=200):
    base = slugify(value)[: max_length - 8] or "item"
    slug, n = base, 2
    qs = model.objects.all()
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Category(models.Model):
    """A topic / category. Managed entirely from Django admin."""

    ICON_CHOICES = [
        ("code", "Code / programming"),
        ("video", "Video / media"),
        ("bible", "Open book / Bible"),
        ("graduation", "Courses / education"),
        ("books", "Books / publications"),
        ("science", "Science"),
        ("business", "Business"),
        ("fiction", "Fiction / stories"),
        ("tag", "Generic tag"),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default="tag")
    color = models.CharField(
        max_length=7, default="#2F4858", validators=[hex_color],
        help_text="Accent colour used on the topic tile and label (hex, e.g. #2F4858).",
    )
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "category / topic"
        verbose_name_plural = "categories / topics"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Category, self.name, self.pk, 100)
        super().save(*args, **kwargs)


class Book(models.Model):
    class Type(models.TextChoices):
        BOOK = "Book", "Book"
        GUIDE = "Guide", "Guide"
        LESSON = "Lesson", "Lesson"
        WORKBOOK = "Workbook", "Workbook"
        COURSE = "Course", "Course"
        STUDY = "Study Material", "Study Material"
        NOTES = "Notes", "Notes"

    class Level(models.TextChoices):
        BEGINNER = "Beginner", "Beginner"
        INTERMEDIATE = "Intermediate", "Intermediate"
        ADVANCED = "Advanced", "Advanced"
        ALL = "All Levels", "All Levels"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    author = models.CharField(max_length=200)
    description = models.TextField(help_text="Shown on the book page and in cards.")
    preview_text = models.TextField(
        "reading preview / snippet", blank=True,
        help_text="A short excerpt shown on the open-book spread. Falls back to the description when empty.",
    )
    table_of_contents = models.TextField(blank=True, help_text="One chapter per line.")

    cover = models.ImageField(
        upload_to="covers/", blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    file = models.FileField(
        "book file", upload_to="books/", blank=True,
        validators=[FileExtensionValidator(["pdf", "epub"])],
        help_text="PDF/EPUB readers can open or download. Optional.",
    )
    page_count = models.PositiveIntegerField(default=0)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="books")
    book_type = models.CharField(max_length=20, choices=Type.choices, default=Type.BOOK)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.ALL)

    publication_date = models.DateField(default=timezone.localdate)
    publisher = models.CharField(max_length=200, blank=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True)

    is_featured = models.BooleanField(default=False, help_text="Eligible for 'Curator's Volume of the Month'.")
    is_published = models.BooleanField(default=True, help_text="Untick to hide from the public site.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-publication_date", "-created_at"]
        indexes = [models.Index(fields=["is_published", "-publication_date"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Book, self.title, self.pk, 200)
        super().save(*args, **kwargs)

    @property
    def chapters(self):
        return [line.strip() for line in self.table_of_contents.splitlines() if line.strip()]


class Collection(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    books = models.ManyToManyField(Book, through="CollectionBook", related_name="collections", blank=True)
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Collection, self.title, self.pk, 200)
        super().save(*args, **kwargs)


class CollectionBook(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["collection", "book"], name="uniq_book_per_collection")]

    def __str__(self):
        return f"{self.collection} → {self.book}"


class Profile(models.Model):
    """Links a Django user to the Google account that signed in."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    google_sub = models.CharField(max_length=64, unique=True)
    picture = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.user} (Google)"


class UserBook(models.Model):
    """A book on a particular user's shelf, with their reading progress."""

    class Status(models.TextChoices):
        READING = "reading", "Currently reading"
        FINISHED = "finished", "Finished"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shelf")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="shelf_entries")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.READING)
    current_page = models.PositiveIntegerField(default=0)
    date_started = models.DateTimeField(default=timezone.now)
    date_finished = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "shelf entry"
        verbose_name_plural = "shelf entries"
        constraints = [models.UniqueConstraint(fields=["user", "book"], name="uniq_book_per_user")]

    def __str__(self):
        return f"{self.user} — {self.book} ({self.status})"

    @property
    def total_pages(self):
        return self.book.page_count

    @property
    def percentage(self):
        """current_page / total_pages × 100, rounded down; finished is always 100."""
        if self.status == self.Status.FINISHED:
            return 100
        total = self.total_pages
        if not total:
            return 0
        return min(100, int(self.current_page * 100 / total))

    def apply_progress(self, current_page=None, status=None):
        """Single place where the reading-state rules live (used by the API and admin)."""
        total = self.total_pages
        now = timezone.now()

        # Re-opening a finished book without naming a page means "read it again".
        if status == self.Status.READING and self.status == self.Status.FINISHED and current_page is None:
            self.status = self.Status.READING
            self.current_page = 0
            self.date_started = now
            self.date_finished = None
            return

        if status is not None:
            self.status = status
        if current_page is not None:
            self.current_page = max(0, min(current_page, total) if total else current_page)

        if self.status == self.Status.FINISHED:
            if total:
                self.current_page = total
            if self.date_finished is None:
                self.date_finished = now
        elif total and self.current_page >= total:
            # Reading the last page counts as finishing the book.
            self.status = self.Status.FINISHED
            self.current_page = total
            if self.date_finished is None:
                self.date_finished = now
        else:
            self.date_finished = None
