# RentHouse

RentHouse is a Django rental and property-management MVP for houses,
apartments, paying-guest accommodation, hostels and rooms. It has two account
roles: **Service provider** (lists rentals) and **Home seeker** (searches and
requests viewings). Providers can publish detailed listings with a cover image
and an eight-photo gallery; seekers can filter, sort and save places, then
request a viewing. The interface uses Tailwind CSS with restrained dark
accents.

See [WORKFLOW.md](WORKFLOW.md) for the key user journeys, workflow rules, and
local run instructions.

## Start locally

Start MongoDB locally, or provide a MongoDB Atlas connection URI. The app uses
`mongodb://localhost:27017` and the `renthouse` database by default. Override
these with environment variables when needed:

```powershell
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DATABASE = "renthouse"
```

Then install dependencies, build the Tailwind stylesheet, and initialize the
database:

```powershell
python -m pip install -r requirements.txt
npm install
npm run css:build
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit `http://127.0.0.1:8000/`. Listings default to draft; select
**Published** when adding or editing a landlord listing to make it searchable.

Run checks and tests with `python manage.py check` and `python manage.py test`.
Run `npm run css:watch` while developing styles. For deployment requirements
and real-world limitations, read `WORKFLOW.md`.
