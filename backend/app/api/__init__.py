# backend/app/api/__init__.py

# Εισάγουμε τα blueprints από τα αντίστοιχα αρχεία routes
# χρησιμοποιώντας σχετικές εισαγωγές.
try:
    from .routes import bp
except ImportError as e:
    import sys
    sys.stderr.write(f"ERROR in app/api/__init__.py: Could not import 'bp' from .routes. Error: {e}\n")
    bp = None # Ορισμός σε None για να μην σπάσει το app/__init__.py αν αποτύχει το import (θα το πιάσει εκεί)

try:
    from .routes_admin import admin_bp
except ImportError as e:
    import sys
    sys.stderr.write(f"ERROR in app/api/__init__.py: Could not import 'admin_bp' from .routes_admin. Error: {e}\n")
    admin_bp = None

try:
    from .routes_company_admin import company_admin_bp
except ImportError as e:
    import sys
    sys.stderr.write(f"ERROR in app/api/__init__.py: Could not import 'company_admin_bp' from .routes_company_admin. Error: {e}\n")
    company_admin_bp = None

# Δεν χρειάζεται να εξάγουμε τίποτα με __all__ αν τα imports γίνονται σωστά στο app/__init__.py
# Αν θέλεις να είσαι ρητός:
# __all__ = ['bp', 'admin_bp', 'company_admin_bp']