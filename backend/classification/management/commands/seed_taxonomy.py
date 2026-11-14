from django.core.management.base import BaseCommand

from classification.models import Subject, Subtopic

TAXONOMY = {
    "Geography": [
        "World capitals",
        "Countries and regions",
        "US geography",
        "Physical geography",
        "Rivers and bodies of water",
    ],
    "History": ["Ancient history", "European history", "American history", "World history", "War and military history"],
    "Literature": ["Authors", "Novels", "Poetry", "Drama", "Literary works"],
    "Science": ["Biology", "Chemistry", "Physics", "Astronomy", "Earth science", "Mathematics"],
    "Arts": ["Visual art", "Classical music", "Architecture", "Dance", "Theater"],
    "Entertainment": ["Movies", "Television", "Popular music", "Celebrities", "Video games"],
    "Religion & Mythology": ["World religions", "Greek mythology", "Roman mythology", "Myth and folklore"],
    "Language": ["Word meanings", "Etymology", "Spelling", "Foreign languages", "Wordplay"],
    "Sports": ["Olympics", "American sports", "International sports", "Athletes", "Sports rules"],
    "Society & Politics": ["Government", "Law", "US politics", "World politics", "Social movements"],
    "Business & Economics": ["Companies", "Economics", "Finance", "Inventions and industry"],
    "Food & Drink": ["Food", "World cuisines", "Beverages", "Ingredients"],
    "General Knowledge": ["Animals", "People and places", "Everyday knowledge", "Numbers and measures"],
}


def slugify(value: str) -> str:
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in value).split())


class Command(BaseCommand):
    help = "Create or update the built-in v1 subject taxonomy."

    def handle(self, *args, **options):
        for index, (name, topics) in enumerate(TAXONOMY.items()):
            subject, _ = Subject.objects.update_or_create(
                slug=slugify(name), defaults={"name": name, "sort_order": index}
            )
            for topic in topics:
                Subtopic.objects.update_or_create(subject=subject, slug=slugify(topic), defaults={"name": topic})
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(TAXONOMY)} subjects."))
