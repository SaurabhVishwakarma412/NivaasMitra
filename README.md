# RentHouse

RentHouse is a Django rental and property-management application that uses
PyMongo directly to read and write MongoDB documents. Django handles routing,
forms, templates, email, and password hashing; authentication, sessions, users,
properties, saved listings, visits, and bookings are stored in MongoDB.
Property gallery metadata is embedded in each property document.

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
.\venv\Scripts\python.exe manage.py runserver
```

Then visit `http://127.0.0.1:8000/`. Listings default to draft; select
**Published** when adding or editing a landlord listing to make it searchable.
Create user accounts through the signup page. MongoDB stores account, listing,
booking, viewing-request, saved-property, and session documents. Gallery photo
metadata is embedded in the parent listing document. Uploaded image files are
stored under Django's `MEDIA_ROOT`; MongoDB stores their paths. MongoDB
collections and indexes are initialized automatically when the app first
connects; Django migrations are not used.
Users who forget their password can request a time-limited reset link by email
from the login page. In development, reset emails use Django's console backend;
configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`EMAIL_USE_TLS`, and a real `DEFAULT_FROM_EMAIL` in `.env` to deliver them to
inboxes. When `EMAIL_HOST` is set, the app automatically uses SMTP unless
`DJANGO_EMAIL_BACKEND` explicitly overrides it. For Gmail, use an app password,
not your regular account password.

Run checks and tests with `.\venv\Scripts\python.exe manage.py check` and
`.\venv\Scripts\python.exe manage.py test`.
Run `npm run css:watch` while developing styles. For deployment requirements
and real-world limitations, read `WORKFLOW.md`.

## Data and backups

The direct PyMongo layer creates the required indexes on first connection. It
does not import records from `db.sqlite3` or from a different MongoDB schema.
Keep backups of any existing data before changing the configured database or
schema.

## Explaining the NoSQL code

The database calls are in `rentals/repository.py`. For example, listing search
builds a MongoDB filter and passes it to `find()`:

```python
collection.find({
    "status": "published",
    "city": {"$regex": "Pune", "$options": "i"},
})
```

Documents are grouped by collection rather than represented as relational
tables. A property document contains its own details and embeds its gallery:

```javascript
{
  "_id": ObjectId("..."),
  "owner_id": ObjectId("..."),
  "title": "Garden apartment",
  "monthly_rent": Decimal128("25000.00"),
  "status": "published",
  "gallery": [
    {"image_id": "...", "image": "properties/gallery/room.png"}
  ]
}
```

`rentals/validation.py` has both the Python checks used before repository
inserts and MongoDB `$jsonSchema` definitions. `rentals/database.py` installs
those validators with MongoDB's `collMod` command and creates unique/query
indexes. The forms give users readable errors; MongoDB validators also reject
malformed documents if a write bypasses the forms or repository checks.
