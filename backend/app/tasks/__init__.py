# backend/app/tasks/__init__.py
# This file ensures that 'tasks' is treated as a package.

# Explicitly importing task modules can help with discovery,
# especially if there are subtle import issues that autodiscover might miss silently.
try:
    from . import parsing
except ImportError as e:
    print(f"WARNING: Could not import parsing tasks in app/tasks/__init__.py: {e}")

try:
    from . import communication
except ImportError as e:
    print(f"WARNING: Could not import communication tasks in app/tasks/__init__.py: {e}")

try:
    from . import reminders
except ImportError as e:
    print(f"WARNING: Could not import reminder tasks in app/tasks/__init__.py: {e}")