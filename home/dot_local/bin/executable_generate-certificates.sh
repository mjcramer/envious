#!/bin/bash

country="US"
state="CA"
locality="San Francisco"
organization="Michael Cramer"
unit="de"
host="michael.cramer.name"
email="michael@cramer.name"

csr="${host}.csr"
key="${host}.key"
cert="${host}.cert"

openssl genrsa -des3 -out michael.cramer.name.key -passout "pass:password" 1024

openssl req -new -key michael.cramer.name.key -passin "pass:password" -out michael.cramer.name.csr -subj "/C=US/ST=CA/L=San Francisco/O=brainframe/CN=michael.cramer.name"

mv michael.cramer.name.key michael.cramer.name.key.orig
openssl rsa -in michael.cramer.name.key.orig -passin "pass:password" -out michael.cramer.name.key

openssl x509 -req -days 365 -in michael.cramer.name.csr -signkey michael.cramer.name.key -out michael.cramer.name.crt


private_key=$1

#openssl req -new -x509 -nodes -sha256 -days 365 -key $private_key -outform PEM -subj "/C=US/ST=CA/L=San Francisco/O=Imgur/OU=Discovery/CN=imgur.com/emailAddress=info@imgur.com" > $private_key.pem
openssl req -new -x509 -nodes -sha256 -days 365 -key $private_key -outform PEM > $private_key.pem

