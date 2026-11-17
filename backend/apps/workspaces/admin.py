from django.contrib import admin

from apps.workspaces.models import AuditEvent, Member, Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin[Workspace]):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin[Member]):
    list_display = ("workspace", "user", "role", "joined_at")
    list_filter = ("role",)


# The audit log is read-only everywhere, the admin included.
@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin[AuditEvent]):
    list_display = ("at", "workspace", "actor", "action", "model", "object_id")
    list_filter = ("action",)

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False
