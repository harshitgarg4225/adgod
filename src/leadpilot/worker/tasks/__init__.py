"""Task package. Importing it registers all Celery tasks with the app."""
from leadpilot.worker.tasks import closer, maintenance, pipeline  # noqa: F401
