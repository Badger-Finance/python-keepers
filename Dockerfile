FROM python:3.9

WORKDIR /keepers

RUN apt-get remove libexpat1 libexpat1-dev -y
RUN apt-get remove libsasl2-2 libsasl2-modules-db -y
RUN apt-get remove linux-libc-dev -y
RUN apt-get remove libssl-dev -y
RUN apt-get remove libtiff5 libtiffxx5 -y
RUN apt-get update -y
RUN apt-get install libssl-dev>=1.1.1k-1+deb11u2 libssl1.1>=1.1.1k-1+deb11u2 openssl>=1.1.1k-1+deb11u2 -y
RUN apt-get install libexpat1>=2.2.10-2+deb11u1 -y
RUN apt-get install libsasl2-2>=2.1.27+dfsg-2.1+deb11u1 -y
RUN apt-get install linux-libc-dev>=5.10.113-1 libc6-dev -y
RUN apt-get install libtiff5>=4.2.0-1+deb11u1 -y
RUN apt-get install zlib1g>=1:1.2.11.dfsg-2+deb11u1 -y
RUN apt-get install gzip>=1.10-4+deb11u1 -y
RUN apt-get install libfreetype6>=2.10.4+dfsg-1+deb11u1
RUN apt-get install libfribidi0>=1.0.8-2+deb11u1
RUN apt-get install git -y
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
