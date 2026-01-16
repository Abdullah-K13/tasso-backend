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
        "projectId": "47709ce3-3780-45b4-b050-80f075cdf4ad",
        "subjectId": "A1001",
        "firstName": "Terry",
        "lastName": "Taso",
        "shippingAddress": {
            "address1": "1631 15th Ave W",
            "address2": "Suite 105",
            "city": "Seattle",
            "district1": "WA",
            "postalCode": "98119",
            "country": "US"
        },
        "contactInformation": {
            "email": "terryt@tassoinc.com",
            "phoneNumber": "12124567890"
        },
        "dateOfBirth": "1988-01-25",
        "gender": "cisFemale",
        "assignedSex": "female",
        "race": "American Indian or Alaska Native",
        "smsConsent": True
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
