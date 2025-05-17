import requests
import json
from datetime import datetime, timedelta  # Προστέθηκε για το propose_interview

BASE_URL = "http://localhost:5001/api"

# === Στοιχεία Χρήστη για Login (company_admin) ===
LOGIN_PAYLOAD = {
    "username": "tasos",
    "password": "12345678"
}

# === Δημιουργία Session για διατήρηση cookies ===
session = requests.Session()

# === ID Υποψηφίου (ΠΡΟΣΩΡΙΝΟ - ΘΑ ΤΟ ΑΛΛΑΞΟΥΜΕ ΜΕΤΑ) ===
# Για να τρέξει το script χωρίς να ψάχνεις UUID τώρα, θα το αφήσω ως placeholder.
# Αργότερα, θα φτιάξουμε μια συνάρτηση που θα παίρνει έναν υποψήφιο.
CANDIDATE_UUID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"  # Απλά για να μην είναι το αρχικό string


def login_user():
    print(f"Attempting login for user: {LOGIN_PAYLOAD['username']}...")
    try:
        response = session.post(f"{BASE_URL}/login", json=LOGIN_PAYLOAD)
        response.raise_for_status()
        print("Login successful!")
        user_data = response.json().get('user', {})
        print(
            f"User ID: {user_data.get('id')}, Role: {user_data.get('role')}, Company ID: {user_data.get('company_id')}")
        return True
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error during login: {http_err}")
        print("Response text:", response.text)
    except requests.exceptions.RequestException as req_err:
        print(f"Request error during login: {req_err}")
    except json.JSONDecodeError:
        print("Failed to decode JSON response from login.")
        print("Response text:", response.text)
    return False


def get_session_status():
    if not session.cookies:
        print("Not logged in. Cannot get session status.")
        return
    print("\nGetting session status...")
    try:
        response = session.get(f"{BASE_URL}/session")
        response.raise_for_status()
        print("Session status retrieved successfully.")
        print("Session Data:", json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error getting session status: {e}")
        if hasattr(e, 'response'): print("Response text:", e.response.text)


def get_first_candidate_uuid():
    """Ανακτά το UUID του πρώτου υποψηφίου της εταιρείας του συνδεδεμένου χρήστη."""
    if not session.cookies:
        print("Not logged in. Cannot get candidates.")
        return None

    print("\nFetching candidates to get a UUID...")
    try:
        response = session.get(f"{BASE_URL}/candidates", params={"page": 1, "per_page": 1})
        response.raise_for_status()
        data = response.json()
        if data.get("candidates") and len(data["candidates"]) > 0:
            first_candidate_uuid = data["candidates"][0].get("candidate_id")
            print(f"Found candidate UUID: {first_candidate_uuid}")
            return first_candidate_uuid
        else:
            print("No candidates found for the logged-in user's company.")
            return None
    except Exception as e:
        print(f"Error fetching candidates: {e}")
        if hasattr(e, 'response'): print("Response text:", e.response.text)
        return None


def propose_interview_for_candidate(candidate_uuid):
    if not session.cookies:
        print("User not logged in. Please login first.")
        return None
    if not candidate_uuid:
        print("No candidate UUID provided for proposing interview.")
        return None

    print(f"\nAttempting to propose interview for candidate: {candidate_uuid}...")
    now = datetime.now()
    slot1_start = now + timedelta(days=1, hours=2)
    slot1_end = slot1_start + timedelta(hours=1)
    slot2_start = now + timedelta(days=1, hours=5)
    slot2_end = slot2_start + timedelta(minutes=30)
    slot3_start = now + timedelta(days=2, hours=3)
    slot3_end = slot3_start + timedelta(hours=1)
    time_format = "%Y-%m-%d %H:%M:%S"

    interview_payload = {
        "position_id": None,
        "proposed_slots": [
            {"start_time": slot1_start.strftime(time_format), "end_time": slot1_end.strftime(time_format)},
            {"start_time": slot2_start.strftime(time_format), "end_time": slot2_end.strftime(time_format)},
            {"start_time": slot3_start.strftime(time_format), "end_time": slot3_end.strftime(time_format)}
        ],
        "location": "Online - Python Script Test",
        "interview_type": "ONLINE",
        "notes_for_candidate": "Test interview proposal from Python script."
    }
    print("Payload for propose interview:", json.dumps(interview_payload, indent=2))
    try:
        response = session.post(f"{BASE_URL}/candidates/{candidate_uuid}/propose-interview", json=interview_payload)
        response.raise_for_status()
        print("Interview proposed successfully!")
        interview_data = response.json()
        print("Response JSON:", json.dumps(interview_data, indent=2, ensure_ascii=False))
        return interview_data
    except Exception as e:
        print(f"Error proposing interview: {e}")
        if hasattr(e, 'response'): print("Response text:", e.response.text)
        return None


def confirm_slot(token, choice):
    if not token:
        print("Confirmation token is required.")
        return
    print(f"\nAttempting to confirm slot {choice} for token: {token}...")
    try:
        response = requests.get(f"{BASE_URL}/interviews/confirm/{token}/{choice}")
        response.raise_for_status()
        print(f"Slot {choice} confirmation request sent successfully for token {token}.")
        print(f"Status Code: {response.status_code}")
        if "Επιβεβαίωση Συνέντευξης" in response.text and "Ευχαριστούμε!" in response.text:
            print("Επιβεβαίωση επιτυχής! (Βάσει περιεχομένου HTML)")
        elif "Σφάλμα" in response.text or "δεν είναι πλέον ενεργή" in response.text:
            print("Η επιβεβαίωση απέτυχε ή ο σύνδεσμος δεν είναι έγκυρος. (Βάσει περιεχομένου HTML)")
        else:
            print("Άγνωστη απάντηση HTML.")
            # print("Response HTML (first 500 chars):", response.text[:500])
    except Exception as e:
        print(f"Error confirming slot: {e}")
        if hasattr(e, 'response'): print("Response text:", e.response.text)


# --- Κύρια Ροή του Script ---
if __name__ == "__main__":
    if login_user():
        get_session_status()

        candidate_to_test_uuid = get_first_candidate_uuid()  # Παίρνουμε δυναμικά έναν υποψήφιο

        if candidate_to_test_uuid:
            proposed_interview_data = propose_interview_for_candidate(candidate_to_test_uuid)
            if proposed_interview_data:
                confirmation_token = proposed_interview_data.get('confirmation_token')
                print(f"\nInterview proposal sent. Confirmation token: {confirmation_token}")
                print("Παρακαλώ έλεγξε τα logs του Celery worker και το email του υποψηφίου (αν είναι ρυθμισμένο).")

                # Προαιρετικά: Αυτόματη επιβεβαίωση του πρώτου slot για δοκιμή
                if confirmation_token:
                    print("\n--- Αυτόματη Δοκιμή Επιβεβαίωσης του Slot 1 ---")
                    # Περίμενε λίγο για να προλάβει να σταλεί το email (αν και δεν είναι απαραίτητο για το API call)
                    # import time
                    # time.sleep(5)
                    confirm_slot(confirmation_token, 1)
                    print(
                        "\nΈλεγξε τη βάση δεδομένων για την αλλαγή status του interview και το history του candidate.")
        else:
            print("\nΔεν βρέθηκε υποψήφιος για δοκιμή πρότασης συνέντευξης.")
            print("Παρακαλώ δημιούργησε τουλάχιστον έναν υποψήφιο για την εταιρεία του χρήστη 'tasos'.")
    else:
        print("\nCould not proceed due to login failure.")