from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from config import (
    TASSO_BASE_URL,
    JOTFORM_WEBHOOK_SECRET,
    TASSO_USERNAME,
    TASSO_SECRET,
    GLP1_PROJECT_ID,
    TESTOSTRONE_PROJECT_ID,
)

import traceback
import json
import re
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------
# US State Code Lookup
# -----------------------------------------------
US_STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}

# Lowercase keys for case-insensitive full-name lookup (fixes "TEXAS" rejection)
_STATE_LOWER = {k.lower(): v for k, v in US_STATE_CODES.items()}
# Set of valid 2-letter abbreviations for quick validation
_VALID_ABBREVS = set(US_STATE_CODES.values())

# -----------------------------------------------
# Token Cache
# API token TTL is 8 hours; cache for 7 to avoid expiry mid-request.
# The API docs explicitly warn: do NOT request a new token on every call.
# -----------------------------------------------
_token_cache: dict = {"value": None, "fetched_at": 0.0}
_TOKEN_VALID_SECONDS = 7 * 3600


# -----------------------------------------------
# Data Normalization Helpers
# -----------------------------------------------

def normalize_name(raw: str) -> str:
    """Strip extra whitespace and title-case a name.
    Handles ALL CAPS ('JOHN'), all lowercase ('john'), and padded inputs (' John  ').
    """
    if not raw:
        return ""
    return " ".join(raw.split()).title()


def normalize_state(raw: str):
    """Return a 2-letter state code, or None if unrecognizable.

    Handles:
    - Any case for full names: 'TEXAS', 'texas', 'Texas' → 'TX'
    - Any case for abbreviations: 'tx', 'TX', 'Tx' → 'TX'
    - Multi-word states: 'NEW YORK', 'new york', 'New York' → 'NY'
    - Extra whitespace: '  Texas  ' → 'TX'
    """
    if not raw:
        return None
    s = raw.strip()
    if len(s) == 2:
        upper = s.upper()
        return upper if upper in _VALID_ABBREVS else None
    return _STATE_LOWER.get(s.lower())


def normalize_email(raw: str):
    """Lowercase, strip, and validate basic email format. Returns None if invalid."""
    if not raw:
        return None
    email = raw.strip().lower()
    if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', email):
        return email
    return None


def normalize_phone(area: str, phone: str):
    """Extract digits, return US format '1XXXXXXXXXX' or None if not a valid US number."""
    digits = "".join(c for c in f"{area}{phone}" if c.isdigit())
    if len(digits) == 10:
        return "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    return None


def normalize_postal(raw: str) -> str:
    """Extract numeric digits and return a 5-digit ZIP. Returns '00000' if unresolvable."""
    if not raw:
        return "00000"
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) >= 5:
        return digits[:5]
    return "00000"


def normalize_address_line(raw: str) -> str:
    """Collapse runs of whitespace into single spaces."""
    if not raw:
        return ""
    return " ".join(raw.split())


def normalize_dob(year: str, month: str, day: str) -> str:
    """Validate date components and return 'YYYY-MM-DD'. Raises ValueError if invalid."""
    if not (year and month and day):
        raise ValueError("Date of Birth is incomplete — year, month, and day are all required")
    try:
        y, m, d = int(year), int(month), int(day)
    except (TypeError, ValueError):
        raise ValueError(f"Date of Birth contains non-numeric values: {year}-{month}-{day}")
    if not (1900 <= y <= 2100):
        raise ValueError(f"Date of Birth year out of range: {y}")
    if not (1 <= m <= 12):
        raise ValueError(f"Date of Birth month out of range: {m}")
    if not (1 <= d <= 31):
        raise ValueError(f"Date of Birth day out of range: {d}")
    return f"{y:04d}-{m:02d}-{d:02d}"


def normalize_gender(raw: str):
    """Map common gender inputs to Tasso's (gender, assignedSex) tuple.

    Tasso accepted values:
      gender:      cisMale | cisFemale | unspecified
      assignedSex: male    | female    | unknown
    """
    gender_map = {
        "male":      ("cisMale",   "male"),
        "m":         ("cisMale",   "male"),
        "man":       ("cisMale",   "male"),
        "cismale":   ("cisMale",   "male"),
        "female":    ("cisFemale", "female"),
        "f":         ("cisFemale", "female"),
        "woman":     ("cisFemale", "female"),
        "cisfemale": ("cisFemale", "female"),
    }
    key = raw.strip().lower().replace(" ", "") if raw else ""
    return gender_map.get(key, ("unspecified", "unknown"))


def normalize_race(raw: str) -> str:
    """Map common race inputs to Tasso's accepted enum values.

    Tasso accepted values:
      American Indian or Alaska Native | Asian | Black or African American |
      Native Hawaiian or Other Pacific Islander | Hispanic or Latino | White | Other
    """
    race_map = {
        "american indian or alaska native":           "American Indian or Alaska Native",
        "american indian":                            "American Indian or Alaska Native",
        "alaska native":                              "American Indian or Alaska Native",
        "native american":                            "American Indian or Alaska Native",
        "asian":                                      "Asian",
        "black or african american":                  "Black or African American",
        "black":                                      "Black or African American",
        "african american":                           "Black or African American",
        "native hawaiian or other pacific islander":  "Native Hawaiian or Other Pacific Islander",
        "native hawaiian":                            "Native Hawaiian or Other Pacific Islander",
        "pacific islander":                           "Native Hawaiian or Other Pacific Islander",
        "hispanic or latino":                         "Hispanic or Latino",
        "hispanic":                                   "Hispanic or Latino",
        "latino":                                     "Hispanic or Latino",
        "latina":                                     "Hispanic or Latino",
        "latinx":                                     "Hispanic or Latino",
        "white":                                      "White",
        "caucasian":                                  "White",
        "other":                                      "Other",
        "prefer not to say":                          "Other",
        "prefer not to answer":                       "Other",
        "unknown":                                    "Other",
    }
    if not raw or not isinstance(raw, str):
        return "Other"
    return race_map.get(raw.strip().lower(), "Other")


# -----------------------------------------------
# Tasso API Helpers
# -----------------------------------------------

def get_tasso_token(force_refresh: bool = False) -> str:
    now = time.time()
    if (
        not force_refresh
        and _token_cache["value"]
        and (now - _token_cache["fetched_at"]) < _TOKEN_VALID_SECONDS
    ):
        return _token_cache["value"]

    url = f"{TASSO_BASE_URL}/authTokens"
    payload = {"username": TASSO_USERNAME, "secret": TASSO_SECRET}
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print("AUTH RESPONSE:", response.text)

    data = response.json()
    if "results" not in data or "idToken" not in data["results"]:
        raise Exception(f"Tasso auth failed: {response.text}")

    token = data["results"]["idToken"]
    _token_cache["value"] = token
    _token_cache["fetched_at"] = now
    return token


def create_tasso_patient(token: str, patient: dict) -> dict:
    url = f"{TASSO_BASE_URL}/patients"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(url, json=patient, headers=headers, timeout=10)
    if response.status_code not in (200, 201):
        raise Exception(f"Tasso patient creation failed {response.status_code}: {response.text}")
    return response.json()


def create_tasso_order(token: str, order: dict) -> dict:
    url = f"{TASSO_BASE_URL}/orders"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(url, json=order, headers=headers, timeout=10)
    if response.status_code not in (200, 201):
        raise Exception(f"Tasso order creation failed {response.status_code}: {response.text}")
    return response.json()


# -----------------------------------------
# Webhook Endpoint (Triggered by Jotform)
# -----------------------------------------
# @app.post("/webhooks/jotform/tasso")
# async def jotform_webhook(request: Request):

#     US_STATE_CODES = {
#         "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
#         "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
#         "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
#         "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
#         "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
#         "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
#         "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
#         "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
#         "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
#         "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
#         "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
#         "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
#         "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC"
#     }

#     try:
#         form = await request.form()

#         raw = form.get("rawRequest")
#         data = json.loads(raw)

#         print("PARSED RAW:", data)
#         name = data.get("q3_name", {})
#         dob = data.get("q16_dateOf", {})
#         phone = data.get("q6_phoneNumber", {})
#         digits = f"{phone.get('area','')}{phone.get('phone','')}"

#         # keep only digits
#         digits = "".join([c for c in digits if c.isdigit()])

#         path = data.get("path", "")
#         if path == "/submit/242116255933151":
#             project_id = GLP1_PROJECT_ID
#         elif path == "/submit/242115439242147":
#             project_id = TESTOSTRONE_PROJECT_ID
#         else:
#             project_id = GLP1_PROJECT_ID

#         # If 10 digits, assume US and add +1
#         if len(digits) == 10:
#     # US local number
#             formatted_phone = "1" + digits          # 18632756381
#         elif len(digits) == 11 and digits.startswith("1"):
#             # Already has country code
#             formatted_phone = digits                # 18632756381
#         else:
#             formatted_phone = None                  # invalid

#         if formatted_phone:
#             contact = {
#                 "email": data.get("q4_email"),
#                 "phoneNumber": formatted_phone,
#               }
#         else:
#             contact = {
#                 "email": data.get("q4_email"),
#             }

#         addr = data.get("q5_shippingAddress", {})
#         raw_id = data.get("event_id", "unknown")
#         safe_id = raw_id.replace("_", "-")
#         jot_gender = data.get("q15_gender", "").lower()
#         postal = addr.get("postal")

#         if not postal:
#             postal = "00000"   # or skip field if allowed

#         gender_map = {
#             "male": "cisMale",
#             "female": "cisFemale",
#         }
#         tasso_gender = gender_map.get(jot_gender, "unspecified")

#         sex_map = {
#             "male": "male",
#             "female": "female"
#         }
#         tasso_sex = sex_map.get(jot_gender, "unknown")

#         addr = data.get("q5_shippingAddress", {})

#         address1 = addr.get("addr_line1") or "Unknown"
#         if addr.get("addr_line2") == '':
#             address2 = "Unknown"
#         else:
#             address2 = addr.get("addr_line2")
#         city = addr.get("city") or "Unknown"
#         state = addr.get("state") or "Unknown"
#         postal = addr.get("postal") or "00000"
#         if len(state) == 2:
#             state_code = state
#         else:
#             state_code = US_STATE_CODES.get(state, "Unknown")

#         normalized_address = {
#             "address1": address1,
#             "address2": address2,
#             "city": city,
#             "district1": state_code,
#             "postalCode": postal,
#             "country": "US"
#             # "address1": "1631 15th Ave W",
#             # "address2": "Suite 105",
#             # "city": "Seattle",
#             # "district1": "WA",
#             # "postalCode": "98119",
#             # "country": "US"
#         }

#         patient_payload = {
#             "projectId": project_id,
#             "subjectId": "AUTO-" + safe_id,
#             "firstName": name.get("first"),
#             "lastName": name.get("last"),
#             "shippingAddress": normalized_address,
#             "contactInformation": contact,
#             "dateOfBirth": f"{dob.get('year')}-{dob.get('month')}-{dob.get('day')}",
#             "gender": tasso_gender,
#             "assignedSex": tasso_sex,
#             "race": data.get("q17_race"),
#             "smsConsent": False
#         }


#         print("PATIENT PAYLOAD:", patient_payload)

#         if not patient_payload["firstName"] or not patient_payload["lastName"]:
#             raise ValueError("Missing patient name")

#         token = get_tasso_token()
#         tasso_patient = create_tasso_patient(token, patient_payload)

#         return {
#             "status": "success",
#             "tasso_patient_id": tasso_patient["results"]["id"]
#         }

#     except Exception as e:
#         print("ERROR STACKTRACE:")
#         print(traceback.format_exc())
#         raise HTTPException(status_code=500, detail=str(e))


# # -----------------------------------------
# # API Endpoint: Create Order for Patient
# # -----------------------------------------
# @app.post("/orders/create")
# async def create_order(request: Request):
#     """
#     Create an order for a patient's kit in Tasso.

#     Expected JSON payload:
#     {
#         "patientId": "e3bb6a15-e19e-47f2-b484-87939cae395f",
#         "configurationId": "fOsd_k9GQ3",
#         "npi": {
#             "id": "1234509876",
#             "firstName": "Marcy",
#             "lastName": "Frank"
#         },
#         "containerIdentifier": "0000000176",  // Optional
#         "shipByDate": "2021-10-18",  // Optional, format: YYYY-MM-DD
#         "customAttributes": [  // Optional
#             {
#                 "name": "attrib1",
#                 "value": "a str"
#             }
#         ]
#     }
#     """
#     try:
#         body = await request.json()

#         # Validate required fields
#         patient_id = body.get("patientId")
#         configuration_id = body.get("configurationId")
#         npi = body.get("npi")

#         if not patient_id:
#             raise ValueError("patientId is required")
#         if not npi or not npi.get("id"):
#             raise ValueError("npi information is required")

#         # Build order payload
#         order_payload = {
#             "patientId": patient_id,
#             "provider": {
#                 "npi": {
#                     "id": npi.get("id"),
#                     "firstName": npi.get("firstName"),
#                     "lastName": npi.get("lastName")
#                 }
#             }
#         }


#         # Remove empty provider names
#         npi_obj = order_payload["provider"]["npi"]
#         if not npi_obj.get("firstName"):
#             npi_obj.pop("firstName", None)
#         if not npi_obj.get("lastName"):
#             npi_obj.pop("lastName", None)

#         # Add optional specimens if provided
#         container_identifier = body.get("containerIdentifier")
#         if container_identifier:
#             order_payload["specimens"] = [
#                 {
#                     "containerIdentifier": container_identifier
#                 }
#             ]

#         # Add optional timing if provided
#         ship_by_date = body.get("shipByDate")
#         if ship_by_date:
#             order_payload["timing"] = {
#                 "shipByDate": ship_by_date
#             }

#         # Add optional custom attributes if provided
#         custom_attributes = body.get("customAttributes")
#         if custom_attributes:
#             order_payload["customAttributes"] = custom_attributes

#         print("ORDER PAYLOAD:", order_payload)

#         # Get authentication token
#         token = get_tasso_token()

#         # Create the order
#         tasso_order = create_tasso_order(token, order_payload)

#         return {
#             "status": "success",
#             "order": tasso_order.get("results", tasso_order)
#         }

#     except ValueError as ve:
#         print(f"Validation Error: {str(ve)}")
#         raise HTTPException(status_code=400, detail=str(ve))
#     except Exception as e:
#         print("ERROR STACKTRACE:")
#         print(traceback.format_exc())
#         raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------
# Combined Endpoint: Create Patient + Order
# -----------------------------------------
@app.post("/webhooks/jotform/tasso")
async def jotform_webhook_with_order(request: Request):
    try:
        form = await request.form()
        raw = form.get("rawRequest")
        data = json.loads(raw)

        print("PARSED RAW:", data)

        # ── Project routing ──────────────────────────────────────────────
        path = data.get("path", "")
        if path == "/submit/242115439242147":
            project_id = TESTOSTRONE_PROJECT_ID
        else:
            project_id = GLP1_PROJECT_ID

        # ── Name ─────────────────────────────────────────────────────────
        name = data.get("q3_name", {})
        first_name = normalize_name(name.get("first", ""))
        last_name = normalize_name(name.get("last", ""))
        if not first_name or not last_name:
            raise ValueError("Missing patient first or last name")

        # ── Date of Birth ────────────────────────────────────────────────
        dob = data.get("q16_dateOf", {})
        date_of_birth = normalize_dob(
            dob.get("year", ""), dob.get("month", ""), dob.get("day", "")
        )

        # ── Phone ─────────────────────────────────────────────────────────
        phone_raw = data.get("q6_phoneNumber", {})
        formatted_phone = normalize_phone(
            phone_raw.get("area", ""), phone_raw.get("phone", "")
        )
        if not formatted_phone:
            print(f"WARNING: could not normalize phone '{phone_raw}'")

        # ── Email ─────────────────────────────────────────────────────────
        email = normalize_email(data.get("q4_email", ""))
        if not email:
            print(f"WARNING: invalid or missing email '{data.get('q4_email')}'")

        # ── Address ───────────────────────────────────────────────────────
        addr = data.get("q5_shippingAddress", {})

        address1 = normalize_address_line(addr.get("addr_line1", "")) or "Unknown"
        address2 = normalize_address_line(addr.get("addr_line2", ""))  # omit if blank
        city = normalize_address_line(addr.get("city", "")) or "Unknown"
        postal = normalize_postal(addr.get("postal", ""))

        state_code = normalize_state(addr.get("state", ""))
        if not state_code:
            print(f"WARNING: unrecognized state '{addr.get('state')}' — defaulting to 'Unknown'")
            state_code = "Unknown"

        normalized_address = {
            "address1": address1,
            "address2": address2 if address2 else "Unknown",
            "city": city,
            "district1": state_code,
            "postalCode": postal,
            "country": "US",
        }

        # ── Gender / Sex ─────────────────────────────────────────────────
        tasso_gender, tasso_sex = normalize_gender(data.get("q15_gender", ""))

        # ── Race ─────────────────────────────────────────────────────────
        tasso_race = normalize_race(data.get("q17_race", ""))

        # ── Subject ID ───────────────────────────────────────────────────
        safe_id = data.get("event_id", "unknown").replace("_", "-")

        # ── Build patient payload ─────────────────────────────────────────
        contact = {"email": email} if email else {}
        if formatted_phone:
            contact["phoneNumber"] = formatted_phone

        patient_payload = {
            "projectId": project_id,
            "subjectId": "AUTO-" + safe_id,
            "firstName": first_name,
            "lastName": last_name,
            "shippingAddress": normalized_address,
            "contactInformation": contact,
            "dateOfBirth": date_of_birth,
            "gender": tasso_gender,
            "assignedSex": tasso_sex,
            "race": tasso_race,
            "smsConsent": False,
        }

        print("PATIENT PAYLOAD:", patient_payload)

        # ── Submit to Tasso ───────────────────────────────────────────────
        token = get_tasso_token()

        tasso_patient = create_tasso_patient(token, patient_payload)
        patient_id = tasso_patient["results"]["id"]
        print(f"Patient created: {patient_id}")

        order_payload = {"patientId": patient_id}
        print("ORDER PAYLOAD:", order_payload)

        tasso_order = create_tasso_order(token, order_payload)
        print("ORDER RESPONSE:", tasso_order)

        order_id = tasso_order.get("results", {}).get("id")

        return {
            "status": "success",
            "tasso_patient_id": patient_id,
            "tasso_order_id": order_id,
        }

    except ValueError as ve:
        print(f"VALIDATION ERROR: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        print("ERROR STACKTRACE:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
