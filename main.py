from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from config import (
    TASSO_BASE_URL,
    JOTFORM_WEBHOOK_SECRET,
    TASSO_USERNAME,
    TASSO_SECRET,
    GLP1_PROJECT_ID,
    TESTOSTRONE_PROJECT_ID)

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


# -------------------------------
# Helper: Create Order in Tasso
# -------------------------------
def create_tasso_order(token: str, order: dict) -> dict:
    url = f"{TASSO_BASE_URL}/orders"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=order, headers=headers, timeout=10)

    if response.status_code not in (200, 201):
        raise Exception(f"Tasso order creation failed: {response.status_code} - {response.text}")

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
    """
    Create a patient and immediately create an order for them.
    This combines both operations in one webhook call.
    
    Requires additional fields in the Jotform:
    - configurationId
    - npi (provider information)
    - containerIdentifier (optional)
    - shipByDate (optional)
    """
    
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

    try:
        form = await request.form()
        raw = form.get("rawRequest")
        data = json.loads(raw)

        print("PARSED RAW:", data)
        
        # Extract patient information (same as original webhook)
        name = data.get("q3_name", {})
        dob = data.get("q16_dateOf", {})
        phone = data.get("q6_phoneNumber", {})
        digits = f"{phone.get('area','')}{phone.get('phone','')}"
        digits = "".join([c for c in digits if c.isdigit()])

        path = data.get("path", "")
        if path == "/submit/242116255933151":
            project_id = GLP1_PROJECT_ID
        elif path == "/submit/242115439242147":
            project_id = TESTOSTRONE_PROJECT_ID
        else:
            project_id = GLP1_PROJECT_ID

        if len(digits) == 10:
            formatted_phone = "1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            formatted_phone = digits
        else:
            formatted_phone = None

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

        address1 = addr.get("addr_line1") or "Unknown"
        address2 = addr.get("addr_line2") if addr.get("addr_line2") != '' else "Unknown"
        city = addr.get("city") or "Unknown"
        state = addr.get("state") or "Unknown"
        postal = addr.get("postal") or "00000"
        
        if len(state) == 2:
            state_code = state
        else:
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
            "projectId": project_id,
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

        # Create patient
        token = get_tasso_token()
        tasso_patient = create_tasso_patient(token, patient_payload)
        patient_id = tasso_patient["results"]["id"]
        
        print(f"Patient created with ID: {patient_id}")
        
        # Now create order for the patient
        # You'll need to add these fields to your Jotform
        configuration_id = data.get("configurationId")  # Add this field to Jotform
        npi_data = data.get("npi", {})  # Add this field to Jotform
        
        if npi_data.get("id"):
            order_payload = {
                "patientId": patient_id,
                "provider": {
                    "npi": {
                        "id": npi_data.get("id"),
                        "firstName": npi_data.get("firstName"),
                        "lastName": npi_data.get("lastName")
                    }
                }
            }

            if configuration_id:
                order_payload["orderConfiguration"] = {
                    "configurationId": configuration_id
                }

            # Remove empty provider names
            npi_obj = order_payload["provider"]["npi"]
            if not npi_obj.get("firstName"):
                npi_obj.pop("firstName", None)
            if not npi_obj.get("lastName"):
                npi_obj.pop("lastName", None)
            
            # Add optional fields
            container_identifier = data.get("containerIdentifier")
            if container_identifier:
                order_payload["specimens"] = [
                    {
                        "containerIdentifier": container_identifier
                    }
                ]
            
            ship_by_date = data.get("shipByDate")
            if ship_by_date:
                order_payload["timing"] = {
                    "shipByDate": ship_by_date
                }
            
            print("ORDER PAYLOAD:", order_payload)
            
            # Create the order
            tasso_order = create_tasso_order(token, order_payload)
            
            return {
                "status": "success",
                "tasso_patient_id": patient_id,
                "tasso_order_id": tasso_order["results"]["id"],
                "order_details": tasso_order.get("results", tasso_order)
            }
        else:
            # If no order configuration provided, just return patient creation
            return {
                "status": "success",
                "tasso_patient_id": patient_id,
                "note": "Patient created but no order was placed (missing configuration)"
            }

    except Exception as e:
        print("ERROR STACKTRACE:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))