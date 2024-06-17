FROM 10.3.18.60/docker/tdx-straper:u1

WORKDIR /home
COPY . /home
COPY ./cron/root /var/spool/cron/crontabs/root
WORKDIR /home

CMD ["cron", "-f"]
