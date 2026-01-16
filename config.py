import os
from dotenv import load_dotenv

load_dotenv()


TASSO_BASE_URL = os.getenv("TASSO_BASE_URL")  # sandbox or prod
JOTFORM_WEBHOOK_SECRET = os.getenv("JOTFORM_WEBHOOK_SECRET")
TASSO_USERNAME = os.getenv("TASSO_USERNAME")
TASSO_SECRET = os.getenv("TASSO_SECRET")
TASSO_PROJECT_ID = os.getenv("TASSO_PROJECT_ID")

