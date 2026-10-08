from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    PropertyForm,
    PropertySearchForm,
    SignUpForm,
    VisitDecisionForm,
    VisitRequestForm,
)
from .models import Property, PropertyImage, SavedProperty, User, VisitRequest


def save_additional_images(property_listing, form):
    for image in form.cleaned_data["additional_images"]:
        PropertyImage.objects.create(property=property_listing, image=image)


def home(request):
    search_form = PropertySearchForm(request.GET or None)
    properties = Property.objects.filter(status=Property.Status.PUBLISHED).select_related(
        "owner"
    )
    if search_form.is_valid():
        filters = search_form.cleaned_data
        if filters.get("city"):
            properties = properties.filter(city__icontains=filters["city"].strip())
        if filters.get("property_type"):
            properties = properties.filter(property_type=filters["property_type"])
        if filters.get("min_rent") is not None:
            properties = properties.filter(monthly_rent__gte=filters["min_rent"])
        if filters.get("max_rent") is not None:
            properties = properties.filter(monthly_rent__lte=filters["max_rent"])
        if filters.get("min_bedrooms"):
            properties = properties.filter(bedrooms__gte=filters["min_bedrooms"])
        if filters.get("move_in_date"):
            properties = properties.filter(
                available_from__lte=filters["move_in_date"]
            )
        sort_order = filters.get("sort")
        if sort_order == PropertySearchForm.SortOrder.RENT_LOW:
            properties = properties.order_by("monthly_rent", "-created_at")
        elif sort_order == PropertySearchForm.SortOrder.RENT_HIGH:
            properties = properties.order_by("-monthly_rent", "-created_at")
        elif sort_order == PropertySearchForm.SortOrder.AVAILABLE:
            properties = properties.order_by("available_from", "-created_at")
    else:
        properties = properties.none()
    saved_property_ids = set()
    if request.user.is_authenticated and request.user.role == User.Role.RENTER:
        saved_property_ids = set(
            SavedProperty.objects.filter(renter=request.user).values_list(
                "property_id", flat=True
            )
        )
    return render(
        request,
        "rentals/home.html",
        {
            "search_form": search_form,
            "properties": properties,
            "results_count": properties.count(),
            "saved_property_ids": saved_property_ids,
        },
    )


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def property_detail(request, pk):
    property_listing = get_object_or_404(Property, pk=pk)
    if (
        property_listing.status != Property.Status.PUBLISHED
        and property_listing.owner_id != request.user.id
        and not request.user.is_staff
    ):
        raise Http404
    visit_form = VisitRequestForm()
    is_saved = False
    if request.user.is_authenticated and request.user.role == User.Role.RENTER:
        is_saved = SavedProperty.objects.filter(
            renter=request.user, property=property_listing
        ).exists()
    return render(
        request,
        "rentals/property_detail.html",
        {
            "property": property_listing,
            "visit_form": visit_form,
            "is_saved": is_saved,
            "gallery_images": property_listing.gallery_images.all(),
        },
    )


@login_required
def dashboard(request):
    if request.user.role == User.Role.LANDLORD:
        properties = Property.objects.filter(owner=request.user).annotate(
            visit_count=Count("visit_requests", distinct=True)
        )
        visit_requests = VisitRequest.objects.filter(
            property__owner=request.user
        ).select_related("property", "renter")
        saved_properties = Property.objects.none()
        summary = {
            "properties": properties.count(),
            "published": properties.filter(status=Property.Status.PUBLISHED).count(),
            "pending_visits": visit_requests.filter(
                status=VisitRequest.Status.REQUESTED
            ).count(),
            "total_visits": visit_requests.count(),
        }
    else:
        properties = Property.objects.none()
        visit_requests = VisitRequest.objects.filter(renter=request.user).select_related(
            "property", "property__owner"
        )
        saved_properties = Property.objects.filter(
            saved_by__renter=request.user,
            status=Property.Status.PUBLISHED,
        ).select_related("owner")
        summary = {
            "saved": saved_properties.count(),
            "pending_visits": visit_requests.filter(
                status=VisitRequest.Status.REQUESTED
            ).count(),
            "confirmed_visits": visit_requests.filter(
                status=VisitRequest.Status.CONFIRMED
            ).count(),
        }
    return render(
        request,
        "rentals/dashboard.html",
        {
            "properties": properties,
            "visit_requests": visit_requests,
            "saved_properties": saved_properties,
            "summary": summary,
        },
    )


@login_required
def property_create(request):
    if request.user.role != User.Role.LANDLORD:
        messages.error(
            request,
            "Only service provider accounts can create property listings.",
        )
        return redirect("dashboard")
    form = PropertyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        property_listing = form.save(commit=False)
        property_listing.owner = request.user
        property_listing.save()
        save_additional_images(property_listing, form)
        messages.success(request, "Your listing has been saved.")
        return redirect("dashboard")
    return render(request, "rentals/property_form.html", {"form": form})


@login_required
def property_edit(request, pk):
    property_listing = get_object_or_404(Property, pk=pk, owner=request.user)
    form = PropertyForm(
        request.POST or None,
        request.FILES or None,
        instance=property_listing,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        save_additional_images(property_listing, form)
        messages.success(request, "Your listing has been updated.")
        return redirect("dashboard")
    return render(
        request,
        "rentals/property_form.html",
        {
            "form": form,
            "property": property_listing,
            "gallery_images": property_listing.gallery_images.all(),
        },
    )


@login_required
@require_POST
def property_image_delete(request, pk, image_pk):
    property_listing = get_object_or_404(Property, pk=pk, owner=request.user)
    image = get_object_or_404(
        PropertyImage, pk=image_pk, property=property_listing
    )
    stored_file = image.image
    image.delete()
    stored_file.delete(save=False)
    messages.success(request, "The property photo has been removed.")
    return redirect("property_edit", pk=property_listing.pk)


@login_required
@require_POST
def property_status_update(request, pk):
    property_listing = get_object_or_404(Property, pk=pk, owner=request.user)
    allowed_transitions = {
        Property.Status.DRAFT: {Property.Status.PUBLISHED, Property.Status.ARCHIVED},
        Property.Status.PUBLISHED: {Property.Status.PAUSED, Property.Status.ARCHIVED},
        Property.Status.PAUSED: {Property.Status.PUBLISHED, Property.Status.ARCHIVED},
        Property.Status.ARCHIVED: {Property.Status.DRAFT},
    }
    new_status = request.POST.get("status")
    if new_status not in allowed_transitions[property_listing.status]:
        messages.error(request, "That listing status change is not allowed.")
        return redirect("dashboard")
    property_listing.status = new_status
    property_listing.save(update_fields=["status", "updated_at"])
    messages.success(
        request, f'“{property_listing.title}” is now {property_listing.get_status_display().lower()}.'
    )
    return redirect("dashboard")


@login_required
@require_POST
def saved_property_toggle(request, pk):
    if request.user.role != User.Role.RENTER:
        messages.error(request, "Only home seeker accounts can save properties.")
        return redirect("property_detail", pk=pk)
    property_listing = get_object_or_404(
        Property, pk=pk, status=Property.Status.PUBLISHED
    )
    if request.POST.get("action") == "remove":
        SavedProperty.objects.filter(
            renter=request.user, property=property_listing
        ).delete()
        messages.success(request, "Property removed from your saved list.")
    else:
        SavedProperty.objects.get_or_create(
            renter=request.user,
            property=property_listing,
        )
        messages.success(request, "Property saved to your list.")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("property_detail", pk=pk)


@login_required
@require_POST
def visit_request_create(request, pk):
    property_listing = get_object_or_404(
        Property, pk=pk, status=Property.Status.PUBLISHED
    )
    if request.user.role != User.Role.RENTER:
        messages.error(
            request, "Only home seeker accounts can request property viewings."
        )
        return redirect("property_detail", pk=pk)
    form = VisitRequestForm(request.POST)
    if form.is_valid():
        visit_request = form.save(commit=False)
        visit_request.property = property_listing
        visit_request.renter = request.user
        try:
            visit_request.save()
        except IntegrityError:
            form.add_error(
                None,
                "You already have an open visit request for this property. "
                "Cancel or finish it before requesting another.",
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Visit request sent to the landlord.")
            return redirect("dashboard")
    return render(
        request,
        "rentals/property_detail.html",
        {
            "property": property_listing,
            "visit_form": form,
            "gallery_images": property_listing.gallery_images.all(),
            "is_saved": SavedProperty.objects.filter(
                renter=request.user, property=property_listing
            ).exists(),
        },
    )


@login_required
@require_POST
def visit_request_decide(request, pk):
    visit_request = get_object_or_404(
        VisitRequest.objects.select_related("property"),
        pk=pk,
        property__owner=request.user,
        status=VisitRequest.Status.REQUESTED,
    )
    form = VisitDecisionForm(request.POST, instance=visit_request)
    if form.is_valid():
        form.save()
        messages.success(request, "The visit request has been updated.")
    else:
        messages.error(request, "Choose a valid decision for this visit request.")
    return redirect("dashboard")


@login_required
@require_POST
def visit_request_cancel(request, pk):
    visit_request = get_object_or_404(
        VisitRequest.objects.select_related("property"),
        pk=pk,
        renter=request.user,
        status__in=[VisitRequest.Status.REQUESTED, VisitRequest.Status.CONFIRMED],
    )
    visit_request.status = VisitRequest.Status.CANCELLED
    visit_request.save(update_fields=["status", "updated_at"])
    messages.success(request, "Your visit request has been cancelled.")
    return redirect("dashboard")
