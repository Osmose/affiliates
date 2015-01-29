FROM debian:wheezy
RUN echo "deb http://ftp.us.debian.org/debian wheezy-backports main" >> /etc/apt/sources.list
RUN apt-get update && apt-get install -y python python-pip python-dev libpq-dev libmysqlclient-dev gettext libjpeg8-dev nodejs-legacy
RUN curl -L --insecure https://www.npmjs.org/install.sh | bash

RUN npm install -g stylus

WORKDIR /app

# First copy requirements.txt and peep so we can take advantage of
# docker caching.
COPY requirements /tmp/requirements
RUN pip install -r /tmp/requirements/dev.txt

EXPOSE 8000

#COPY . /app
