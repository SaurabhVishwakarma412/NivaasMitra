# RentHouse

RentHouse is a Django rental and property-management MVP for houses,
apartments, paying-guest accommodation, hostels and rooms. It has two account
roles: **Service provider** (lists rentals) and **Home seeker** (searches and
requests viewings and date-based bookings). Providers can publish detailed
listings with a cover image and an eight-photo gallery; seekers can filter,
sort and save places, request a viewing, and submit booking dates. Booking
requests require provider confirmation; online payments are not implemented.
The interface uses Tailwind CSS with restrained dark accents.

See [WORKFLOW.md](WORKFLOW.md) for the key user journeys, workflow rules, and
local run instructions.

## Start locally

Start MongoDB locally, or provide a MongoDB Atlas connection URI. The app uses
`mongodb://localhost:27017` and the `renthouse` database by default. Override
these with environment variables when needed:

```powershell
$env:DJANGO_DEBUG = "1"
$env:DJANGO_SECRET_KEY = "replace-with-a-long-random-secret"
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DATABASE = "renthouse"
```

For production deployments, disable debug mode and set `DJANGO_ALLOWED_HOSTS`,
`DJANGO_SECURE_SSL_REDIRECT`, and a stronger secret key via environment
variables or a `.env` file.

On Windows, use the project's virtual environment for every Python command.
From the repository root in PowerShell, install dependencies and start the app
like this:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
npm run css:build
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py runserver
```

Then visit `http://127.0.0.1:8000/`. Listings default to draft; select
**Published** when adding or editing a landlord listing to make it searchable.

Run checks and tests with `.\venv\Scripts\python.exe manage.py check` and
`.\venv\Scripts\python.exe manage.py test`.
Run `npm run css:watch` while developing styles. For deployment requirements
and real-world limitations, read `WORKFLOW.md`.
