from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from .models import Property, Reservation, User, VisitRequest
from .repository import (
    authenticate_user,
    find_user_by_email,
    find_user_by_username,
    get_image_count,
)


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


class SignUpForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    role = forms.ChoiceField(
        label="How will you use RentHouse?",
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={"class": "accent-brand-600"}),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if find_user_by_username(username):
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if find_user_by_email(email):
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two password fields didn’t match.")
        return cleaned_data


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    subject = forms.CharField(required=False, max_length=150)
    message = forms.CharField(
        min_length=10,
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 5}),
    )
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(
            attrs={"tabindex": "-1", "autocomplete": "off"}
        ),
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if "\r" in name or "\n" in name:
            raise forms.ValidationError("Enter your name on a single line.")
        return name

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if "\r" in subject or "\n" in subject:
            raise forms.ValidationError("Enter a subject on a single line.")
        return subject

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("website"):
            raise forms.ValidationError("Unable to submit this message.")
        return cleaned_data


class RoleBasedAuthenticationForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    role = forms.ChoiceField(
        label="Log in as",
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={"class": "accent-brand-600"}),
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        role = cleaned_data.get("role")
        if username and password and role:
            account = authenticate_user(username=username, password=password)
            if account is None or account.role != role:
                raise forms.ValidationError(
                    "Please enter valid credentials for the selected account type."
                )
            self.user = account
        return cleaned_data


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class PasswordResetSetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label="New password",
        strip=False,
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 8 characters.",
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "The two password fields didn’t match.")
        return cleaned_data


class PropertySearchForm(forms.Form):
    class SortOrder:
        NEWEST = "newest"
        RENT_LOW = "rent_low"
        RENT_HIGH = "rent_high"
        AVAILABLE = "available"

    q = forms.CharField(required=False, max_length=150, label="Keyword")
    city = forms.CharField(required=False, max_length=100)
    property_type = forms.ChoiceField(
        required=False,
        choices=[("", "Any property type"), *Property.PropertyType.choices],
    )
    min_rent = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2
    )
    max_rent = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2
    )
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
        minimum = cleaned_data.get("min_rent")
        maximum = cleaned_data.get("max_rent")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("max_rent", "Maximum rent must be at least the minimum rent.")
        return cleaned_data

    def clean_move_in_date(self):
        move_in_date = self.cleaned_data["move_in_date"]
        if move_in_date and move_in_date < timezone.localdate():
            raise forms.ValidationError("Move-in date cannot be in the past.")
        return move_in_date


class PropertyForm(forms.Form):
    title = forms.CharField(max_length=120)
    description = forms.CharField(
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 5, "data-char-counter": "desc-count"}),
    )
    property_type = forms.ChoiceField(choices=Property.PropertyType.choices)
    monthly_rent = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    security_deposit = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    address = forms.CharField(max_length=250)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    postal_code = forms.CharField(max_length=12)
    bedrooms = forms.IntegerField(min_value=1, max_value=20)
    bathrooms = forms.IntegerField(min_value=1, max_value=20)
    available_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    cover_image = forms.ImageField(required=False)
    remove_cover_image = forms.BooleanField(required=False, label="Remove current cover photo")
    status = forms.ChoiceField(choices=Property.Status.choices)
    additional_images = MultipleImageField(
        required=False,
        label="Additional property photos",
        help_text="Upload up to 8 extra JPG, PNG, or WebP photos. Each photo must be 5 MB or smaller.",
        widget=MultipleImageInput(),
    )

    def __init__(self, data=None, files=None, *, instance=None, **kwargs):
        initial = dict(kwargs.pop("initial", {}) or {})
        if instance:
            initial.update(
                {
                    key: getattr(instance, key)
                    for key in (
                        "title", "description", "property_type", "monthly_rent",
                        "security_deposit", "address", "city", "state", "postal_code",
                        "bedrooms", "bathrooms", "available_from", "status",
                    )
                }
            )
        super().__init__(data=data, files=files, initial=initial, **kwargs)
        self.instance = instance
        if not instance or not instance.cover_image:
            self.fields.pop("remove_cover_image")

    def clean_available_from(self):
        available_from = self.cleaned_data["available_from"]
        if available_from < timezone.localdate():
            raise forms.ValidationError("Availability cannot be in the past.")
        return available_from

    @staticmethod
    def _validate_image(upload, *, filename):
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError(f"{filename} is larger than the 5 MB photo limit.")
        if not isinstance(upload, UploadedFile):
            raise forms.ValidationError("Choose a valid image file.")
        try:
            if upload.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise forms.ValidationError(f"{filename} must be a JPEG, PNG, or WebP image.")
            width, height = upload.image.size
        except forms.ValidationError:
            raise
        except (AttributeError, OSError, ValueError) as error:
            raise forms.ValidationError(f"{filename} is not a readable image.") from error
        if width * height > 20_000_000:
            raise forms.ValidationError(f"{filename} is too large to display safely.")

    def clean_cover_image(self):
        cover = self.cleaned_data.get("cover_image")
        if cover:
            self._validate_image(cover, filename="The main photo")
        return cover

    def clean_additional_images(self):
        photos = self.cleaned_data["additional_images"]
        existing = get_image_count(self.instance.pk) if self.instance else 0
        if existing + len(photos) > 8:
            raise forms.ValidationError(
                f"This listing can have up to 8 additional photos. "
                f"You can add {max(0, 8 - existing)} more."
            )
        for photo in photos:
            self._validate_image(photo, filename=photo.name)
        return photos


class VisitRequestForm(forms.Form):
    scheduled_for = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
    )
    message = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data["scheduled_for"]
        if scheduled_for <= timezone.now():
            raise forms.ValidationError("Choose a visit time in the future.")
        return scheduled_for


class ReservationForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    message = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and start_date < timezone.localdate():
            self.add_error("start_date", "Check-in cannot be in the past.")
        if start_date and end_date and end_date <= start_date:
            self.add_error("end_date", "Check-out must be after check-in.")
        return cleaned_data


class ReservationDecisionForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            (Reservation.Status.CONFIRMED, "Confirm"),
            (Reservation.Status.DECLINED, "Decline"),
        ]
    )


class VisitDecisionForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            (VisitRequest.Status.CONFIRMED, "Confirm"),
            (VisitRequest.Status.DECLINED, "Decline"),
        ]
    )
