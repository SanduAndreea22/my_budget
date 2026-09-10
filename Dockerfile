FROM python:3.12-slim

WORKDIR /app

# Install dependencies needed for the database driver and image processing
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copy the dependency list first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Build static files
# DEBUG=True only for this build step: collectstatic needs settings.py to
# load, but doesn't use SECRET_KEY for anything sensitive. The real
# production key comes from the runtime environment, not from here.
RUN DEBUG=True python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]