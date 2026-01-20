from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from config import (
    TASSO_BASE_URL,
    JOTFORM_WEBHOOK_SECRET,
    TASSO_USERNAME,
    TASSO_SECRET,
    TASSO_PROJECT_ID)

from fastapi import Form
import traceback
import json

app = FastAPI()

# -------------------------------
# Enable CORS for all origins
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Helper: Authenticate with Tasso
# -------------------------------
def get_tasso_token() -> str:
    url = f"{TASSO_BASE_URL}/authTokens"

    payload = {
        "username": f"{TASSO_USERNAME}",
        "secret":   f"{TASSO_SECRET}"
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print('---------------')
    print(response.text)

    # if response.status_code != 200:
    #     raise Exception(f"Tasso auth failed: {response.text}")
    
    data = response.json()
    if "results" not in data or "idToken" not in data["results"]:
        raise Exception(f"Unexpected response format: {response.text}")

    return data["results"]["idToken"]

# -------------------------------
# Helper: Create Patient in Tasso
# -------------------------------
def create_tasso_patient(token: str, patient: dict) -> dict:
    url = f"{TASSO_BASE_URL}/patients"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=patient, headers=headers, timeout=10)

    if response.status_code not in (200, 201):
        raise Exception(response.text)

    return response.json()

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
        "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC"
    }


# -----------------------------------------
# Webhook Endpoint (Triggered by Jotform)
# -----------------------------------------
@app.post("/webhooks/jotform/tasso")
async def jotform_webhook(request: Request):
    try:
        form = await request.form()

        raw = form.get("rawRequest")
        data = json.loads(raw)

        print("PARSED RAW:", data)
        name = data.get("q3_name", {})
        dob = data.get("q16_dateOf", {})
        phone = data.get("q6_phoneNumber", {})
        digits = f"{phone.get('area','')}{phone.get('phone','')}"

        # keep only digits
        digits = "".join([c for c in digits if c.isdigit()])

        # If 10 digits, assume US and add +1
        if len(digits) == 10:
    # US local number
            formatted_phone = "1" + digits          # 18632756381
        elif len(digits) == 11 and digits.startswith("1"):
            # Already has country code
            formatted_phone = digits                # 18632756381
        else:
            formatted_phone = None                  # invalid

        if formatted_phone:
            contact = {
                "email": data.get("q4_email"),
                "phoneNumber": formatted_phone,
              }
        else:
            contact = {
                "email": data.get("q4_email"),
            }    

        addr = data.get("q5_shippingAddress", {})
        raw_id = data.get("event_id", "unknown")
        safe_id = raw_id.replace("_", "-")
        jot_gender = data.get("q15_gender", "").lower()
        postal = addr.get("postal")

        if not postal:
            postal = "00000"   # or skip field if allowed

        gender_map = {
            "male": "cisMale",
            "female": "cisFemale",
        }
        tasso_gender = gender_map.get(jot_gender, "unspecified")

        sex_map = {
            "male": "male",
            "female": "female"
        }
        tasso_sex = sex_map.get(jot_gender, "unknown")

        addr = data.get("q5_shippingAddress", {})

        address1 = addr.get("addr_line1") or "Unknown"
        if addr.get("addr_line2") == '':
            address2 = "Unknown"
        else:
            address2 = addr.get("addr_line2")
        city = addr.get("city") or "Unknown"
        state = addr.get("state") or "Unknown"
        postal = addr.get("postal") or "00000"
        state_code = US_STATE_CODES.get(state, "Unknown")

        normalized_address = {
            "address1": address1,
            "address2": address2,
            "city": city,
            "district1": state_code,
            "postalCode": postal,
            "country": "US"
        }

        patient_payload = {
            "projectId": TASSO_PROJECT_ID,
            "subjectId": "AUTO-" + safe_id,
            "firstName": name.get("first"),
            "lastName": name.get("last"),
            "shippingAddress": normalized_address,
            "contactInformation": contact,
            "dateOfBirth": f"{dob.get('year')}-{dob.get('month')}-{dob.get('day')}",
            "gender": tasso_gender,
            "assignedSex": tasso_sex,
            "race": data.get("q17_race"),
            "smsConsent": False
        }


        print("PATIENT PAYLOAD:", patient_payload)

        if not patient_payload["firstName"] or not patient_payload["lastName"]:
            raise ValueError("Missing patient name")

        token = get_tasso_token()
        tasso_patient = create_tasso_patient(token, patient_payload)

        return {
            "status": "success",
            "tasso_patient_id": tasso_patient["results"]["id"]
        }

    except Exception as e:
        print("ERROR STACKTRACE:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))