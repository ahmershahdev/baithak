from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def guests_leave_channels(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    channel_member = apps.get_model("chat", "ChannelMember")
    member = apps.get_model("workspaces", "Member")
    for guest in member.objects.filter(role="guest"):
        channel_member.objects.filter(
            user_id=guest.user_id,
            channel__workspace_id=guest.workspace_id,
            channel__kind__in=["public", "private"],
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0010_message_sender_name"),
        ("workspaces", "0002_invitation"),
    ]

    operations = [migrations.RunPython(guests_leave_channels, migrations.RunPython.noop)]
