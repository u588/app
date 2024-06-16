FROM ubuntu:22.04
RUN apt-get update && apt-get install -y cron

COPY . /home
COPY ./cron/root /var/spool/cron/crontabs/root
WORKDIR /home
RUN pip install -r requirement.txt
CMD ["cron", "-f"]
