from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Property,
    PropertyImage,
    Reservation,
    SavedProperty,
    User,
    VisitRequest,
)


def _property_queryset(*, with_gallery=False):
    queryset = Property.objects.select_related("owner")
    if with_gallery:
        queryset = queryset.prefetch_related("gallery")
    return queryset


def _valid_pk(model, value):
    if value in (None, ""):
        return False
    try:
        model._meta.pk.to_python(value)
    except (TypeError, ValueError, ValidationError, OverflowError):
        return False
    return True


def get_user(user_id):
    if not _valid_pk(User, user_id):
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


def find_user_by_username(username):
    return User.objects.filter(username__iexact=username.strip()).first()


def find_user_by_email(email):
    return User.objects.filter(email__iexact=email.strip()).first()


def create_user(*, username, email, first_name, last_name, role, password):
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role=role,
    )
    user.set_password(password)
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as error:
        if find_user_by_email(email):
            raise ValueError("An account with this email already exists.") from error
        if find_user_by_username(username):
            raise ValueError("That username is already taken.") from error
        raise
    return user


def get_property(property_id, *, owner_id=None, status=None, with_gallery=False):
    if not _valid_pk(Property, property_id):
        return None
    queryset = _property_queryset(with_gallery=with_gallery).filter(pk=property_id)
    if owner_id is not None:
        queryset = queryset.filter(owner_id=owner_id)
    if status is not None:
        queryset = queryset.filter(status=status)
    return queryset.first()


def create_property(values, owner_id):
    return Property.objects.create(owner_id=owner_id, **values)


def update_property(property_id, values, owner_id):
    listing = get_property(property_id, owner_id=owner_id)
    if listing is None:
        return None
    for field, value in values.items():
        setattr(listing, field, value)
    listing.save()
    return listing


def update_property_status(property_id, owner_id, status):
    return Property.objects.filter(pk=property_id, owner_id=owner_id).update(
        status=status,
        updated_at=timezone.now(),
    ) == 1


def list_properties(*, owner_id=None, status=None, filters=None, sort="newest"):
    queryset = _property_queryset()
    if owner_id is not None:
        queryset = queryset.filter(owner_id=owner_id)
    if status is not None:
        queryset = queryset.filter(status=status)
    filters = filters or {}
    keyword = filters.get("q")
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(description__icontains=keyword)
            | Q(address__icontains=keyword)
            | Q(city__icontains=keyword)
        )
    if filters.get("city"):
        queryset = queryset.filter(city__icontains=filters["city"].strip())
    if filters.get("property_type"):
        queryset = queryset.filter(property_type=filters["property_type"])
    if filters.get("min_rent") is not None:
        queryset = queryset.filter(monthly_rent__gte=filters["min_rent"])
    if filters.get("max_rent") is not None:
        queryset = queryset.filter(monthly_rent__lte=filters["max_rent"])
    if filters.get("min_bedrooms"):
        queryset = queryset.filter(bedrooms__gte=filters["min_bedrooms"])
    if filters.get("move_in_date"):
        queryset = queryset.filter(available_from__lte=filters["move_in_date"])
    ordering = {
        "rent_low": ("monthly_rent", "-created_at"),
        "rent_high": ("-monthly_rent", "-created_at"),
        "available": ("available_from", "-created_at"),
    }.get(sort, ("-created_at",))
    return list(queryset.order_by(*ordering))


def count_visits_for_property(property_id):
    return VisitRequest.objects.filter(property_id=property_id).count()


def create_property_image(property_id, image_name):
    return PropertyImage.objects.create(property_id=property_id, image=image_name)


def list_property_images(property_id):
    return list(PropertyImage.objects.filter(property_id=property_id))


def delete_property_image(property_id, image_id):
    image = PropertyImage.objects.filter(pk=image_id, property_id=property_id).first()
    if image is not None:
        image.delete()
    return image


def get_image_count(property_id):
    return PropertyImage.objects.filter(property_id=property_id).count()


def saved_property_ids(renter_id):
    return set(
        SavedProperty.objects.filter(renter_id=renter_id).values_list(
            "property_id", flat=True
        )
    )


def list_saved_properties(renter_id):
    return list(
        _property_queryset()
        .filter(saved_by__renter_id=renter_id, status=Property.Status.PUBLISHED)
        .order_by("-saved_by__created_at")
    )


def set_saved_property(renter_id, property_id, save):
    if save:
        SavedProperty.objects.get_or_create(
            renter_id=renter_id,
            property_id=property_id,
        )
    else:
        SavedProperty.objects.filter(
            renter_id=renter_id,
            property_id=property_id,
        ).delete()


def _visit_queryset():
    return VisitRequest.objects.select_related(
        "property__owner",
        "renter",
    )


def create_visit(property_id, renter_id, scheduled_for, message=""):
    listing = get_property(property_id)
    renter = get_user(renter_id)
    if listing is None or renter is None:
        raise ValueError("The selected listing or account no longer exists.")
    if listing.owner_id == renter.pk:
        raise ValueError("You cannot request a visit to your own property.")
    if scheduled_for <= timezone.now():
        raise ValueError("Choose a visit time in the future.")
    try:
        with transaction.atomic():
            return VisitRequest.objects.create(
                property=listing,
                renter=renter,
                scheduled_for=scheduled_for,
                message=message,
            )
    except IntegrityError as error:
        raise ValueError(
            "You already have an open visit request for this property. Cancel or finish it before requesting another."
        ) from error


def list_visits(*, renter_id=None, owner_id=None):
    queryset = _visit_queryset()
    if renter_id is not None:
        queryset = queryset.filter(renter_id=renter_id)
    elif owner_id is not None:
        queryset = queryset.filter(property__owner_id=owner_id)
    return list(queryset.order_by("scheduled_for"))


def get_visit(visit_id, *, renter_id=None, owner_id=None, status=None):
    if not _valid_pk(VisitRequest, visit_id):
        return None
    queryset = _visit_queryset().filter(pk=visit_id)
    if renter_id is not None:
        queryset = queryset.filter(renter_id=renter_id)
    if owner_id is not None:
        queryset = queryset.filter(property__owner_id=owner_id)
    if isinstance(status, (list, tuple, set)):
        queryset = queryset.filter(status__in=status)
    elif status is not None:
        queryset = queryset.filter(status=status)
    return queryset.first()


def update_visit_status(visit_id, status):
    return VisitRequest.objects.filter(pk=visit_id).update(
        status=status,
        updated_at=timezone.now(),
    ) == 1


def create_reservation(
    property_id,
    renter_id,
    start_date: date,
    end_date: date,
    message="",
):
    listing = get_property(property_id)
    renter = get_user(renter_id)
    if listing is None or renter is None:
        raise ValueError("The selected listing or account no longer exists.")
    if listing.owner_id == renter.pk:
        raise ValueError("You cannot book your own property.")
    if start_date < timezone.localdate():
        raise ValueError("Check-in cannot be in the past.")
    if end_date <= start_date:
        raise ValueError("Check-out must be after check-in.")
    with transaction.atomic():
        overlapping = Reservation.objects.filter(
            property=listing,
            status__in=(Reservation.Status.REQUESTED, Reservation.Status.CONFIRMED),
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if overlapping.exists():
            raise ValueError(
                "These dates overlap another active booking request for this property."
            )
        return Reservation.objects.create(
            property=listing,
            renter=renter,
            start_date=start_date,
            end_date=end_date,
            message=message,
        )


def list_reservations(*, renter_id=None, owner_id=None):
    queryset = Reservation.objects.select_related(
        "property__owner",
        "renter",
    )
    if renter_id is not None:
        queryset = queryset.filter(renter_id=renter_id)
    elif owner_id is not None:
        queryset = queryset.filter(property__owner_id=owner_id)
    return list(queryset.order_by("start_date", "created_at"))


def get_reservation(reservation_id, *, renter_id=None, owner_id=None, status=None):
    if not _valid_pk(Reservation, reservation_id):
        return None
    queryset = Reservation.objects.select_related(
        "property__owner",
        "renter",
    ).filter(pk=reservation_id)
    if renter_id is not None:
        queryset = queryset.filter(renter_id=renter_id)
    if owner_id is not None:
        queryset = queryset.filter(property__owner_id=owner_id)
    if isinstance(status, (list, tuple, set)):
        queryset = queryset.filter(status__in=status)
    elif status is not None:
        queryset = queryset.filter(status=status)
    return queryset.first()


def update_reservation_status(reservation_id, status):
    with transaction.atomic():
        reservation = (
            Reservation.objects.select_for_update()
            .filter(pk=reservation_id)
            .first()
        )
        if reservation is None:
            return False
        if status == Reservation.Status.CONFIRMED:
            overlapping = Reservation.objects.filter(
                property=reservation.property,
                status__in=(
                    Reservation.Status.REQUESTED,
                    Reservation.Status.CONFIRMED,
                ),
                start_date__lt=reservation.end_date,
                end_date__gt=reservation.start_date,
            ).exclude(pk=reservation.pk)
            if overlapping.exists():
                raise ValueError(
                    "These dates overlap another active booking request for this property."
                )
        reservation.status = status
        reservation.save(update_fields=("status", "updated_at"))
        return True
