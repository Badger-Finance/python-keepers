FROM python:3.9

WORKDIR /keepers

RUN apt-get remove libexpat1 libexpat1-dev -y
RUN apt-get update -y
RUN apt-get install libexpat1>=2.2.10-2+deb11u1 -y
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .