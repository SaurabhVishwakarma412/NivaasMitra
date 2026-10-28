# RentHouse workflow

RentHouse is a Django rental platform using Django's ORM, PostgreSQL, built-in
authentication and sessions, and Tailwind CSS. It has two account roles:
**Service provider** lists rentals, and **Home seeker** searches, requests
viewings, and submits date-based booking requests.

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
│   ├── management/commands/        # One-time MongoDB export importer
│   ├── migrations/                 # Django database migrations
│   ├── models.py                   # Django ORM models and custom user
│   ├── repository.py               # ORM queries and domain operations
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
  use Django password hashers, database-backed sessions, and Django's
  authentication middleware.
- Booking/visit email notifications, payments, identity verification and
  maintenance workflows are not implemented. The contact form sends email
  using the configured mail backend. Configure backups and production security
  before using real customer data.

## Django persistence

Django's ORM stores the custom role-aware user, properties, gallery photos,
saved properties, visits, reservations, and sessions in PostgreSQL. Django
migrations create and evolve the relational schema. Connection values come
from the `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
and `POSTGRES_PORT` variables in `.env`. Uploaded image contents live in
`MEDIA_ROOT`; PostgreSQL stores their relative paths.

To preserve records from the existing SQLite database, migrate the PostgreSQL
schema and run `manage.py import_sqlite_data`. The importer reads `db.sqlite3`
without modifying it, requires the PostgreSQL rentals tables to be empty, and
copies records atomically. See README.md for details.

Existing MongoDB data is not deleted or accessed by the running app. To retain
it, export the six collections as canonical Extended JSON using `mongoexport`,
copy the old media files, and use the `import_mongo_export` management command.
The importer reads exports without a MongoDB Python driver, preserves Django
password hashes and Mongo listing IDs, and leaves the source database intact.
Refer to README.md for the command example.

## How a request works

```text
Browser -> rentals/urls.py -> rentals/views.py -> rentals/forms.py
        -> rentals/repository.py -> Django ORM -> PostgreSQL -> templates/
```

URLs route requests to views. Django middleware authenticates sessions; views
check role and ownership; forms validate submitted data; ORM query helpers
enforce domain rules and read/write relational records; templates render the
response.

## Run and verify locally

From the project folder run:

```powershell
.\venv\Scripts\Activate.ps1
Copy-Item .env.example .env
python -m pip install -r requirements.txt
npm install
npm run css:build
python manage.py migrate
python manage.py runserver
```

Before running migrations, update `POSTGRES_PASSWORD` in `.env` and create the
configured database in PostgreSQL. See README.md for the database setup and
the one-time SQLite data transfer steps.

Open `http://127.0.0.1:8000/` and create accounts through the site. Check the
project with:

```powershell
python manage.py check
python manage.py test
```
