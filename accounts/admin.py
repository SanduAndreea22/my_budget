from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from django.utils.translation import gettext_lazy as _

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'description', 'image')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )

    def get_deleted_objects(self, objs, request):
        """Admin refuses to delete a user whose categories/wallets are PROTECTed by transactions.
        CustomUser.delete() (and the queryset's) clear those rows first, so nothing is actually
        blocked: show the full list of what will go, and do not report protected objects."""
        deleted_objects, model_count, perms_needed, _protected = super().get_deleted_objects(objs, request)
        return deleted_objects, model_count, perms_needed, []


admin.site.register(CustomUser, CustomUserAdmin)

