from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Follow


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'nickname', 'investment_type', 'risk_score', 'is_staff')
    list_filter = ('is_staff', 'investment_type')
    search_fields = ('email', 'nickname')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('프로필', {'fields': ('nickname', 'bio', 'profile_image', 'investment_type', 'risk_score')}),
        ('권한', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nickname', 'password1', 'password2'),
        }),
    )


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'following', 'created_at')
