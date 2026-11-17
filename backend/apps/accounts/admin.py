from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.accounts import lockout
from apps.accounts.models import ContactMessage, User


@admin.register(User)
class BaithakUserAdmin(UserAdmin):  # type: ignore[type-arg]
    list_display = ("email", "username", "is_active", "lock_level", "locked_until", "banned_at")
    list_filter = ("is_active", "is_staff", "lock_level")
    readonly_fields = ("failed_attempts", "lock_level", "locked_until", "banned_at")
    fieldsets = (
        *UserAdmin.fieldsets,  # type: ignore[misc]
        ("Lockout", {"fields": ("failed_attempts", "lock_level", "locked_until", "banned_at")}),
    )
    actions = ("unlock_accounts",)

    @admin.action(description="Unlock: lift locks and bans and start the count again")
    def unlock_accounts(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        for user in queryset:
            lockout.unlock(user)
        self.message_user(request, f"Unlocked {queryset.count()} accounts.", messages.SUCCESS)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin[ContactMessage]):
    list_display = ("created_at", "name", "email", "sent_at")
    readonly_fields = ("name", "email", "message", "created_at", "sent_at")
