from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def add_general(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Workspace = apps.get_model("workspaces", "Workspace")
    Member = apps.get_model("workspaces", "Member")
    Channel = apps.get_model("chat", "Channel")
    ChannelMember = apps.get_model("chat", "ChannelMember")
    for workspace in Workspace.objects.filter(channels__isnull=True):
        general = Channel.objects.create(
            workspace=workspace,
            name="general",
            kind="public",
            is_default=True,
            created_by_id=workspace.created_by_id,
        )
        ChannelMember.objects.bulk_create(
            ChannelMember(channel=general, user_id=member.user_id)
            for member in Member.objects.filter(workspace=workspace).exclude(role="guest")
        )


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0001_initial"),
        ("workspaces", "0002_invitation"),
    ]

    operations = [migrations.RunPython(add_general, migrations.RunPython.noop)]
