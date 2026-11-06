"""Development entry point. Production deployments should use a WSGI server."""
import os

# Keep local Windows memory usage predictable before importing NumPy/scikit-learn.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ.setdefault("OMP_NUM_THREADS", "1")

from app import create_app

app = create_app()


if __name__ == "__main__":
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "5000"))
    if os.getenv("APP_ENV", "development").lower() == "production":
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
    else:
        app.run(host=host, port=port, debug=False, threaded=True)
