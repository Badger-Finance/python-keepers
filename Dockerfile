FROM python:3.9

WORKDIR /keepers

RUN apt-get remove libexpat1 libexpat1-dev -y
RUN apt-get remove libsasl2-2 libsasl2-modules-db -y
RUN apt-get remove linux-libc-dev -y
RUN apt-get update -y
RUN apt-get install libexpat1>=2.2.10-2+deb11u1 -y
RUN apt-get install libsasl2-2>=2.1.27+dfsg-2.1+deb11u1 -y
RUN apt-get install linux-libc-dev>=5.10.92-2 libc6-dev -y
RUN apt-get install git -y
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .