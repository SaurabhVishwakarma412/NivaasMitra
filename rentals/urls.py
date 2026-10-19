from django.urls import path

from . import views

urlpatterns = [
    path("listings/", views.listings, name="listings"),
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("accounts/signup/", views.sign_up, name="signup"),
    path(
        "accounts/login/",
        views.login_view,
        name="login",
    ),
    path(
        "accounts/logout/",
        views.logout_view,
        name="logout",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("properties/new/", views.property_create, name="property_create"),
    path("properties/<str:pk>/", views.property_detail, name="property_detail"),
    path("properties/<str:pk>/edit/", views.property_edit, name="property_edit"),
    path(
        "properties/<str:pk>/status/",
        views.property_status_update,
        name="property_status_update",
    ),
    path(
        "properties/<str:pk>/photos/<str:image_pk>/delete/",
        views.property_image_delete,
        name="property_image_delete",
    ),
    path(
        "properties/<str:pk>/save/",
        views.saved_property_toggle,
        name="saved_property_toggle",
    ),
    path(
        "properties/<str:pk>/visit/",
        views.visit_request_create,
        name="visit_request_create",
    ),
    path(
        "visits/<str:pk>/decision/",
        views.visit_request_decide,
        name="visit_request_decide",
    ),
    path(
        "visits/<str:pk>/cancel/",
        views.visit_request_cancel,
        name="visit_request_cancel",
    ),
    path(
        "properties/<str:pk>/book/",
        views.reservation_create,
        name="reservation_create",
    ),
    path(
        "bookings/<str:pk>/decision/",
        views.reservation_decide,
        name="reservation_decide",
    ),
    path(
        "bookings/<str:pk>/cancel/",
        views.reservation_cancel,
        name="reservation_cancel",
    ),
]
