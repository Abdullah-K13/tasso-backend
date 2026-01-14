from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from config import (
    TASSO_BASE_URL,
    TASSO_USERNAME,
    TASSO_SECRET,
    JOTFORM_WEBHOOK_SECRET
)

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
        "username": TASSO_USERNAME,
        "secret": TASSO_SECRET
    }

    response = requests.post(url, json=payload, timeout=10)

    if response.status_code != 200:
        raise Exception("Failed to authenticate with Tasso")

    return response.json()["results"]["idToken"]


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
    payload = await request.json()

    # -------------------------------
    # (OPTIONAL) Webhook verification
    # -------------------------------
    received_secret = payload.get("webhook_secret")
    if JOTFORM_WEBHOOK_SECRET and received_secret != JOTFORM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized webhook")

    # -------------------------------
    # Extract Jotform fields
    # (adjust field names!)
    # -------------------------------
    try:
        submission = payload["content"]
        print(payload)

        patient_payload = {
            "firstName": submission["first_name"],
            "lastName": submission["last_name"],
            "dob": submission["dob"],  # YYYY-MM-DD
            "sexAtBirth": submission.get("sex", "unknown"),
            "contact": {
                "email": submission["email"],
                "phone": submission["phone"]
            },
            "address": {
                "line1": submission["address_line1"],
                "line2": submission.get("address_line2"),
                "city": submission["city"],
                "state": submission["state"],
                "postalCode": submission["zip"],
                "country": "US"
            }
        }
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")

    # -------------------------------
    # Create patient in Tasso
    # -------------------------------
    # try:
    #     token = get_tasso_token()
    #     tasso_patient = create_tasso_patient(token, patient_payload)
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=str(e))

    # -------------------------------
    # Success response
    # -------------------------------
    return {
        "status": "success",
        "tasso_patient_id": tasso_patient["results"]["id"]
    }
