from django.db import migrations, models

import accounts.models


def clear_stale_default_image(apps, schema_editor):
    """The old default pointed every avatar-less user at "default/user.jpg",
    a file that was never actually shipped with the app (media/ isn't
    version-controlled) — that made the field truthy and broke the
    template's own placeholder fallback, showing a broken image instead.
    Reset any row still carrying that stale value back to empty."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    CustomUser.objects.filter(image="default/user.jpg").update(image="")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_customuser_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="image",
            field=models.ImageField(
                blank=True,
                default="",
                null=True,
                upload_to=accounts.models.user_image_upload_path,
                validators=[accounts.models.validate_image_size],
            ),
        ),
        migrations.RunPython(clear_stale_default_image, noop_reverse),
    ]
