FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["bash", "-lc", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py seed_site && gunicorn meet_lessons.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 60"]
