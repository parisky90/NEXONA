# backend/app/api/__init__.py

# Κάνουμε τα blueprints από τα αρχεία routes διαθέσιμα όταν κάποιος κάνει "from app.api import ..."
# Βεβαιώσου ότι τα ονόματα των blueprints είναι σωστά στα αντίστοιχα αρχεία routes*.py:
# - routes.py: πρέπει να ορίζει Blueprint με όνομα 'bp'
# - routes_admin.py: πρέπει να ορίζει Blueprint με όνομα 'admin_bp'
# - routes_company_admin.py: πρέπει να ορίζει Blueprint με όνομα 'company_admin_bp'

try:
    from .routes import bp
except ImportError as e:
    # Log ή print για να ξέρεις αν το πρόβλημα είναι εδώ
    import sys
    sys.stderr.write(f"ERROR in app/api/__init__.py: Could not import 'bp' from .routes. Error: {e}\n")
    # raise # Μπορείς να κάνεις raise αν είναι κρίσιμο

try:
    from .routes_admin import admin_bp
except ImportError as e:
    import sys
    sys.stderr.write(f"ERROR in app/api/__init__.py: Could not import 'admin_bp' from .routes_admin. Error: {e}\n")

try:
    from .routes_company_admin import company_admin_bp
except ImportError as e:
    import sys
    sys.stderr.write(f"ERROR in app/api/__init__.py: Could not import 'company_admin_bp' from .routes_company_admin. Error: {e}\n")

# Προαιρετικά, για να είσαι σίγουρος ότι τα ονόματα είναι διαθέσιμα:
# __all__ = ['bp', 'admin_bp', 'company_admin_bp']
# (Αν και συνήθως δεν χρειάζεται αν τα imports παραπάνω είναι σωστά)