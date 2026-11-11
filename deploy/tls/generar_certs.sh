#!/usr/bin/env bash
# Genera la CA y el certificado de demo del Nodo A (F-27, SUP-33): EC P-256, CA 365 dias, certificado 90 dias.
# Solo escribe en CERTS_DIR (por defecto $HOME/.ms-certs, fuera del repo). ca.key nunca sale de esta maquina;
# a los workers solo viaja ca.pem. Terceros: openssl (https://docs.openssl.org/).
#   NODE_IP=<ip de tailscale> NODE_NAME=<hostname> bash deploy/tls/generar_certs.sh
set -euo pipefail
umask 077

DESTINO="${CERTS_DIR:-$HOME/.ms-certs}"
: "${NODE_IP:?define NODE_IP con la IP de Tailscale del Nodo A}"
NOMBRE="${NODE_NAME:-$(hostname)}"
[[ "$NODE_IP" =~ ^[0-9A-Fa-f.:]+$ ]] || { echo "NODE_IP no es una direccion IP" >&2; exit 1; }
[[ "$NOMBRE" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "NODE_NAME solo admite letras, digitos, punto y guion" >&2; exit 1; }

mkdir -p "$DESTINO/minio"
chmod 700 "$DESTINO" "$DESTINO/minio"
cd "$DESTINO"

# Se reutiliza la CA para que el ca.pem ya repartido a los workers siga siendo valido.
if [[ ! -f ca.key || ! -f ca.pem ]]; then
  openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.key
  openssl req -x509 -new -key ca.key -sha256 -days 365 -subj "/CN=ms-demo-ca" -out ca.pem \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out server.key
openssl req -new -key server.key -subj "/CN=$NOMBRE" -out server.csr
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -sha256 -days 90 -out server.pem \
  -extfile <(printf '%s\n' \
    "subjectAltName=IP:$NODE_IP,DNS:$NOMBRE,DNS:localhost,DNS:redis,DNS:minio,DNS:coordinator" \
    "basicConstraints=critical,CA:FALSE" "keyUsage=critical,digitalSignature" "extendedKeyUsage=serverAuth")
rm -f server.csr

# MinIO exige estos nombres en su directorio de certificados.
cp server.pem minio/public.crt
cp server.key minio/private.key
chmod 600 ca.key server.key minio/private.key
chmod 644 ca.pem server.pem minio/public.crt

echo "Certificados en $DESTINO. Copia solo ca.pem a los workers."
