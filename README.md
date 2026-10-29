# RentHouse

RentHouse is a Django rental and property-management application backed by
MongoDB through MongoDB's official Django backend. Property gallery photos are
embedded in their property documents; users, saved properties, visits, bookings,
and sessions are stored as MongoDB documents and managed with Django's ORM and
built-in authentication.

RentHouse supports houses, apartments, paying-guest accommodation, hostels and
rooms. It has two account roles: **Service provider** (lists rentals) and
**Home seeker** (searches and requests viewings and date-based bookings).
Providers can publish detailed listings with a cover image and an eight-photo
gallery; seekers can filter, sort and save places, request a viewing, and
submit booking dates. Booking requests require provider confirmation; online
payments are not implemented. The interface uses Tailwind CSS with restrained
dark accents.

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
│   ├── models.py                   # Django ORM models and custom user
│   ├── repository.py               # ORM queries and domain operations
│   ├── tests.py                    # Application tests
│   ├── urls.py                     # Rental app URL routes
│   └── views.py                    # Request handlers
├── mongo_migrations/               # MongoDB-compatible Django migrations
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
│   │   ├── _empty.html             # Shared empty-state component
│   │   ├── _filter_bar.html        # Listing search and filters
│   │   ├── _pagination.html        # Listing pagination
│   │   ├── _property_card.html     # Shared listing card
│   │   ├── _request_list.html      # Shared booking and visit request list
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

See [WORKFLOW.md](WORKFLOW.md) for the key user journeys, workflow rules, and
local run instructions.

## Start locally

For production deployments, disable debug mode and set `DJANGO_ALLOWED_HOSTS`,
`DJANGO_SECURE_SSL_REDIRECT`, a stronger secret key, and SMTP settings via
environment variables or a `.env` file. Set `CONTACT_EMAIL` to the support
inbox and `DEFAULT_FROM_EMAIL` to a sender address accepted by your mail
provider. While `DEBUG` is enabled, contact messages are printed by Django's
console email backend.

On Windows, use the project's virtual environment for every Python command.
Start MongoDB locally or create a MongoDB Atlas deployment, copy
`.env.example` to `.env`, and set `MONGODB_URI` and `MONGODB_NAME` for your
deployment. Django loads values from `.env`. Install dependencies and start
the app from PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
npm run css:build
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

Then visit `http://127.0.0.1:8000/`. Listings default to draft; select
**Published** when adding or editing a landlord listing to make it searchable.
Create user accounts through the signup page. Django's standard
authentication/session system is enabled. MongoDB stores account, listing,
booking, viewing-request, saved-property, and session documents. Gallery photo
metadata is embedded in the parent listing document. Uploaded image files are
stored under Django's `MEDIA_ROOT`; MongoDB stores their paths.

Run checks and tests with `.\venv\Scripts\python.exe manage.py check` and
`.\venv\Scripts\python.exe manage.py test`.
Run `npm run css:watch` while developing styles. For deployment requirements
and real-world limitations, read `WORKFLOW.md`.

## Data and backups

`manage.py migrate` creates or updates the collections and indexes used by
this application. It does not import records from `db.sqlite3` or from a
different MongoDB schema. Keep backups of any existing data before changing
the configured database or applying schema changes. The SQLite file is left
untouched.
