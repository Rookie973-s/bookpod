"""
python manage.py seed_library

Creates the default topics and (unless --categories-only) imports the eight books and
three collections that used to be hard-coded in the old frontend, so you have something
to look at on first run. Safe to run repeatedly. Everything it creates can be edited or
deleted in Django admin afterwards.
"""
import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from library.models import Book, Category, Collection, CollectionBook

CATEGORIES = [
    ("Programming & Technology", "code", "#2F4858", "Programming languages, machine learning and everything technology."),
    ("Creative & Media", "video", "#D81784", "Video editing, design and media production guides."),
    ("Bible & Christian Studies", "bible", "#6E1F3C", "Bible study materials, lessons and devotional guides."),
    ("Tutorials & Courses", "graduation", "#6B5B3E", "Step-by-step tutorials and structured courses."),
    ("Books & Publications", "books", "#3B3A36", "Original books, essays and published works."),
]

BOOKS = [
    dict(slug="python-fundamentals", title="Python Fundamentals", author="Richfield A.", cat="Programming & Technology",
         type="Book", level="Beginner", pages=214, date=(2026, 3), featured=True, cover="python-cover.png",
         desc="A grounded, practical introduction to Python variables through file handling built for learners with no prior programming background.",
         toc=["Getting started & setup", "Variables & data types", "Control flow", "Functions", "Data structures", "File handling", "Capstone projects"]),
    dict(slug="neural-networks-practice", title="Neural Networks in Practice", author="Richfield A.", cat="Programming & Technology",
         type="Guide", level="Intermediate", pages=186, date=(2026, 2), cover="neural-cover.png",
         desc="Core neural network concepts paired with runnable examples, for developers moving from scripting into applied machine learning.",
         toc=["Why neural networks", "Perceptrons & layers", "Training & backpropagation", "Convolutional networks", "Evaluating models", "Applied projects"]),
    dict(slug="premiere-pro-masterclass", title="Premiere Pro Masterclass", author="Richfield A.", cat="Creative & Media",
         type="Course", level="Beginner", pages=96, date=(2026, 1), cover="premiere.png",
         desc="A structured path through Adobe Premiere Pro — timelines, color, audio and export — for editors building their first real workflow.",
         toc=["Interface & timelines", "Cutting & pacing", "Color correction basics", "Audio mixing", "Exporting for platforms"]),
    dict(slug="editors-eye", title="The Editor's Eye", author="Rookie A.", cat="Creative & Media",
         type="Book", level="Intermediate", pages=142, date=(2025, 12),
         desc="Notes on visual storytelling and pacing for video editors — how cuts, rhythm and composition carry meaning.",
         toc=["Reading a scene", "Rhythm & pacing", "Composition in the cut", "Case studies"]),
    dict(slug="knowing-god", title="Knowing God: A Study in Trust", author="Rookie A.", cat="Bible & Christian Studies",
         type="Study Material", level="All Levels", pages=64, date=(2026, 3), featured=True,
         desc="A five-week study exploring what it means to know and trust God through seasons of certainty and doubt alike.",
         toc=["Who God says He is", "Trust in the waiting", "When faith is tested", "Walking in obedience", "Living from trust"]),
    dict(slug="abiding-in-christ", title="Abiding in Christ", author="Rookie A.", cat="Bible & Christian Studies",
         type="Lesson", level="All Levels", pages=38, date=(2025, 11),
         desc="A short lesson series on John 15, built for small-group Bible study and personal reflection.",
         toc=["The vine and the branches", "Fruitfulness", "Remaining in His love", "Group discussion guide"]),
    dict(slug="javascript-fundamentals", title="JavaScript Fundamentals", author="Rookie A.", cat="Tutorials & Courses",
         type="Course", level="Beginner", pages=176, date=(2026, 2),
         desc="The essentials of JavaScript for the web — syntax, the DOM and everyday problem solving — taught through small projects.",
         toc=["Syntax & variables", "Functions & scope", "The DOM", "Events", "Small projects"]),
    dict(slug="quiet-discipline", title="Notes on a Quiet Discipline", author="Rookie A.", cat="Books & Publications",
         type="Book", level="All Levels", pages=112, date=(2025, 10),
         desc="A short collection of personal essays on craft, patience and building things that last.",
         toc=["On starting small", "The discipline of finishing", "Building in seasons", "Closing notes"]),
]

COLLECTIONS = [
    ("learn-python", "Learn Python", "A guided path from first script to applied ML.", ["python-fundamentals", "neural-networks-practice"]),
    ("video-editing", "Video Editing Essentials", "From timeline basics to a trained editing eye.", ["premiere-pro-masterclass", "editors-eye"]),
    ("bible-study", "Bible Study Collection", "Short studies for personal or group reflection.", ["knowing-god", "abiding-in-christ"]),
]


class Command(BaseCommand):
    help = "Create default topics and (optionally) the sample books and collections."

    def add_arguments(self, parser):
        parser.add_argument("--categories-only", action="store_true", help="Only create the default topics.")

    def handle(self, *args, **opts):
        cats = {}
        for order, (name, icon, color, desc) in enumerate(CATEGORIES):
            cat, _ = Category.objects.update_or_create(
                name=name, defaults=dict(icon=icon, color=color, description=desc, order=order))
            cats[name] = cat
        self.stdout.write(self.style.SUCCESS(f"{len(cats)} topics ready."))
        if opts["categories_only"]:
            return

        cover_dir = Path(settings.BASE_DIR) / "static" / "images" / "cover"
        for data in BOOKS:
            book, created = Book.objects.update_or_create(
                slug=data["slug"],
                defaults=dict(
                    title=data["title"], author=data["author"], description=data["desc"],
                    category=cats[data["cat"]], book_type=data["type"], level=data["level"],
                    page_count=data["pages"], publication_date=datetime.date(*data["date"], 1),
                    table_of_contents="\n".join(data["toc"]), is_featured=data.get("featured", False),
                    is_published=True,
                ),
            )
            cover_name = data.get("cover")
            if cover_name and not book.cover and (cover_dir / cover_name).exists():
                book.cover.save(cover_name, ContentFile((cover_dir / cover_name).read_bytes()), save=True)

        for order, (slug, title, desc, slugs) in enumerate(COLLECTIONS):
            coll, _ = Collection.objects.update_or_create(
                slug=slug, defaults=dict(title=title, description=desc, order=order, is_featured=True))
            for pos, book_slug in enumerate(slugs):
                CollectionBook.objects.update_or_create(
                    collection=coll, book=Book.objects.get(slug=book_slug), defaults=dict(order=pos))
        self.stdout.write(self.style.SUCCESS(f"{len(BOOKS)} books and {len(COLLECTIONS)} collections ready."))
