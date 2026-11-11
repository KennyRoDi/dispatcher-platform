**PRUEBA LOCAL: una sola máquina, datos sintéticos; no acredita la prueba A en nodos reales ni la ficha M4.**

# F-29: prueba A local sintética, 2026-11-11

Salida del verificador `scripts.verify_custody` sobre un log y una evidencia sintéticos, íntegros y luego manipulados. La llave y los hashes de ejemplo no son secretos: son datos generados solo para esta ejecución. Los casos 9 a 11 comprueban que la herramienta falla cerrada ante una llave inválida o ausente.

Salida tal como la produjo la ejecución (código de salida en `exit=`):

```
### 0. sin manipular
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
ok: la cadena de custodia no tiene alteraciones
exit=0

### 1. campo alterado en la entrada 2 (actor)
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 2: sello: el HMAC de la entrada no coincide
exit=1

### 2. linea 2 borrada
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 2: enlace: se esperaba seq 1 enlazada a la entrada anterior
exit=1

### 3. lineas 2 y 3 reordenadas
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 2: enlace: se esperaba seq 1 enlazada a la entrada anterior
exit=1

### 4. log truncado a 2 entradas (ancla intacta)
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 4: truncado: el log termina antes del último eslabón anclado
exit=1

### 5. log truncado y ancla borrada
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 2: ancla: falta el ancla del último eslabón
exit=1

### 6. cadena recalculada con SHA-256 sin la llave
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 1: sello: el HMAC de la entrada no coincide
exit=1

### 7. evidencia A alterada en el almacen
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 1: evidencia: se esperaba 16c267304ca4751c82289e04534ecf81c7a05cbd92ef55b498ab2732963429a6 y el objeto tiene 39f9888144a85b84ca894d5b1ca8ef270d61a30dbb883d07df2916e657ac0166
exit=1

### 8. evidencia B borrada del almacen
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
posicion 4: evidencia: falta el objeto 953879138efe098f8d2be3414965a0b508ff07ae2570943c855599edbb73e0fb
exit=1

### 9. llave con permisos 0644 (falla cerrado)
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
no se pudo verificar: KEK_FILE debe tener permisos 0400 o 0600
exit=2

### 10. llave de 16 bytes (falla cerrado)
$ CUSTODY_KEY_FILE=custodia.custody-key python -m scripts.verify_custody --log custodia.jsonl --anchor custodia.jsonl.head --store objetos
no se pudo verificar: la KEK debe ser de 32 bytes y estar bien codificada
exit=2

### 11. sin CUSTODY_KEY_FILE
no se pudo verificar: falta la variable CUSTODY_KEY_FILE
exit=2
```
