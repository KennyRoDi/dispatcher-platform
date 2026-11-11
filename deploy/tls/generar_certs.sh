#!/usr/bin/env bash
# Genera la CA y el certificado de demo del Nodo A (F-27, SUP-33): EC P-256, CA 365 dias, certificado 90 dias.
# Solo escribe en CERTS_DIR (por defecto $HOME/.ms-certs, fuera del repo). ca.key nunca sale de esta maquina;
# a los workers solo viaja ca.pem. Terceros: openssl (https://docs.openssl.org/), ipaddress de Python.
#   NODE_IP=<ip de tailscale> NODE_NAME=<hostname> bash deploy/tls/generar_certs.sh
set -euo pipefail
umask 077

DESTINO="${CERTS_DIR:-$HOME/.ms-certs}"
: "${NODE_IP:?define NODE_IP con la IP de Tailscale del Nodo A}"
NOMBRE="${NODE_NAME:-$(hostname)}"
ETIQUETA='[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?'
SEGUNDOS_CERT=$((90 * 86400))

fallar() { echo "$1" >&2; exit 1; }

# Todo se valida antes de crear nada: un fallo no deja CA, llaves ni carpetas a medias.
[[ "$NODE_IP" =~ ^[0-9A-Fa-f.:]+$ ]] && python3 -c 'import ipaddress, sys; ipaddress.ip_address(sys.argv[1])' "$NODE_IP" 2>/dev/null \
  || fallar "NODE_IP no es una direccion IPv4 ni IPv6 valida"
[[ ${#NOMBRE} -le 253 && "$NOMBRE" =~ ^$ETIQUETA(\.$ETIQUETA)*$ ]] \
  || fallar "NODE_NAME no es un nombre de host valido (letras, digitos, guion y punto; sin guion al inicio)"
DESTINO="$(realpath -m -- "$DESTINO")"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
[[ "$DESTINO" != "$REPO" && "$DESTINO" != "$REPO"/* ]] || fallar "CERTS_DIR no puede estar dentro del repositorio"

mkdir -p "$DESTINO/minio"
chmod 700 "$DESTINO" "$DESTINO/minio"
TMP="$(mktemp -d "$DESTINO/.tmp.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
cd "$DESTINO"

nueva_llave() { openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$1"; }

# Se reutiliza la CA mientras viva mas que un certificado nuevo, para que el ca.pem ya repartido siga valido.
# Si esta por vencer se regenera: hay que volver a copiar ca.pem a los workers.
CA_NUEVA=0
if [[ -f ca.key && -f ca.pem ]]; then
  [[ "$(openssl pkey -in ca.key -pubout)" == "$(openssl x509 -in ca.pem -noout -pubkey)" ]] \
    || fallar "ca.key y ca.pem no corresponden: borra ambos para crear una CA nueva"
  openssl x509 -in ca.pem -noout -checkend $((SEGUNDOS_CERT + 86400)) >/dev/null || { echo "La CA vence pronto: se regenera; copia el nuevo ca.pem a los workers" >&2; CA_NUEVA=1; }
else
  CA_NUEVA=1
fi
if [[ $CA_NUEVA == 1 ]]; then
  nueva_llave "$TMP/ca.key"
  openssl req -x509 -new -key "$TMP/ca.key" -sha256 -days 365 -subj "/CN=ms-demo-ca" -out "$TMP/ca.pem" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" -addext "keyUsage=critical,keyCertSign,cRLSign"
  CA_KEY="$TMP/ca.key"; CA_PEM="$TMP/ca.pem"
else
  CA_KEY=ca.key; CA_PEM=ca.pem
fi

nueva_llave "$TMP/server.key"
openssl req -new -key "$TMP/server.key" -subj "/CN=$NOMBRE" -out "$TMP/server.csr"
openssl x509 -req -in "$TMP/server.csr" -CA "$CA_PEM" -CAkey "$CA_KEY" -CAserial "$TMP/ca.srl" -CAcreateserial -sha256 -days 90 -out "$TMP/server.pem" \
  -extfile <(printf '%s\n' \
    "subjectAltName=IP:$NODE_IP,DNS:$NOMBRE,DNS:localhost,DNS:redis,DNS:minio,DNS:coordinator" \
    "basicConstraints=critical,CA:FALSE" "keyUsage=critical,digitalSignature" "extendedKeyUsage=serverAuth")

# MinIO exige estos nombres en su directorio de certificados.
cp "$TMP/server.pem" "$TMP/public.crt"
cp "$TMP/server.key" "$TMP/private.key"
chmod 600 "$TMP"/*.key
chmod 644 "$TMP"/*.pem "$TMP/public.crt"

# Con todo generado y firmado, se publica: un fallo anterior no deja llave nueva con certificado viejo.
if [[ $CA_NUEVA == 1 ]]; then
  mv -f "$TMP/ca.key" ca.key; mv -f "$TMP/ca.pem" ca.pem; mv -f "$TMP/ca.srl" ca.srl
fi
mv -f "$TMP/server.key" server.key; mv -f "$TMP/server.pem" server.pem
mv -f "$TMP/private.key" minio/private.key; mv -f "$TMP/public.crt" minio/public.crt

echo "Certificados en $DESTINO. Copia solo ca.pem a los workers."
