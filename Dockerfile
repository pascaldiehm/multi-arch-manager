FROM php:apache

COPY ./mam-server.php /var/www/html/index.php
COPY ./mam.py /var/www/html/mam.py

RUN mkdir /data && chown -R www-data:www-data /data
VOLUME /data

EXPOSE 80
