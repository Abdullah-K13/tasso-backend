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
        print("RAW FORM:", form)

        patient_payload = {
            "projectId": TASSO_PROJECT_ID,
            "subjectId": form.get("subject_id") or form.get("q_subjectId") or "AUTO-" + form.get("submission_id", "unknown"),
            "firstName": form.get("first_name") or form.get("q3_name[first]"),
            "lastName": form.get("last_name") or form.get("q3_name[last]"),
            "shippingAddress": {
                "address1": form.get("address_line1") or form.get("q8_address[addr_line1]"),
                "address2": form.get("address_line2") or form.get("q8_address[addr_line2]") or "",
                "city": form.get("city") or form.get("q8_address[city]"),
                "district1": form.get("state") or form.get("q8_address[state]"),
                "postalCode": form.get("zip") or form.get("q8_address[postal]"),
                "country": "US"
            },
            "contactInformation": {
                "email": form.get("email") or form.get("q5_email"),
                "phoneNumber": form.get("phone") or form.get("q7_phoneNumber")
            },
            "dateOfBirth": form.get("dob") or form.get("q10_dob"),
            "gender": form.get("gender") or form.get("q_gender") or "preferNotToAnswer",
            "assignedSex": form.get("sex") or form.get("q_sex") or "unknown",
            "race": form.get("race") or form.get("q_race") or "Prefer not to answer",
            "smsConsent": form.get("sms_consent") == "Yes" or form.get("q_smsConsent") == "Yes"
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