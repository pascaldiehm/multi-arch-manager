FROM php:apache

COPY ./mam-server.php /var/www/html/index.php
COPY ./mam.py /var/www/html/mam.py

EXPOSE 80
