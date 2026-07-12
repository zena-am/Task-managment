from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from .services.user_service import UserService
# Register your models here.


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "is_active", "is_deleted", "deleted_at")
    list_filter = ("is_active", "is_deleted", "is_staff", "is_superuser")
    readonly_fields = ("deleted_at",)
    actions = ("soft_delete_selected", "restore_selected")

    @admin.action(description="Soft delete selected users")
    def soft_delete_selected(self, request, queryset):
        for user in queryset.exclude(is_deleted=True):
            UserService.soft_delete_account(user)

    @admin.action(description="Restore selected users")
    def restore_selected(self, request, queryset):
        for user in queryset.filter(is_deleted=True):
            user.restore()

    def get_queryset(self, request):
        return User.all_objects.all()

    def delete_model(self, request, obj):
        UserService.soft_delete_account(obj)

    def delete_queryset(self, request, queryset):
        for user in queryset:
            UserService.soft_delete_account(user)

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2","first_name","last_name","email"),
            },
        ),
    )