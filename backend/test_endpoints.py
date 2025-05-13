# backend/test_endpoints.py
import requests
import json
import os

BASE_URL = "http://localhost:5001/api/v1"
session = requests.Session()

# Credentials (πάρ' τα από το .env σου ή όρισέ τα εδώ για τη δοκιμή)
# Βεβαιώσου ότι αυτά ταιριάζουν με το .env σου για τον superadmin
SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL', "superadmin@yourdomain.com")
SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD', "YourSuperSecurePassword123!")

# Credentials για τον Company Admin όπως δημιουργήθηκαν από το seed_data.py
# Αν το DEFAULT_COMPANY_NAME στο .env είναι "My Nexona Company"
COMPANY_ADMIN_EMAIL = "admin@mynexonacompany.com"
COMPANY_ADMIN_PASSWORD = "companyadminpassword"  # Αυτό ορίστηκε στο seed_data.py


def login_user_test(email, password, user_type="User"):
    print(f"\n--- Attempting Login for {user_type}: {email} ---")
    login_payload = {"login_identifier": email, "password": password}
    try:
        response = session.post(f"{BASE_URL}/login", json=login_payload, timeout=10)
        print(f"Login Status Code: {response.status_code}")
        response_data = response.json()
        print("Login Response JSON:", json.dumps(response_data, indent=2))
        if response.status_code == 200 and response_data.get("user"):
            print(
                f"{user_type} Login successful. User ID: {response_data['user'].get('id')}, Company ID: {response_data['user'].get('company_id')}")
            return True
        else:
            print(f"{user_type} Login failed. Error: {response_data.get('error', 'Unknown error')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Login request failed for {email}: {e}")
        return False
    except json.JSONDecodeError:
        print(f"Login response was not valid JSON. Status: {response.status_code}, Text: {response.text}")
        return False


def get_candidates_test(status="Processing", user_type="User", params=None):
    print(f"\n--- Attempting to GET /candidates/{status} as {user_type} ---")
    try:
        response = session.get(f"{BASE_URL}/candidates/{status}", params=params, timeout=10)
        print(f"Get Candidates Status Code: {response.status_code}")
        response_data = response.json()
        if response.status_code == 200:
            print(f"Successfully fetched {len(response_data)} candidates with status '{status}'.")
            if response_data:
                print("First candidate example:", json.dumps(response_data[0], indent=2))
            else:
                print("No candidates found for this status and filter.")
        else:
            print(f"Failed to fetch candidates. Response: {json.dumps(response_data, indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Get candidates request failed: {e}")
    except json.JSONDecodeError:
        print(f"Get candidates response was not valid JSON. Status: {response.status_code}, Text: {response.text}")


def upload_cv_test(cv_path, position_name="Test Developer", user_type="User", target_company_id_for_superadmin=None):
    print(f"\n--- Attempting to UPLOAD CV as {user_type} (Position: {position_name}) ---")
    if not os.path.exists(cv_path):
        print(f"CV file not found at: {cv_path}. Skipping upload test.")
        return None  # Return None if upload skipped

    files = {'cv_file': (os.path.basename(cv_path), open(cv_path, 'rb'), 'application/pdf')}
    data = {'position': position_name}

    if user_type == "Superadmin" and target_company_id_for_superadmin:
        data['company_id_for_upload'] = target_company_id_for_superadmin
        print(f"Superadmin uploading for Company ID: {target_company_id_for_superadmin}")

    try:
        response = session.post(f"{BASE_URL}/upload", files=files, data=data, timeout=30)
        print(f"Upload CV Status Code: {response.status_code}")
        response_data = response.json()
        print("Upload CV Response JSON:", json.dumps(response_data, indent=2))
        if response.status_code == 201:
            candidate_id = response_data.get('candidate_id')
            print(f"CV uploaded successfully! Candidate ID: {candidate_id}")
            return candidate_id  # Return candidate_id on success
        else:
            print(f"CV upload failed.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Upload CV request failed: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Upload CV response was not valid JSON. Status: {response.status_code}, Text: {response.text}")
        return None


def get_single_candidate_test(candidate_id, user_type="User"):
    print(f"\n--- Attempting to GET /candidate/{candidate_id} as {user_type} ---")
    if not candidate_id:
        print("No candidate_id provided for GET single candidate test. Skipping.")
        return
    try:
        response = session.get(f"{BASE_URL}/candidate/{candidate_id}", timeout=10)
        print(f"Get Single Candidate Status Code: {response.status_code}")
        response_data = response.json()
        if response.status_code == 200:
            print("Single Candidate Data:", json.dumps(response_data, indent=2))
        else:
            print(f"Failed to fetch single candidate. Response: {json.dumps(response_data, indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Get single candidate request failed: {e}")
    except json.JSONDecodeError:
        print(
            f"Get single candidate response was not valid JSON. Status: {response.status_code}, Text: {response.text}")


if __name__ == "__main__":
    # Ορισμός του dummy_cv_path στην αρχή του main block
    dummy_cv_path = "dummy_cv.pdf"
    uploaded_candidate_id_company_admin = None
    uploaded_candidate_id_superadmin = None

    print("=============================================")
    print("=== TESTING AS COMPANY ADMIN ===")
    print("=============================================")
    # Test login for Company Admin
    if login_user_test(COMPANY_ADMIN_EMAIL, COMPANY_ADMIN_PASSWORD, "Company Admin"):
        get_candidates_test(status="Processing", user_type="Company Admin")

        if not os.path.exists(dummy_cv_path):
            with open(dummy_cv_path, "wb") as f:
                f.write(b"%PDF-1.4\n%test\n%%EOF")
            print(f"Created dummy CV: {dummy_cv_path}")

        uploaded_candidate_id_company_admin = upload_cv_test(dummy_cv_path,
                                                             position_name="Software Engineer (Test by CA)",
                                                             user_type="Company Admin")
        get_candidates_test(status="Processing", user_type="Company Admin")
        if uploaded_candidate_id_company_admin:
            get_single_candidate_test(uploaded_candidate_id_company_admin, "Company Admin")

        # Logout Company Admin
        try:
            logout_response = session.post(f"{BASE_URL}/logout")
            print("\n--- Company Admin Logout Status:", logout_response.status_code,
                  logout_response.json() if logout_response.content else "")
        except requests.exceptions.RequestException as e:
            print(f"Logout request failed for Company Admin: {e}")
        session = requests.Session()  # Reset session for next user
        print("=============================================")

    print("\n\n=============================================")
    print("=== TESTING AS SUPERADMIN ===")
    print("=============================================")
    # Test login for Superadmin
    if login_user_test(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, "Superadmin"):
        # Superadmin βλέπει υποψηφίους (με filter για την εταιρεία 1)
        print("\nSuperadmin fetching candidates for Company ID 1:")
        get_candidates_test(status="Processing", user_type="Superadmin", params={"company_id": 1})

        # Superadmin ανεβάζει CV για την εταιρεία 1
        if not os.path.exists(dummy_cv_path):  # Ξαναδημιούργησε αν δεν υπάρχει
            with open(dummy_cv_path, "wb") as f:
                f.write(b"%PDF-1.4\n%test\n%%EOF")
            print(f"Re-created dummy CV: {dummy_cv_path}")

        uploaded_candidate_id_superadmin = upload_cv_test(dummy_cv_path, position_name="Data Analyst (Test by SA)",
                                                          user_type="Superadmin", target_company_id_for_superadmin=1)
        print("\nSuperadmin fetching candidates for Company ID 1 (after SA upload):")
        get_candidates_test(status="Processing", user_type="Superadmin", params={"company_id": 1})
        if uploaded_candidate_id_superadmin:
            get_single_candidate_test(uploaded_candidate_id_superadmin, "Superadmin")

        # Logout Superadmin
        try:
            logout_response = session.post(f"{BASE_URL}/logout")
            print("\n--- Superadmin Logout Status:", logout_response.status_code,
                  logout_response.json() if logout_response.content else "")
        except requests.exceptions.RequestException as e:
            print(f"Logout request failed for Superadmin: {e}")
        print("=============================================")

    # Καθάρισε το dummy CV στο τέλος
    if os.path.exists(dummy_cv_path):
        try:
            os.remove(dummy_cv_path)
            print(f"\nRemoved dummy CV: {dummy_cv_path}")
        except Exception as e:
            print(f"Could not remove dummy_cv.pdf: {e}")