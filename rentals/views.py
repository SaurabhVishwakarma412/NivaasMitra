import logging
import smtplib
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    ContactForm,
    PropertyForm,
    PropertySearchForm,
    ReservationDecisionForm,
    ReservationForm,
    RoleBasedAuthenticationForm,
    SignUpForm,
    VisitDecisionForm,
    VisitRequestForm,
)
from .models import Property, Reservation, User, VisitRequest
from .repository import (
    count_visits_for_property,
    create_property,
    create_property_image,
    create_reservation,
    create_user,
    create_visit,
    delete_property_image,
    get_property,
    get_reservation,
    get_visit,
    list_properties,
    list_reservations,
    list_saved_properties,
    list_visits,
    saved_property_ids,
    set_saved_property,
    update_property,
    update_property_status,
    update_reservation_status,
    update_visit_status,
)

logger = logging.getLogger(__name__)


def require_login(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('login')}?{query}")
        return view(request, *args, **kwargs)

    return wrapped


def _save_image(upload, path):
    return default_storage.save(path, upload)


def _search_context(request):
    form = PropertySearchForm(request.GET or None)
    valid_search = form.is_valid()
    if not request.GET or valid_search:
        filters = form.cleaned_data if valid_search else {}
        properties = list_properties(
            status=Property.Status.PUBLISHED,
            filters=filters,
            sort=filters.get("sort") or PropertySearchForm.SortOrder.NEWEST,
        )
    else:
        properties = []
    saved_ids = (
        saved_property_ids(request.user.id)
        if request.user.is_authenticated and request.user.role == User.Role.RENTER
        else set()
    )
    return form, properties, saved_ids


def home(request):
    search_form, properties, saved_ids = _search_context(request)
    return render(
        request,
        "rentals/home.html",
        {
            "search_form": search_form,
            "properties": properties,
            "featured": properties[:6],
            "results_count": len(properties),
            "saved_property_ids": saved_ids,
            "listings_url": reverse("listings"),
        },
    )


def listings(request):
    search_form, results, saved_ids = _search_context(request)
    paginator = Paginator(results, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "rentals/listings.html",
        {
            "search_form": search_form,
            "properties": page_obj.object_list,
            "page_obj": page_obj,
            "results_count": len(results),
            "saved_property_ids": saved_ids,
            "base_qs": query.urlencode(),
        },
    )


def about(request):
    return render(request, "rentals/about.html")


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            user = create_user(
                username=data["username"],
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=data["role"],
                password=data["password1"],
            )
        except ValueError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Your account is ready.")
            auth_login(request, user)
            return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RoleBasedAuthenticationForm(request.POST or None)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.method == "POST" and form.is_valid():
        user = form.user
        auth_login(request, user)
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            response = redirect(next_url)
        else:
            response = redirect("dashboard")
        return response
    return render(
        request,
        "registration/login.html",
        {"form": form, "next": next_url},
    )


@require_POST
def logout_view(request):
    auth_logout(request)
    response = redirect("home")
    return response


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        subject = data["subject"].strip() or f"Message from {data['name']}"
        body = (
            f"From: {data['name']} <{data['email']}>\n\n"
            f"{data['message']}"
        )
        try:
            sent_count = send_mail(
                subject=f"RentHouse contact: {subject}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL],
                fail_silently=False,
            )
        except (OSError, smtplib.SMTPException):
            logger.exception("Could not send a RentHouse contact message")
            messages.error(
                request,
                "We couldn't send your message right now. Please try again later or email us directly.",
            )
        else:
            if sent_count == 1:
                messages.success(
                    request,
                    "Thanks for getting in touch. Your message has been sent.",
                )
                return redirect("contact")
            logger.error("The configured email backend did not send the contact message")
            messages.error(
                request,
                "We couldn't send your message right now. Please try again later or email us directly.",
            )
    return render(
        request,
        "rentals/contact.html",
        {"form": form, "contact_email": settings.CONTACT_EMAIL},
    )


def _property_or_404(pk, *, owner_id=None, status=None):
    property_listing = get_property(pk, owner_id=owner_id, status=status)
    if property_listing is None:
        raise Http404
    return property_listing


def property_detail(request, pk):
    property_listing = get_property(pk)
    if property_listing is None:
        raise Http404
    if (
        property_listing.status != Property.Status.PUBLISHED
        and property_listing.owner_id != request.user.id
        and not request.user.is_staff
    ):
        raise Http404
    is_saved = (
        property_listing.pk in saved_property_ids(request.user.id)
        if request.user.is_authenticated and request.user.role == User.Role.RENTER
        else False
    )
    return render(
        request,
        "rentals/property_detail.html",
        {
            "property": property_listing,
            "visit_form": VisitRequestForm(),
            "reservation_form": ReservationForm(),
            "is_saved": is_saved,
            "gallery_images": property_listing.gallery_images,
        },
    )


@require_login
def dashboard(request):
    if request.user.role == User.Role.LANDLORD:
        properties = list_properties(owner_id=request.user.id)
        for listing in properties:
            listing.visit_count = count_visits_for_property(listing.pk)
        visit_requests = list_visits(owner_id=request.user.id)
        reservations = list_reservations(owner_id=request.user.id)
        saved_properties = []
        summary = {
            "properties": len(properties),
            "published": sum(p.status == Property.Status.PUBLISHED for p in properties),
            "pending_visits": sum(v.status == VisitRequest.Status.REQUESTED for v in visit_requests),
            "total_visits": len(visit_requests),
            "pending_reservations": sum(r.status == Reservation.Status.REQUESTED for r in reservations),
            "total_reservations": len(reservations),
        }
    else:
        properties = []
        visit_requests = list_visits(renter_id=request.user.id)
        reservations = list_reservations(renter_id=request.user.id)
        saved_properties = list_saved_properties(request.user.id)
        summary = {
            "saved": len(saved_properties),
            "pending_visits": sum(v.status == VisitRequest.Status.REQUESTED for v in visit_requests),
            "confirmed_visits": sum(v.status == VisitRequest.Status.CONFIRMED for v in visit_requests),
            "pending_reservations": sum(r.status == Reservation.Status.REQUESTED for r in reservations),
            "confirmed_reservations": sum(r.status == Reservation.Status.CONFIRMED for r in reservations),
        }
    return render(
        request,
        "rentals/dashboard.html",
        {
            "properties": properties,
            "visit_requests": visit_requests,
            "reservations": reservations,
            "saved_properties": saved_properties,
            "summary": summary,
            "role": "provider" if request.user.role == User.Role.LANDLORD else "seeker",
            "listings_url": reverse("listings"),
            "property_create_url": reverse("property_create"),
        },
    )


@require_login
def property_create(request):
    if request.user.role != User.Role.LANDLORD:
        messages.error(request, "Only service provider accounts can create property listings.")
        return redirect("dashboard")
    form = PropertyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        cover = values.pop("cover_image", None)
        values.pop("remove_cover_image", None)
        images = values.pop("additional_images", [])
        if cover:
            values["cover_image"] = _save_image(cover, f"properties/covers/{cover.name}")
        else:
            values["cover_image"] = ""
        property_listing = create_property(values, request.user.id)
        for image in images:
            path = _save_image(image, f"properties/gallery/{property_listing.pk}/{image.name}")
            create_property_image(property_listing.pk, path)
        messages.success(request, "Your listing has been saved.")
        return redirect("dashboard")
    return render(request, "rentals/property_form.html", {"form": form})


@require_login
def property_edit(request, pk):
    property_listing = _property_or_404(pk, owner_id=request.user.id)
    form = PropertyForm(
        request.POST or None,
        request.FILES or None,
        instance=property_listing,
    )
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        cover = values.pop("cover_image", None)
        remove_cover = values.pop("remove_cover_image", False)
        images = values.pop("additional_images", [])
        old_cover = property_listing.cover_image.name
        values["cover_image"] = old_cover
        if cover:
            values["cover_image"] = _save_image(cover, f"properties/covers/{cover.name}")
        elif remove_cover:
            values["cover_image"] = ""
        updated = update_property(pk, values, request.user.id)
        if updated is None:
            raise Http404
        if old_cover and old_cover != updated.cover_image.name:
            default_storage.delete(old_cover)
        for image in images:
            path = _save_image(image, f"properties/gallery/{updated.pk}/{image.name}")
            create_property_image(updated.pk, path)
        messages.success(request, "Your listing has been updated.")
        return redirect("dashboard")
    return render(
        request,
        "rentals/property_form.html",
        {"form": form, "property": property_listing, "gallery_images": property_listing.gallery_images},
    )


@require_login
@require_POST
def property_image_delete(request, pk, image_pk):
    property_listing = _property_or_404(pk, owner_id=request.user.id)
    image = delete_property_image(property_listing.pk, image_pk)
    if image is None:
        raise Http404
    default_storage.delete(image.image.name)
    messages.success(request, "The property photo has been removed.")
    return redirect("property_edit", pk=property_listing.pk)


@require_login
@require_POST
def property_status_update(request, pk):
    property_listing = _property_or_404(pk, owner_id=request.user.id)
    allowed = {
        Property.Status.DRAFT: {Property.Status.PUBLISHED, Property.Status.ARCHIVED},
        Property.Status.PUBLISHED: {Property.Status.PAUSED, Property.Status.ARCHIVED},
        Property.Status.PAUSED: {Property.Status.PUBLISHED, Property.Status.ARCHIVED},
        Property.Status.ARCHIVED: {Property.Status.DRAFT},
    }
    new_status = request.POST.get("status")
    if new_status not in allowed[property_listing.status]:
        messages.error(request, "That listing status change is not allowed.")
        return redirect("dashboard")
    update_property_status(pk, request.user.id, new_status)
    messages.success(request, f"“{property_listing.title}” is now {new_status.lower()}.")
    return redirect("dashboard")


@require_login
@require_POST
def saved_property_toggle(request, pk):
    if request.user.role != User.Role.RENTER:
        messages.error(request, "Only home seeker accounts can save properties.")
        return redirect("property_detail", pk=pk)
    property_listing = _property_or_404(pk, status=Property.Status.PUBLISHED)
    save = request.POST.get("action") != "remove"
    set_saved_property(request.user.id, property_listing.pk, save)
    messages.success(
        request,
        "Property saved to your list." if save else "Property removed from your saved list.",
    )
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("property_detail", pk=pk)


def _detail_error(request, property_listing, *, visit_form=None, reservation_form=None):
    return render(
        request,
        "rentals/property_detail.html",
        {
            "property": property_listing,
            "visit_form": visit_form or VisitRequestForm(),
            "reservation_form": reservation_form or ReservationForm(),
            "gallery_images": property_listing.gallery_images,
            "is_saved": property_listing.pk in saved_property_ids(request.user.id),
        },
    )


@require_login
@require_POST
def visit_request_create(request, pk):
    property_listing = _property_or_404(pk, status=Property.Status.PUBLISHED)
    if request.user.role != User.Role.RENTER:
        messages.error(request, "Only home seeker accounts can request property viewings.")
        return redirect("property_detail", pk=pk)
    form = VisitRequestForm(request.POST)
    if form.is_valid():
        try:
            create_visit(
                property_listing.pk,
                request.user.id,
                form.cleaned_data["scheduled_for"],
                form.cleaned_data["message"],
            )
        except ValueError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Visit request sent to the landlord.")
            return redirect("dashboard")
    return _detail_error(request, property_listing, visit_form=form)


@require_login
@require_POST
def visit_request_decide(request, pk):
    visit = get_visit(
        pk, owner_id=request.user.id, status=VisitRequest.Status.REQUESTED
    )
    if visit is None:
        raise Http404
    form = VisitDecisionForm(request.POST)
    if form.is_valid():
        update_visit_status(pk, form.cleaned_data["status"])
        messages.success(request, "The visit request has been updated.")
    else:
        messages.error(request, "Choose a valid decision for this visit request.")
    return redirect("dashboard")


@require_login
@require_POST
def visit_request_cancel(request, pk):
    visit = get_visit(
        pk,
        renter_id=request.user.id,
        status=[VisitRequest.Status.REQUESTED, VisitRequest.Status.CONFIRMED],
    )
    if visit is None:
        raise Http404
    update_visit_status(pk, VisitRequest.Status.CANCELLED)
    messages.success(request, "Your visit request has been cancelled.")
    return redirect("dashboard")


@require_login
@require_POST
def reservation_create(request, pk):
    property_listing = _property_or_404(pk, status=Property.Status.PUBLISHED)
    if request.user.role != User.Role.RENTER:
        messages.error(request, "Only home seeker accounts can book a place.")
        return redirect("property_detail", pk=pk)
    form = ReservationForm(request.POST)
    if form.is_valid():
        try:
            create_reservation(
                property_listing.pk,
                request.user.id,
                form.cleaned_data["start_date"],
                form.cleaned_data["end_date"],
                form.cleaned_data["message"],
            )
        except ValueError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Your booking request was sent to the service provider.")
            return redirect("dashboard")
    return _detail_error(request, property_listing, reservation_form=form)


@require_login
@require_POST
def reservation_decide(request, pk):
    reservation = get_reservation(
        pk, owner_id=request.user.id, status=Reservation.Status.REQUESTED
    )
    if reservation is None:
        raise Http404
    form = ReservationDecisionForm(request.POST)
    if form.is_valid():
        try:
            update_reservation_status(pk, form.cleaned_data["status"])
        except ValueError:
            messages.error(request, "This booking can no longer be confirmed.")
        else:
            messages.success(request, "The booking request has been updated.")
    else:
        messages.error(request, "Choose a valid decision for this booking.")
    return redirect("dashboard")


@require_login
@require_POST
def reservation_cancel(request, pk):
    reservation = get_reservation(
        pk,
        renter_id=request.user.id,
        status=[Reservation.Status.REQUESTED, Reservation.Status.CONFIRMED],
    )
    if reservation is None:
        raise Http404
    update_reservation_status(pk, Reservation.Status.CANCELLED)
    messages.success(request, "Your booking request has been cancelled.")
    return redirect("dashboard")
