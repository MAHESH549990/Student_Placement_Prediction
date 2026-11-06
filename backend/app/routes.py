"""API route registration."""
from .controllers.auth_controller import auth
from .controllers.student_controller import students
from .controllers.admin_controller import admin


def register_routes(app):
    app.register_blueprint(auth)
    app.register_blueprint(students)
    app.register_blueprint(admin)
