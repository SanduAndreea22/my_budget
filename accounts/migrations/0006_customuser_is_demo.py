from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_alter_customuser_options_and_more")]
    operations = [
        migrations.AddField(
            model_name="customuser",
            name="is_demo",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
