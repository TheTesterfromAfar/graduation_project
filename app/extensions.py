"""Extension instances, created unbound so the application factory can wire them up."""
from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
# render_as_batch lets Alembic ALTER SQLite tables (which it cannot do natively).
migrate = Migrate(render_as_batch=True)
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)
oauth = OAuth()
