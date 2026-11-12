from scripts.measure.m3_backpressure import percentil, resumir


def test_percentil_de_lista_vacia_es_none():
    assert percentil([], 95) is None


def test_percentil_toma_el_valor_mas_cercano():
    valores = list(range(1, 101))
    assert (percentil(valores, 50), percentil(valores, 95), percentil(valores, 100)) == (51, 95, 100)


def test_resume_profundidad_codigos_y_latencias():
    filas = [
        {"tipo": "muestra", "profundidad": 3},
        {"tipo": "muestra", "profundidad": 7},
        {"tipo": "respuesta", "codigo": 201, "latencia_ms": 10.0},
        {"tipo": "respuesta", "codigo": 503, "latencia_ms": 2.0},
        {"tipo": "respuesta", "codigo": 201, "latencia_ms": 6.0},
    ]
    assert resumir(filas) == {"profundidad_max": 7, "codigos": {201: 2, 503: 1},
                              "latencia_p50_ms": 6.0, "latencia_p95_ms": 10.0, "latencia_media_ms": 6.0}


def test_sin_filas_no_falla():
    assert resumir([])["profundidad_max"] == 0
