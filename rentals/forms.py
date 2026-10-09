from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import models
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from .models import Property, Reservation, User, VisitRequest


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        uploads = data if isinstance(data, (list, tuple)) else [data]
        if len(uploads) > 8:
            raise forms.ValidationError("Upload no more than 8 additional photos.")
        return [super().clean(upload, initial) for upload in uploads]


class SignUpForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    role = forms.ChoiceField(
        label="How will you use RentHouse?",
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={"class": "accent-brand-600"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class RoleBasedAuthenticationForm(AuthenticationForm):
    role = forms.ChoiceField(
        label="Log in as",
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={"class": "accent-brand-600"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        user = getattr(self, "user_cache", None)
        if user and user.role != cleaned_data.get("role"):
            raise forms.ValidationError(
                "Please enter valid credentials for the selected account type."
            )
        return cleaned_data


class PropertySearchForm(forms.Form):
    class SortOrder(models.TextChoices):
        NEWEST = "newest", "Newest"
        RENT_LOW = "rent_low", "Rent: low to high"
        RENT_HIGH = "rent_high", "Rent: high to low"
        AVAILABLE = "available", "Available soonest"

    city = forms.CharField(required=False, max_length=100)
    property_type = forms.ChoiceField(
        required=False,
        choices=[("", "Any property type"), *Property.PropertyType.choices],
    )
    min_rent = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    max_rent = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    min_bedrooms = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        label="Bedrooms",
        widget=forms.Select(
            choices=[
                ("", "Any bedrooms"),
                (1, "1+ bedrooms"),
                (2, "2+ bedrooms"),
                (3, "3+ bedrooms"),
                (4, "4+ bedrooms"),
            ]
        ),
    )
    move_in_date = forms.DateField(
        required=False,
        label="Move-in by",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            (SortOrder.NEWEST, "Newest"),
            (SortOrder.RENT_LOW, "Rent: low to high"),
            (SortOrder.RENT_HIGH, "Rent: high to low"),
            (SortOrder.AVAILABLE, "Available soonest"),
        ],
    )

    def clean(self):
        cleaned_data = super().clean()
        min_rent = cleaned_data.get("min_rent")
        max_rent = cleaned_data.get("max_rent")
        if min_rent is not None and max_rent is not None and min_rent > max_rent:
            self.add_error("max_rent", "Maximum rent must be at least the minimum rent.")
        return cleaned_data

    def clean_move_in_date(self):
        move_in_date = self.cleaned_data["move_in_date"]
        if move_in_date and move_in_date < timezone.localdate():
            raise forms.ValidationError("Move-in date cannot be in the past.")
        return move_in_date


class PropertyForm(forms.ModelForm):
    additional_images = MultipleImageField(
        required=False,
        label="Additional property photos",
        help_text="Upload up to 8 extra JPG, PNG, or WebP photos. Each photo must be 5 MB or smaller.",
        widget=MultipleImageInput(),
    )

    class Meta:
        model = Property
        fields = (
            "title",
            "description",
            "property_type",
            "monthly_rent",
            "security_deposit",
            "address",
            "city",
            "state",
            "postal_code",
            "bedrooms",
            "bathrooms",
            "available_from",
            "cover_image",
            "status",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "available_from": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_available_from(self):
        available_from = self.cleaned_data["available_from"]
        if available_from < timezone.localdate():
            raise forms.ValidationError("Availability cannot be in the past.")
        return available_from

    def clean_cover_image(self):
        cover = self.cleaned_data.get("cover_image")
        if isinstance(cover, UploadedFile) and cover.size > 5 * 1024 * 1024:
            raise forms.ValidationError("The main photo must be 5 MB or smaller.")
        if isinstance(cover, UploadedFile):
            if cover.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise forms.ValidationError(
                    "The main photo must be a JPEG, PNG, or WebP image."
                )
            if cover.image.width * cover.image.height > 20_000_000:
                raise forms.ValidationError(
                    "The main photo is too large to display safely."
                )
        return cover

    def clean_additional_images(self):
        photos = self.cleaned_data["additional_images"]
        existing_photos = (
            self.instance.gallery_images.count() if self.instance.pk else 0
        )
        if existing_photos + len(photos) > 8:
            raise forms.ValidationError(
                f"This listing can have up to 8 additional photos. "
                f"You can add {max(0, 8 - existing_photos)} more."
            )
        for photo in photos:
            if photo is None:
                continue
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    f"{photo.name} is larger than the 5 MB photo limit."
                )
            if not isinstance(photo, UploadedFile):
                raise forms.ValidationError("Choose a valid image file.")
            try:
                if photo.image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise forms.ValidationError(
                        f"{photo.name} must be a JPEG, PNG, or WebP image."
                    )
                width, height = photo.image.size
            except forms.ValidationError:
                raise
            except (AttributeError, OSError, ValueError) as error:
                raise forms.ValidationError(
                    f"{photo.name} is not a readable image."
                ) from error
            if width * height > 20_000_000:
                raise forms.ValidationError(
                    f"{photo.name} is too large to display safely."
                )
        return photos


class VisitRequestForm(forms.ModelForm):
    scheduled_for = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = VisitRequest
        fields = ("scheduled_for", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data["scheduled_for"]
        if scheduled_for <= timezone.now():
            raise forms.ValidationError("Choose a visit time in the future.")
        return scheduled_for


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ("start_date", "end_date", "message")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "message": forms.Textarea(attrs={"rows": 3}),
        }


class ReservationDecisionForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (Reservation.Status.CONFIRMED, "Confirm"),
            (Reservation.Status.DECLINED, "Decline"),
        ]


class VisitDecisionForm(forms.ModelForm):
    class Meta:
        model = VisitRequest
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (VisitRequest.Status.CONFIRMED, "Confirm"),
            (VisitRequest.Status.DECLINED, "Decline"),
        ]
