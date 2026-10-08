from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import Property, PropertyImage, User, VisitRequest


class RentalUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")


@admin.register(User)
class RentalUserAdmin(UserAdmin):
    add_form = RentalUserCreationForm
    fieldsets = UserAdmin.fieldsets + (("Rental account", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rental account", {"fields": ("email", "role")}),
    )
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "property_type", "city", "monthly_rent", "status")
    list_filter = ("status", "property_type", "city")
    search_fields = ("title", "city", "owner__username", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [PropertyImageInline]


@admin.register(VisitRequest)
class VisitRequestAdmin(admin.ModelAdmin):
    list_display = ("property", "renter", "scheduled_for", "status")
    list_filter = ("status", "scheduled_for")
    search_fields = ("property__title", "renter__username", "renter__email")
    readonly_fields = ("created_at", "updated_at")
