from django.db import migrations


class Migration(migrations.Migration):
    # Django has no FULLTEXT index for MySQL; search (apps/search) queries it with MATCH.
    dependencies = [("issues", "0002_issue_message")]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE issues_issue ADD FULLTEXT INDEX issue_text_fulltext (title, description)",
            "ALTER TABLE issues_issue DROP INDEX issue_text_fulltext",
        )
    ]
