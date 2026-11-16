import hashlib
import json

from django.db import migrations


def normalize_escaped_single_quotes(apps, schema_editor):
    source_clue = apps.get_model("clues", "SourceClue")
    database = schema_editor.connection.alias
    text_fields = ("clue_text", "correct_response", "original_category", "category_comments")
    batch = []

    for clue in source_clue.objects.using(database).all().iterator(chunk_size=1000):
        changed = False
        for field in text_fields:
            value = getattr(clue, field)
            normalized = value.replace(r"\'", "'")
            if normalized != value:
                setattr(clue, field, normalized)
                changed = True
        if not changed:
            continue

        fingerprint_payload = json.dumps(
            [clue.clue_text, clue.correct_response, clue.original_category],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        clue.content_fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()
        batch.append(clue)
        if len(batch) == 1000:
            source_clue.objects.using(database).bulk_update(
                batch,
                [*text_fields, "content_fingerprint"],
                batch_size=1000,
            )
            batch.clear()

    if batch:
        source_clue.objects.using(database).bulk_update(
            batch,
            [*text_fields, "content_fingerprint"],
            batch_size=1000,
        )


class Migration(migrations.Migration):
    dependencies = [("clues", "0003_normalize_escaped_quotes")]

    operations = [migrations.RunPython(normalize_escaped_single_quotes, migrations.RunPython.noop)]
