FROM python:3.9

WORKDIR /keepers

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .