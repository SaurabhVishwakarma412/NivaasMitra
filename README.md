# RentHouse

RentHouse is a Django rental and property-management application. Rental data,
accounts, and sessions use Django's ORM, PostgreSQL, and built-in authentication.
MongoDB is not required to run the application. Django migrations manage the
schema, and a one-time management command can import MongoDB Extended JSON
exports without adding a MongoDB driver to the runtime dependencies.

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
Install PostgreSQL and make sure its service is running. Create a database
named `nivaasmitra` (or choose another name), copy `.env.example` to `.env`,
and set `POSTGRES_PASSWORD` to the password for your PostgreSQL user. Django
loads values from `.env`. Install dependencies and start the app from
PowerShell:

```powershell
Copy-Item .env.example .env
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
npm run css:build
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

For a local PostgreSQL installation, create the database once in `psql` or
pgAdmin:

```sql
CREATE DATABASE nivaasmitra;
```

Then visit `http://127.0.0.1:8000/`. Listings default to draft; select
**Published** when adding or editing a landlord listing to make it searchable.
Create user accounts through the signup page. Django's standard
authentication/session system is enabled. PostgreSQL stores user, listing,
booking, viewing-request, and session records. Uploaded image files are stored
under Django's `MEDIA_ROOT`; PostgreSQL stores their paths.

Run checks and tests with `.\venv\Scripts\python.exe manage.py check` and
`.\venv\Scripts\python.exe manage.py test`.
Run `npm run css:watch` while developing styles. For deployment requirements
and real-world limitations, read `WORKFLOW.md`.

## Move existing SQLite data to PostgreSQL

The existing `db.sqlite3` is not deleted or changed by switching the app's
database setting. Once PostgreSQL is configured and the schema is migrated,
copy its rental records into PostgreSQL with:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py import_sqlite_data
```

The importer copies users, listings, gallery-image paths, saved listings,
viewing requests, and bookings into an empty PostgreSQL app schema in one
transaction. It does not modify `db.sqlite3`; keep that file as a backup until
you confirm the imported records in pgAdmin. Uploaded image files remain in
`media/`; PostgreSQL stores their relative paths.

## Import existing MongoDB data (optional, one time)

The application no longer connects to MongoDB. To retain existing data, create
canonical Extended JSON exports for `users`, `properties`, `property_images`,
`saved_properties`, `visit_requests`, and `reservations` using `mongoexport`.
Keep the original MongoDB database unchanged as a backup. With MongoDB
Database Tools installed, export every collection from PowerShell:

```powershell
$database = "renthouse"
$collections = @("users", "properties", "property_images", "saved_properties", "visit_requests", "reservations")
New-Item -ItemType Directory -Force .\mongo-export | Out-Null
foreach ($collection in $collections) {
  mongoexport --uri $env:MONGODB_URI --db $database --collection $collection --jsonFormat=canonical --out ".\mongo-export\$collection.json"
  if ($LASTEXITCODE -ne 0) { throw "Export failed for $collection" }
}
```

Copy the old media directory or provide it as `--media-source`, then run:

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py import_mongo_export `
  --directory .\mongo-export `
  --media-source .\old-media
```

The importer reads JSON export files only, preserves account password hashes,
listing IDs, request history, and media paths, and wraps database changes in a
transaction. It does not modify MongoDB. See `python manage.py
import_mongo_export --help` for arguments.
