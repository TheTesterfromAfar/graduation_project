"""Command-line tools: `flask create-user`, `flask set-password`, `flask list-users`, `flask deactivate-user`."""
import click
from email_validator import EmailNotValidError, validate_email
from flask.cli import with_appcontext
from sqlalchemy import select

from .extensions import db
from .models import ROLE_ADMIN, ROLES, User
from .security import password_problems


def _find_user(email):
    return db.session.execute(select(User).filter_by(email=email.strip().lower())).scalar_one_or_none()


def _clean_email(email):
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise click.BadParameter(str(exc)) from exc


def _check_password(password, email):
    problems = password_problems(password, email)
    if problems:
        raise click.UsageError("Weak password - needs: " + "; ".join(problems))


@click.command("create-user")
@click.argument("email")
@click.option("--role", type=click.Choice(ROLES), default=ROLE_ADMIN, show_default=True, help="admin = full access, analyst = read-only.")
@click.option("--name", "full_name", default=None, help="Display name.")
@click.password_option(help="Prompted for (hidden) if omitted.")
@with_appcontext
def create_user(email, role, full_name, password):
    """Create a staff account that signs in with email + password."""
    email = _clean_email(email)
    if _find_user(email):
        raise click.UsageError(f"{email} already exists. Use `flask set-password` to change the password.")
    _check_password(password, email)

    user = User(email=email, full_name=full_name, role=role, active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Created {role} account for {email}.")


@click.command("set-password")
@click.argument("email")
@click.password_option(help="Prompted for (hidden) if omitted.")
@with_appcontext
def set_password(email, password):
    """Change a user's password (also enables password login for Google-only accounts)."""
    user = _find_user(email)
    if not user:
        raise click.UsageError(f"No user with email {email}.")
    _check_password(password, user.email)
    user.set_password(password)
    db.session.commit()
    click.echo(f"Password updated for {user.email}.")


@click.command("deactivate-user")
@click.argument("email")
@with_appcontext
def deactivate_user(email):
    """Disable an account. Existing sessions stop working on their next request."""
    user = _find_user(email)
    if not user:
        raise click.UsageError(f"No user with email {email}.")
    user.active = False
    db.session.commit()
    click.echo(f"{user.email} deactivated.")


@click.command("list-users")
@with_appcontext
def list_users():
    """List all staff accounts."""
    users = db.session.execute(select(User).order_by(User.email)).scalars().all()
    if not users:
        click.echo("No users yet. Create one with: flask create-user you@example.com")
    for user in users:
        state = "active" if user.active else "DISABLED"
        login = "password" if user.password_hash else "google-only"
        click.echo(f"{user.email:<40} {user.role:<8} {state:<8} {login}")


def register_cli(app):
    for command in (create_user, set_password, deactivate_user, list_users):
        app.cli.add_command(command)
