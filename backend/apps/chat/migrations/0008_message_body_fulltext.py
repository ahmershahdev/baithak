from django.db import migrations


class Migration(migrations.Migration):
    # Django has no FULLTEXT index for MySQL; search (apps/search) queries it with MATCH.
    dependencies = [("chat", "0007_conversation_kinds")]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE chat_message ADD FULLTEXT INDEX message_body_fulltext (body)",
            "ALTER TABLE chat_message DROP INDEX message_body_fulltext",
        )
    ]
