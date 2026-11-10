import re

from django.db import migrations

# Old entries end with a literal currency code ("... 25.00 RON" / "... 25.00 RON (recurring)"
# / "... 25.00 RON · day 5"). Replace it with the {cur} placeholder so the history shows the
# account's current currency, like every other page.
PATTERN = re.compile(r"(\d(?:\.\d+)?) (?:RON|EUR|USD|GBP)(?=$| \(recurring\)$| · day \d+$)")


def to_token(apps, schema_editor):
    ActivityLog = apps.get_model("budget", "ActivityLog")
    for entry in ActivityLog.objects.exclude(object_repr__contains="{cur}").iterator():
        new = PATTERN.sub(r"\1 {cur}", entry.object_repr)
        if new != entry.object_repr:
            entry.object_repr = new
            entry.save(update_fields=["object_repr"])


class Migration(migrations.Migration):
    dependencies = [("budget", "0012_category_type")]
    operations = [migrations.RunPython(to_token, migrations.RunPython.noop)]
