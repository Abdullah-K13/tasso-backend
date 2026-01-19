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
        addr = data.get("q5_shippingAddress", {})

        patient_payload = {
            "projectId": TASSO_PROJECT_ID,
            "subjectId": "AUTO-" + data.get("event_id", "unknown"),
            "firstName": name.get("first"),
            "lastName": name.get("last"),
            "shippingAddress": {
                "address1": addr.get("addr_line1"),
                "address2": addr.get("addr_line2") or "",
                "city": addr.get("city"),
                "district1": addr.get("state"),
                "postalCode": addr.get("postal"),
                "country": "US"
            },
            "contactInformation": {
                "email": data.get("q4_email"),
                "phoneNumber": f"{phone.get('area','')}{phone.get('phone','')}",
            },
            "dateOfBirth": f"{dob.get('year')}-{dob.get('month')}-{dob.get('day')}",
            "gender": data.get("q15_gender"),
            "assignedSex": data.get("q15_gender"),
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