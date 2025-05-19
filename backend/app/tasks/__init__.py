# backend/app/tasks/__init__.py
# This file makes the 'tasks' directory a Python package.

# Explicitly importing task modules ensures they are loaded when the
# Celery worker starts, especially if autodiscover might face issues or for clarity.
# print("DEBUG: app/tasks/__init__.py is being executed - Attempting to import task modules...")

try:
    from . import parsing
    # print("DEBUG: app.tasks.parsing imported successfully from tasks/__init__.py")
except ImportError as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to import 'parsing' task module: {e}", exc_info=True)
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Unexpected error importing 'parsing' task module: {e}", exc_info=True)


try:
    from . import communication
    # print("DEBUG: app.tasks.communication imported successfully from tasks/__init__.py")
except ImportError as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to import 'communication' task module: {e}", exc_info=True)
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Unexpected error importing 'communication' task module: {e}", exc_info=True)


try:
    from . import reminders
    # print("DEBUG: app.tasks.reminders imported successfully from tasks/__init__.py")
except ImportError as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to import 'reminders' task module: {e}", exc_info=True)
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Unexpected error importing 'reminders' task module: {e}", exc_info=True)

# print("DEBUG: app/tasks/__init__.py execution finished.")