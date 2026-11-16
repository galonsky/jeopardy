from django.db import migrations


def normalize_answer_snapshots_single_quotes(apps, schema_editor):
    attempt_model = apps.get_model("study", "Attempt")
    database = schema_editor.connection.alias
    batch = []

    for attempt in attempt_model.objects.using(database).all().iterator(chunk_size=1000):
        normalized = attempt.canonical_snapshot.replace(r"\'", "'")
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
    dependencies = [("study", "0006_normalize_answer_snapshots")]

    operations = [migrations.RunPython(normalize_answer_snapshots_single_quotes, migrations.RunPython.noop)]
