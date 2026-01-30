"""
Test script to verify Tasso order creation.

Usage examples:

1) Create order for an existing patient:
   python test_tasso_orders.py

2) Create patient first, then create order:
   Set CREATE_PATIENT_FIRST=true in .env (or export it), then run.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# Import your helpers from main.py
from main import get_tasso_token, create_tasso_patient


def bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def build_order_payload(
    patient_id: str,
    configuration_id: str,
    npi_id: str,
    npi_first: str | None = None,
    npi_last: str | None = None,
    container_identifier: str | None = None,
    ship_by_date: str | None = None,
    custom_attributes: list[dict] | None = None,
) -> dict:
    payload = {
        "patientId": patient_id,
        "orderConfiguration": {"configurationId": configuration_id},
        "provider": {
            "npi": {
                "id": npi_id,
                "firstName": npi_first,
                "lastName": npi_last,
            }
        },
    }

    # Remove empty provider names to avoid sending nulls if Tasso is strict
    if not npi_first:
        payload["provider"]["npi"].pop("firstName", None)
    if not npi_last:
        payload["provider"]["npi"].pop("lastName", None)

    if container_identifier:
        payload["specimens"] = [{"containerIdentifier": container_identifier}]

    if ship_by_date:
        payload["timing"] = {"shipByDate": ship_by_date}

    if custom_attributes:
        payload["customAttributes"] = custom_attributes

    return payload


def maybe_create_test_patient(token: str) -> str:
    """
    Only used when CREATE_PATIENT_FIRST=true or when PATIENT_ID is not provided.
    """
    patient_payload = {
        "projectId": os.getenv("TEST_PROJECT_ID", "47709ce3-3780-45b4-b050-80f075cdf4ad"),
        "subjectId": os.getenv("TEST_SUBJECT_ID", "AUTO-TEST-ORDER-001"),
        "firstName": os.getenv("TEST_FIRST_NAME", "Terry"),
        "lastName": os.getenv("TEST_LAST_NAME", "Taso"),
        "shippingAddress": {
            "address1": "1631 15th Ave W",
            "address2": "Suite 105",
            "city": "Seattle",
            "district1": "WA",
            "postalCode": "98119",
            "country": "US",
        },
        "contactInformation": {
            "email": os.getenv("TEST_EMAIL", "terryt@tassoinc.com"),
            "phoneNumber": os.getenv("TEST_PHONE", "12124567890"),
        },
        "dateOfBirth": os.getenv("TEST_DOB", "1988-01-25"),
        "gender": os.getenv("TEST_GENDER", "cisFemale"),
        "assignedSex": os.getenv("TEST_ASSIGNED_SEX", "female"),
        "race": os.getenv("TEST_RACE", "American Indian or Alaska Native"),
        "smsConsent": bool_env("TEST_SMS_CONSENT", True),
    }

    print("Creating a test patient...")
    result = create_tasso_patient(token, patient_payload)

    patient_id = None
    if isinstance(result, dict):
        patient_id = result.get("results", {}).get("id") or result.get("id")

    if not patient_id:
        raise RuntimeError(f"Patientiled to extract patient id from response: {result}")

    print(f"Patient created. patientId={patient_id}")
    return patient_id


def test_create_order():
    print("Authenticating with Tasso...")
    token = get_tasso_token()
    print("Authentication successful.")

    # Create a patient first to ensure valid patientId
    print("Creating a test patient to get a valid ID...")
    patient_id = maybe_create_test_patient(token)
    print(f"Using created patientId: {patient_id}")

    # Hardcoded payload as requested, but with valid patientId
    configuration_id = os.getenv("TEST_CONFIGURATION_ID", "fOsd_k9GQ3")

    order_payload = {
    "patientId": patient_id,
    "provider": {
        "npi": {
            "id": "1234509876",
            "firstName": "Marcy",
            "lastName": "Frank"
        }
    },
    "timing": {"shipByDate": "2026-02-05"}
    }
    # ✅ Add this block right here (before optional fields is fine)
    npi_obj = order_payload["provider"]["npi"]
    if not npi_obj.get("firstName"):
        npi_obj.pop("firstName", None)
    if not npi_obj.get("lastName"):
        npi_obj.pop("lastName", None)




    print("\nORDER PAYLOAD:")
    print(json.dumps(order_payload, indent=2))

    print("\nCreating order in Tasso...")
    # Ensure create_tasso_order is available or mocked if not in main
    try:
        from main import create_tasso_order
        result = create_tasso_order(token, order_payload)
    except ImportError:
        # Fallback if create_tasso_order is not in main.py yet
        print("create_tasso_order not found in main.py, defining locally...")
        import requests
        from config import TASSO_BASE_URL
        
        def local_create_tasso_order(token: str, order: dict) -> dict:
            url = f"{TASSO_BASE_URL}/orders"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=order, headers=headers, timeout=10)
            if response.status_code not in (200, 201):
                raise Exception(f"Order creation failed: {response}")
            return response.json()
            
        result = local_create_tasso_order(token, order_payload)

    print("Order created successfully.")
    print("\nRESPONSE:")
    print(json.dumps(result, indent=2))

    order_id = None
    if isinstance(result, dict):
        order_id = result.get("results", {}).get("id") or result.get("id")

    if order_id:
        print(f"\norderId={order_id}")


if __name__ == "__main__":
    test_create_order()
