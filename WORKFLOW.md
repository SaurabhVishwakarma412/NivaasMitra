# RentHouse workflow

RentHouse is a Django rental platform using PyMongo for MongoDB document
persistence and Tailwind CSS. It has two account roles: **Service provider**
lists rentals, and **Home seeker** searches, requests viewings, and submits
date-based booking requests.

## Main user journeys

### Service provider

1. Create an account and choose **Service provider**.
2. Add a property with its type, description, rent, location, availability,
   room details and cover photo. Add up to eight gallery photos if needed.
3. Save as a draft, review the details, then publish it to make it searchable.
4. Edit or pause the listing, or archive it when it is no longer available.
5. Review viewing and booking requests; confirm or decline either request.

### Home seeker

1. Browse or search published properties by location, type, rent, bedrooms or
   availability; sort results by date, rent or availability.
2. Open a listing to view its details and photos.
3. Sign in as a **Home seeker** to save properties, request a future viewing,
   or request a booking by selecting check-in and check-out dates.
4. Track viewing and booking statuses on the dashboard; cancel a requested or
   confirmed request when needed.

## Important rules

- Only published properties appear in public search. Providers can manage only
  their own listings and photos.
- Listing states: drafts can be published or archived; published listings can
  be paused or archived; paused listings can be published or archived;
  archived listings return to draft before republishing.
- Viewing states: `Requested -> Confirmed | Declined`; the seeker may cancel
  a requested or confirmed viewing. Completed viewings are not currently
  managed through an in-app staff interface.
- Booking states: `Requested -> Confirmed | Declined`; the seeker may cancel a
  requested or confirmed booking. Requested or confirmed bookings cannot have
  overlapping dates for the same listing.
- A booking request is not a confirmed reservation until the service provider
  approves it. Online payments are not implemented.
- Viewings must be in the future. A seeker cannot request a viewing at their
  own property, and only one requested or confirmed viewing per seeker and
  property is allowed.
- Forms validate user input and image uploads; role and ownership checks
  protect actions. State-changing forms use Django CSRF protection. Accounts
  use Django password hashers and a signed, HTTP-only authentication cookie;
  Django auth tables and sessions are not used.
- Email/SMS notifications, payments, identity verification and maintenance
  workflows are not implemented. Configure backups and production security
  before using real customer data.

## MongoDB persistence

All application records use PyMongo; Django ORM models, auth/session tables,
and relational migrations are not used. The repository stores documents in
these collections:

- `users` — account details and Django-compatible password hashes.
- `properties` — listings, with owner references stored as MongoDB ObjectIds.
- `property_images` — gallery image paths and their listing references.
- `saved_properties` — renter-to-listing references.
- `visit_requests` and `reservations` — requests with references to their
  renter and listing.

Collection indexes are created automatically on first database access.
Uploaded image contents remain in Django's `MEDIA_ROOT`; MongoDB documents
store their paths. User login uses a signed, HTTP-only cookie rather than a
database-backed Django session.

## How a request works

```text
Browser -> rentals/urls.py -> rentals/views.py -> rentals/forms.py
        -> rentals/repository.py -> MongoDB collections -> templates/
```

URLs route requests to views. Views check authentication, role and ownership;
forms validate submitted data; the PyMongo repository reads and writes MongoDB
documents and enforces domain rules; templates render the response.

## Run and verify locally

Start MongoDB, then from the project folder run:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npm run css:build
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and create accounts through the site. The Django
admin is disabled because this project does not use Django ORM models. Check
the project with:

```powershell
python manage.py check
python manage.py test
```

Set `MONGODB_URI` and `MONGODB_DATABASE` to override the local MongoDB defaults.
PyMongo creates the required collection indexes automatically. There is no
`migrate` or `makemigrations` step for application data.
