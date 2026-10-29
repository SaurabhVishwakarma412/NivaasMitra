# RentHouse workflow

RentHouse is a Django rental platform using direct PyMongo access to MongoDB,
MongoDB-backed authentication sessions, and Tailwind CSS. It has two account
roles: **Service provider** lists rentals, and **Home seeker** searches,
requests viewings, and submits date-based booking requests.

## Project structure

```text
NivaasMitra/
├── config/                         # Django project configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py                  # Settings, middleware, and installed apps
│   ├── urls.py                      # Root URL routes
│   └── wsgi.py
├── rentals/                        # Main rental application
│   ├── __init__.py
│   ├── apps.py
│   ├── forms.py                    # Form definitions and input validation
│   ├── models.py                   # Lightweight domain objects
│   ├── database.py                 # PyMongo client, collections, and indexes
│   ├── repository.py               # Direct PyMongo queries and domain operations
│   ├── sessions.py                 # MongoDB-backed Django session store
│   ├── middleware.py               # Mongo-backed authentication
│   ├── validation.py               # Insert validation and MongoDB JSON Schemas
│   ├── tests.py                    # Application tests
│   ├── urls.py                     # Rental app URL routes
│   └── views.py                    # Request handlers
├── static/
│   └── rentals/                    # Front-end assets
│       ├── hero-bg.jpg
│       ├── hero1-bg.jpg
│       ├── input.css               # Tailwind CSS source
│       ├── site.css                # Compiled stylesheet
│       └── site.js                 # Browser-side interactions
├── templates/
│   ├── registration/               # Account pages
│   │   ├── login.html              # User sign-in form
│   │   └── signup.html             # Account registration and role selection
│   ├── rentals/                    # Rental and informational pages
│   │   ├── about.html              # About page
│   │   ├── contact.html            # Contact form and support information
│   │   ├── dashboard.html          # User dashboard for listings and saved places
│   │   ├── hero.html               # Landing-page hero section
│   │   ├── home.html               # Home page with property search and results
│   │   ├── listings.html           # Browse all available properties
│   │   ├── property_detail.html    # Property details, photos, and requests
│   │   └── property_form.html      # Create or edit a property listing
│   └── base.html                   # Shared layout, navigation, and content blocks
├── .env.example                    # Example environment configuration
├── .gitignore
├── manage.py                       # Django management entry point
├── package.json                    # Tailwind CSS scripts and dependencies
├── package-lock.json
├── requirements.txt                # Python dependencies
├── README.md                       # Project overview and setup
└── WORKFLOW.md                     # User journeys and workflow rules
```

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

### Account recovery

1. Select **Forgot your password?** on the login page and enter the account
   email address.
2. Follow the emailed, time-limited reset link to choose a new password of at
   least eight characters.

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
  use Django password hashers, PyMongo-backed sessions, and custom
  PyMongo-backed authentication middleware.
- Booking/visit email notifications, payments, identity verification and
  maintenance workflows are not implemented. The contact form sends email
  using the configured mail backend. Configure backups and production security
  before using real customer data.

## MongoDB document model

The app's `rentals/repository.py` module contains direct PyMongo queries.
Property gallery photos are embedded in each property document; accounts,
saved properties, visits, reservations, and sessions are separate documents.
Image files are stored under `MEDIA_ROOT`, while MongoDB stores their relative
paths. Connection settings come from `MONGODB_URI` and `MONGODB_NAME` in `.env`.
Required indexes are created automatically when the app first connects. Django
migrations are not used; existing MongoDB documents must match the repository's
document schema. Python validation runs before repository writes, and
MongoDB `$jsonSchema` collection validators independently enforce document
fields, types, allowed status values, and gallery size at the database.

For example, `repository.py` searches with a MongoDB filter:

```python
collection.find({
    "status": "published",
    "city": {"$regex": "Pune", "$options": "i"},
})
```

A property is one document with embedded gallery metadata; related accounts,
saved properties, visits, bookings, and sessions use their own collections.
This keeps common property details and gallery reads together while preserving
separate request and account lifecycles.

## How a request works

```text
Browser -> rentals/urls.py -> rentals/views.py -> rentals/forms.py
        -> rentals/repository.py -> PyMongo -> MongoDB -> templates/
```

URLs route requests to views. Middleware loads MongoDB-backed sessions and
accounts; views check role and ownership; forms validate submitted data;
repository helpers enforce domain rules and query MongoDB documents directly;
templates render the response.

## Run and verify locally

From the project folder run:

```powershell
.\venv\Scripts\Activate.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m pip install -r requirements.txt
npm install
npm run css:build
python manage.py runserver
```

Configure `MONGODB_URI` and `MONGODB_NAME` in `.env` for a running MongoDB
deployment. See README.md for setup details.

Open `http://127.0.0.1:8000/` and create accounts through the site. Check the
project with:

```powershell
python manage.py check
python manage.py test
```

rentals/repository.py — the main file for direct PyMongo queries and inserts.
rentals/database.py — connects to MongoDB and sets up collection validators and indexes.
rentals/validation.py — basic validation rules and MongoDB document schemas.
rentals/sessions.py — reads and writes sessions in MongoDB.
config/settings.py — MongoDB connection settings, including database name and URI.
rentals/forms.py — validates submitted form data before it reaches the
