FROM php:apache

COPY ./php.ini /usr/local/etc/php/php.ini
COPY ./mam-server.php /var/www/html/index.php
COPY ./mam.py /var/www/html/mam.py

RUN mkdir /data && chown www-data:www-data /data
VOLUME /data

EXPOSE 80
