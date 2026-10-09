# RentHouse workflow

RentHouse is a Django rental platform using MongoDB and Tailwind CSS. It has
two account roles: **Service provider** lists rentals, and **Home seeker**
searches, requests viewings, and submits date-based booking requests.

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
  a requested or confirmed viewing. Completed viewings are staff-managed in
  this MVP.
- Booking states: `Requested -> Confirmed | Declined`; the seeker may cancel a
  requested or confirmed booking. Requested or confirmed bookings cannot have
  overlapping dates for the same listing.
- A booking request is not a confirmed reservation until the service provider
  approves it. Online payments are not implemented.
- Viewings must be in the future. A seeker cannot request a viewing at their
  own property, and only one requested or confirmed viewing per seeker and
  property is allowed.
- Forms validate user input and image uploads; role and ownership checks
  protect actions. State-changing forms use Django CSRF protection.
- Email/SMS notifications, payments, identity verification and maintenance
  workflows are not implemented. Configure backups and production security
  before using real customer data.

## How a request works

```text
Browser -> rentals/urls.py -> rentals/views.py -> rentals/forms.py
        -> rentals/models.py / MongoDB -> templates/ -> user message
```

URLs route requests to views. Views check authentication, role and ownership;
forms validate submitted data; models enforce domain rules and database
constraints; templates render the response.

## Run and verify locally

Start MongoDB, then from the project folder run:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npm run css:build
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Create accounts through the site; trusted
operators use `/admin/`. Check the project with:

```powershell
python manage.py check
python manage.py test
```

Set `MONGODB_URI` and `MONGODB_DATABASE` to override the local MongoDB defaults.
When models change, generate and commit migrations with
`python manage.py makemigrations`. Keep the MongoDB-specific contrib
migrations in `mongo_migrations/`.
