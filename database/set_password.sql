-- database/set_password.sql
\set passwd `echo $CERT_APP_PASSWORD`
ALTER USER cert_app WITH PASSWORD :'passwd';