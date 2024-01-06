FROM php:apache

COPY ./mam-server.php /var/www/html/index.php
COPY ./mam.py /var/www/html/mam.py
COPY ./.htaccess /var/www/html/.htaccess

EXPOSE 80
