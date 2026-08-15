FROM python:3.12-slim

WORKDIR /app

# Instalăm dependențele necesare pentru baza de date și procesare imagini
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copiem lista de librării
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiem restul codului
COPY . .

# Pregătim fișierele statice (pentru designul site-ului)
# DEBUG=True doar pentru acest pas de build: collectstatic are nevoie ca
# settings.py să se încarce, dar nu foloseşte SECRET_KEY pentru nimic
# sensibil. Cheia reală de producţie vine din mediul de rulare, nu de aici.
RUN DEBUG=True python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]