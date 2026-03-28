"""
Test script to verify Tasso patient creation
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from main import get_tasso_token, create_tasso_patient


def test_create_patient():
    """Test creating a patient in Tasso"""
    
    # Sample patient data matching Tasso API format
    patient_payload = {
        "projectId": "ac4d054b-a9c3-442d-9ce7-0ac19526bcbb",
        "subjectId": "AUTO-1774322478260-242115439242147-wc9E7AX",
        "firstName": "Carlos",
        "lastName": "Madrid",
        "shippingAddress": {
            "address1": "440 Candy Ln",
            "address2": "Unknown",
            "city": "Buffalo",
            "district1": "TX",
            "postalCode": "75831",
            "country": "US"
        },
        "contactInformation": {
            "email": "'madridcarlosluis8@gmail.com",
            "phoneNumber": "14073166374"
        },
        "dateOfBirth": "1996-06-27",
        "gender": "cisMale",
        "assignedSex": "male",
        "race": "Other",
        "smsConsent": False
    }
    
    try:
        print("🔐 Authenticating with Tasso...")
        token = get_tasso_token()
        print("✅ Authentication successful!")
        print(f"Tokcen: {token[:20]}...")  # Print first 20 chars only
        
        print("\n👤 Creating patient in Tasso...")
        result = create_tasso_patient(token, patient_payload)
        print("✅ Patient created successfully!")
        print(f"\n📋 Response:")
        print(result)
        
        if "results" in result and "id" in result["results"]:
            print(f"\n🎉 Patient ID: {result['results']['id']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    test_create_patient()
