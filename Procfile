web: gunicorn --workers=1 --threads=2 --worker-class=gthread --timeout=120 --keep-alive=5 --max-requests=1000 --max-requests-jitter=50 --log-level=info application:application
