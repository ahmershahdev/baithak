from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("files", "0001_initial")]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE files_attachment ADD FULLTEXT INDEX attachment_name_fulltext (name)",
            "ALTER TABLE files_attachment DROP INDEX attachment_name_fulltext",
        )
    ]
