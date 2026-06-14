from django.db import migrations


DEFAULT_LOCAL_EMBEDDING_MODEL_ID = "42f63a3d-427e-11ef-b3ec-a8a1595801ab"


def remove_default_local_embedding(apps, schema_editor):
    Knowledge = apps.get_model("knowledge", "Knowledge")
    Model = apps.get_model("models_provider", "Model")

    Knowledge.objects.filter(embedding_model_id=DEFAULT_LOCAL_EMBEDDING_MODEL_ID).update(embedding_model_id=None)
    Model.objects.filter(
        id=DEFAULT_LOCAL_EMBEDDING_MODEL_ID,
        provider="model_local_provider",
        model_type="EMBEDDING",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("models_provider", "0001_initial"),
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_default_local_embedding, migrations.RunPython.noop),
    ]
