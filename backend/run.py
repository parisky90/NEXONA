# backend/run.py
from app import create_app, db
from app.models import User, Candidate, Position
# Removed Migrate import, using init in __init__

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Candidate': Candidate, 'Position': Position}

if __name__ == '__main__':
    # Use host='0.0.0.0' for Docker accessibility
    app.run(host='0.0.0.0', port=5000, debug=app.config.get('DEBUG', False))