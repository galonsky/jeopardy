from django.db import migrations


def normalize_answer_snapshots(apps, schema_editor):
    attempt_model = apps.get_model("study", "Attempt")
    database = schema_editor.connection.alias
    batch = []

    for attempt in attempt_model.objects.using(database).all().iterator(chunk_size=1000):
        normalized = attempt.canonical_snapshot.replace(r"\"", '"')
        if normalized == attempt.canonical_snapshot:
            continue
        attempt.canonical_snapshot = normalized
        batch.append(attempt)
        if len(batch) == 1000:
            attempt_model.objects.using(database).bulk_update(batch, ["canonical_snapshot"], batch_size=1000)
            batch.clear()

    if batch:
        attempt_model.objects.using(database).bulk_update(batch, ["canonical_snapshot"], batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [("study", "0005_store_recall_rating_and_reveal")]

    operations = [migrations.RunPython(normalize_answer_snapshots, migrations.RunPython.noop)]
