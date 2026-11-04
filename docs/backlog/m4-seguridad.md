# Área: M4 · Seguridad

### US-26 · Autenticación y roles (F-26) · P2 · H3
- **Responsable:** K · **Depende de:** F-01
Como administrador, quiero que cada rol solo haga lo permitido para proteger la información.
- **Dado** usuarios analista, supervisor y administrador
- **Cuando** cada uno intenta cada acción, o no presenta token
- **Entonces** se cumple la matriz de permisos, con 401 sin token y 403 sin permiso
- **Pruebas:** U matriz paramétrica. I API con JWT real. A accesos denegados en demo.
- **Demuestra:** prueba I. **Evidencia:** ficha M4: `curl` y códigos por rol.

### US-27 · TLS entre nodos (F-27) · P2 · H3
- **Responsable:** K · **Depende de:** F-38
Como responsable de seguridad, quiero cifrar la comunicación entre nodos para que no pueda leerse en la red.
- **Dado** el sistema procesando un mensaje con un marcador sintético
- **Cuando** se captura el tráfico entre nodos
- **Entonces** hay handshake TLS y el marcador no aparece en la captura; un cliente sin la CA es rechazado
- **Pruebas:** I cliente sin CA falla; conexión sin TLS a Redis falla. A captura real.
- **Demuestra:** captura. **Evidencia:** ficha M4: `tcpdump`, `tshark`, `strings`.

### US-28 · Cifrado en reposo (F-28) · P2 · H3
- **Responsable:** K · **Depende de:** F-23
Como responsable de seguridad, quiero las evidencias cifradas y las llaves fuera del código para proteger el almacenamiento.
- **Dado** una evidencia almacenada con un marcador sintético
- **Cuando** se lee directo de MinIO, o se busca en el historial de Git
- **Entonces** no contiene el marcador, un byte alterado hace fallar el descifrado, falla sin KEK y no hay llaves en el historial
- **Pruebas:** U ida y vuelta, alteración, nonce y falta de KEK. I objeto real en MinIO.
- **Demuestra:** prueba I y búsqueda en historial. **Evidencia:** ficha M4: comandos y justificación de AD-16.

### US-29 · Cadena de custodia (F-29) · P2 · H3
- **Responsable:** K · **Depende de:** F-23
Como supervisor, quiero una cadena verificable para demostrar que las evidencias no se alteraron.
- **Dado** evidencias procesadas, con entrada de ingreso y de cada transformación
- **Cuando** se altera una evidencia, una entrada, o se trunca el log
- **Entonces** el verificador falla e indica la posición; sin alteraciones, pasa
- **Pruebas:** U enlace, alteración, truncamiento y evidencia alterada. A manipulación real en demo.
- **Demuestra:** prueba A. **Evidencia:** ficha M4: salida del verificador antes y después.

### US-30 · Workers sin privilegios (F-30) · P2 · H3
- **Responsable:** K · **Depende de:** F-38
Como responsable de seguridad, quiero workers sin root para limitar el daño de un compromiso.
- **Dado** los workers desplegados en los tres nodos
- **Cuando** se inspeccionan
- **Entonces** su UID es distinto de 0, la raíz es de solo lectura, se eliminan capacidades y procesan normalmente
- **Pruebas:** I `id -u` y escritura fallida en `/`. A sub-tarea completada bajo esa configuración.
- **Demuestra:** prueba I. **Evidencia:** ficha M4: `docker exec` e `inspect`.
