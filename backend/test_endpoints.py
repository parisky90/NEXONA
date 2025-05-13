# backend/test_endpoints.py
import requests
import json
import os
import uuid  # Για μοναδικά emails/usernames

BASE_API_URL = "http://localhost:5001/api/v1"
BASE_APP_URL = "http://localhost:5001"
session = requests.Session()

# Credentials
SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL', "superadmin@yourdomain.com")
SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD', "YourSuperSecurePassword123!")
COMPANY_ADMIN_EMAIL = "admin@mynexonacompany.com"
COMPANY_ADMIN_PASSWORD = "companyadminpassword"


def login_user_test(email, password, user_type="User"):
    print(f"\n--- Attempting Login for {user_type}: {email} ---")
    login_payload = {"login_identifier": email, "password": password}
    try:
        response = session.post(f"{BASE_API_URL}/login", json=login_payload, timeout=10)
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
        print(f"Login request failed for {email}: {e}"); return False
    except json.JSONDecodeError:
        print(
            f"Login response for {email} was not valid JSON. Status: {response.status_code}, Text: {response.text}"); return False


def logout_current_user(user_type="User"):
    print(f"\n--- Attempting Logout for {user_type} ---")
    try:
        response = session.post(f"{BASE_API_URL}/logout", timeout=10)
        print(f"Logout Status Code: {response.status_code}")
        if response.content:
            print("Logout Response JSON:", json.dumps(response.json(), indent=2))
        else:
            print("Logout response has no content.")
        if response.status_code == 200:
            print(f"{user_type} Logout successful.")
        else:
            print(f"{user_type} Logout might have failed.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Logout request failed: {e}"); return False
    except json.JSONDecodeError:
        print(
            f"Logout response was not valid JSON. Status: {response.status_code}, Text: {response.text}"); return False


def get_candidates_test(status="Processing", user_type="User", params=None):
    print(f"\n--- Attempting to GET {BASE_API_URL}/candidates/{status} as {user_type} ---")
    try:
        response = session.get(f"{BASE_API_URL}/candidates/{status}", params=params, timeout=10)
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
        print(f"CV file not found at: {cv_path}. Skipping upload test.");
        return None
    files = {'cv_file': (os.path.basename(cv_path), open(cv_path, 'rb'), 'application/pdf')}
    data = {'position': position_name}
    if user_type == "Superadmin" and target_company_id_for_superadmin:
        data['company_id_for_upload'] = target_company_id_for_superadmin
        print(f"Superadmin uploading for Company ID: {target_company_id_for_superadmin}")
    try:
        response = session.post(f"{BASE_API_URL}/upload", files=files, data=data, timeout=30)
        print(f"Upload CV Status Code: {response.status_code}")
        response_data = response.json()
        print("Upload CV Response JSON:", json.dumps(response_data, indent=2))
        if response.status_code == 201:
            candidate_id = response_data.get('candidate_id')
            print(f"CV uploaded successfully! Candidate ID: {candidate_id}");
            return candidate_id
        else:
            print(f"CV upload failed."); return None
    except requests.exceptions.RequestException as e:
        print(f"Upload CV request failed: {e}"); return None
    except json.JSONDecodeError:
        print(
            f"Upload CV response was not valid JSON. Status: {response.status_code}, Text: {response.text}"); return None


def get_single_candidate_test(candidate_id, user_type="User"):
    print(f"\n--- Attempting to GET {BASE_API_URL}/candidate/{candidate_id} as {user_type} ---")
    if not candidate_id: print("No candidate_id provided. Skipping."); return
    try:
        response = session.get(f"{BASE_API_URL}/candidate/{candidate_id}", timeout=10)
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


def get_admin_companies_test(user_type="User"):
    admin_companies_url = f"{BASE_APP_URL}/admin/companies"
    print(f"\n--- Attempting to GET {admin_companies_url} as {user_type} ---")
    try:
        response = session.get(admin_companies_url, timeout=10)
        print(f"Get Admin Companies Status Code: {response.status_code}")
        if response.status_code == 200:
            response_data = response.json()
            print(f"Successfully fetched {len(response_data)} companies.")
            if response_data: print("First company example:", json.dumps(response_data[0], indent=2))
        elif response.status_code == 403:
            print(f"Access Denied (403) as expected for {user_type}.")
        elif response.status_code == 401:
            print(f"Unauthorized (401) as expected for {user_type} (not logged in or session expired).")
            print("Response Text (might be HTML for login):", response.text[:200])
        else:
            try:
                print(f"Failed to fetch admin companies. Response: {json.dumps(response.json(), indent=2)}")
            except json.JSONDecodeError:
                print(
                    f"Get admin companies response was not valid JSON. Status: {response.status_code}, Text: {response.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"Get admin companies request failed: {e}")


def get_company_users_test(user_type="Company Admin"):
    company_users_url = f"{BASE_API_URL}/company/users"
    print(f"\n--- Attempting to GET {company_users_url} as {user_type} ---")
    try:
        response = session.get(company_users_url, timeout=10)
        print(f"Get Company Users Status Code: {response.status_code}")
        response_data = response.json()
        if response.status_code == 200:
            print(f"Successfully fetched {len(response_data.get('users', []))} users for the company.")
            if response_data.get('users'):
                print("First user example:", json.dumps(response_data['users'][0], indent=2))
        else:
            print(f"Failed to fetch company users. Response: {json.dumps(response_data, indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Get company users request failed: {e}")
    except json.JSONDecodeError:
        print(
            f"Get company users response was not valid JSON. Status: {response.status_code}, Text: {response.text[:200]}")


def create_company_user_test(new_user_data, user_type="Company Admin"):
    create_user_url = f"{BASE_API_URL}/company/users"
    print(f"\n--- Attempting to POST {create_user_url} as {user_type} with data: {new_user_data} ---")
    try:
        response = session.post(create_user_url, json=new_user_data, timeout=10)
        print(f"Create Company User Status Code: {response.status_code}")
        response_data = response.json()
        print("Create Company User Response JSON:", json.dumps(response_data, indent=2))
        if response.status_code == 201:
            created_user_id = response_data.get('id')
            print(f"Successfully created company user '{response_data.get('username')}' with ID: {created_user_id}")
            return created_user_id
        else:
            print(f"Failed to create company user.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Create company user request failed: {e}"); return None
    except json.JSONDecodeError:
        print(
            f"Create company user response was not valid JSON. Status: {response.status_code}, Text: {response.text[:200]}"); return None


def toggle_company_user_status_test(user_id_to_toggle, new_status_is_active, user_type="Company Admin"):
    toggle_status_url = f"{BASE_API_URL}/company/users/{user_id_to_toggle}/status"
    print(f"\n--- Attempting to PUT {toggle_status_url} as {user_type} to set is_active={new_status_is_active} ---")
    if not user_id_to_toggle: print("No user_id_to_toggle provided. Skipping."); return
    try:
        response = session.put(toggle_status_url, json={"is_active": new_status_is_active}, timeout=10)
        print(f"Toggle User Status Code: {response.status_code}")
        response_data = response.json()
        print("Toggle User Status Response JSON:", json.dumps(response_data, indent=2))
        if response.status_code == 200:
            print(
                f"Successfully toggled status for user {user_id_to_toggle} to is_active={response_data.get('is_active')}")
        else:
            print(f"Failed to toggle user status.")
    except requests.exceptions.RequestException as e:
        print(f"Toggle user status request failed: {e}")
    except json.JSONDecodeError:
        print(
            f"Toggle user status response was not valid JSON. Status: {response.status_code}, Text: {response.text[:200]}")


# --- ΝΕΑ ΣΥΝΑΡΤΗΣΗ ΓΙΑ MINIMAL PING TEST ---
def test_company_admin_ping(use_session=None):  # use_session για να μπορούμε να το καλέσουμε και χωρίς login
    ping_url = f"{BASE_API_URL}/company/ping"
    print(f"\n--- Attempting to GET {ping_url} (Minimal Test) ---")

    current_session = use_session if use_session else requests.Session()  # Χρησιμοποίησε το session αν δόθηκε

    try:
        response = current_session.get(ping_url, timeout=10)
        print(f"Ping Test Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Ping Test Response JSON:", json.dumps(response.json(), indent=2))
        else:
            try:
                print(f"Ping Test Failed. Response: {json.dumps(response.json(), indent=2)}")
            except json.JSONDecodeError:
                print(f"Ping Test Failed. Status: {response.status_code}, Text: {response.text[:200]}")

    except requests.exceptions.RequestException as e:
        print(f"Ping Test request failed: {e}")


# --- ΤΕΛΟΣ ΝΕΑΣ ΣΥΝΑΡΤΗΣΗΣ ---

if __name__ == "__main__":
    dummy_cv_path = "dummy_cv.pdf"
    uploaded_candidate_id_company_admin = None
    uploaded_candidate_id_superadmin = None

    # --- ΠΡΩΤΑ ΤΟ MINIMAL PING TEST ΧΩΡΙΣ LOGIN (για να δούμε αν η διαδρομή υπάρχει) ---
    print("\n\n======================================================")
    print("=== TESTING MINIMAL COMPANY ADMIN PING (NO LOGIN) ===")
    print("======================================================")
    test_company_admin_ping()  # Κλήση χωρίς session/login
    print("======================================================")
    # --------------------------------------------------------------------

    print("\n\n=============================================")  # Προσθήκη κενής γραμμής για καλύτερη ανάγνωση
    print("=== TESTING AS COMPANY ADMIN ===")
    print("=============================================")
    if login_user_test(COMPANY_ADMIN_EMAIL, COMPANY_ADMIN_PASSWORD, "Company Admin"):
        # --- PING TEST ΩΣ COMPANY ADMIN (ΜΕΤΑ ΤΟ LOGIN) ---
        # (Αυτό θα τεστάρει και τον company_admin_required_debug decorator)
        test_company_admin_ping(use_session=session)  # Χρησιμοποίησε το session του συνδεδεμένου χρήστη
        # ---------------------------------------------------

        get_candidates_test(status="Processing", user_type="Company Admin")
        if not os.path.exists(dummy_cv_path):
            with open(dummy_cv_path, "wb") as f: f.write(b"%PDF-1.4\n%test\n%%EOF")
            print(f"Created dummy CV: {dummy_cv_path}")
        uploaded_candidate_id_company_admin = upload_cv_test(dummy_cv_path,
                                                             position_name="Software Engineer (Test by CA)",
                                                             user_type="Company Admin")
        get_candidates_test(status="Processing", user_type="Company Admin")
        if uploaded_candidate_id_company_admin:
            get_single_candidate_test(uploaded_candidate_id_company_admin, "Company Admin")

        print("\n\n--- Testing Company Admin User Management ---")
        get_company_users_test("Company Admin")

        unique_suffix = uuid.uuid4().hex[:6]
        new_company_user_data = {
            "username": f"testuser_{unique_suffix}",
            "email": f"testuser_{unique_suffix}@mynexonacompany.com",
            "password": "testpassword123"
        }
        created_user_id = create_company_user_test(new_company_user_data, "Company Admin")

        if created_user_id:
            get_company_users_test("Company Admin")
            toggle_company_user_status_test(created_user_id, False, "Company Admin")
            toggle_company_user_status_test(created_user_id, True, "Company Admin")

        logout_current_user("Company Admin")
    session = requests.Session()
    print("=============================================")

    print("\n\n=============================================")
    print("=== TESTING AS SUPERADMIN ===")
    print("=============================================")
    if login_user_test(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, "Superadmin"):
        print("\nSuperadmin fetching candidates for Company ID 1:")
        get_candidates_test(status="Processing", user_type="Superadmin", params={"company_id": 1})
        if not os.path.exists(dummy_cv_path):
            with open(dummy_cv_path, "wb") as f: f.write(b"%PDF-1.4\n%test\n%%EOF")
            print(f"Re-created dummy CV: {dummy_cv_path}")
        uploaded_candidate_id_superadmin = upload_cv_test(dummy_cv_path, position_name="Data Analyst (Test by SA)",
                                                          user_type="Superadmin", target_company_id_for_superadmin=1)
        print("\nSuperadmin fetching candidates for Company ID 1 (after SA upload):")
        get_candidates_test(status="Processing", user_type="Superadmin", params={"company_id": 1})
        if uploaded_candidate_id_superadmin:
            get_single_candidate_test(uploaded_candidate_id_superadmin, "Superadmin")
        logout_current_user("Superadmin")
    session = requests.Session()
    print("=============================================")

    print("\n\n=============================================")
    print("=== TESTING ADMIN ENDPOINTS (Superadmin Access) ===")
    print("=============================================")
    print("\n--- Test 1: /admin/companies WITHOUT LOGIN ---")
    unauthenticated_session = requests.Session()
    try:
        response_no_login = unauthenticated_session.get(f"{BASE_APP_URL}/admin/companies", timeout=10)
        print(f"Status Code (No Login): {response_no_login.status_code}")
        if response_no_login.status_code != 401: print("Response Text (No Login):", response_no_login.text[:200])
    except Exception as e:
        print(f"Request failed (No Login): {e}")

    print("\n--- Test 2: /admin/companies AS COMPANY ADMIN ---")
    session = requests.Session()
    if login_user_test(COMPANY_ADMIN_EMAIL, COMPANY_ADMIN_PASSWORD, "Company Admin (for Admin Endpoint Test)"):
        get_admin_companies_test("Company Admin")
        logout_current_user("Company Admin (after Admin Endpoint Test)")
    session = requests.Session()

    print("\n--- Test 3: /admin/companies AS SUPERADMIN ---")
    if login_user_test(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, "Superadmin (for Admin Endpoint Test)"):
        get_admin_companies_test("Superadmin")
        logout_current_user("Superadmin (after Admin Endpoint Test)")
    print("=============================================")

    if os.path.exists(dummy_cv_path):
        try:
            os.remove(dummy_cv_path); print(f"\nRemoved dummy CV: {dummy_cv_path}")
        except Exception as e:
            print(f"Could not remove dummy_cv.pdf: {e}")