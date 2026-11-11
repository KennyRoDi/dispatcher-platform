import hashlib
import json
import random
import re
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.adapters.chat_export_generator import (
    ATTACHMENT_TEXT,
    SYNTHETIC_SENDERS,
    THREAT_PHRASES,
    THREAT_RATIO,
    export_plan_chats,
    generate_chat,
    render_telegram,
    render_whatsapp,
)
from src.domain.chat_message import ChatMessage
from src.domain.dataset_plan import CasePlan, DatasetParams, DatasetPlan, plan_dataset

CABECERA_WHATSAPP = re.compile(
    r"^(\d{1,2})/(\d{1,2})/(\d{2}), (\d{2}):(\d{2}) - ([^:\n]+): (.*)$"
)
DATO_REAL = re.compile(r"@|https?://|www\.|\d{7,}")
FECHA_UNIX = re.compile(r'"date_unixtime": "\d+",\n')
UTC = timezone.utc


def _parsear_whatsapp(texto: str) -> list[tuple[datetime, str, str]]:
    mensajes: list[list] = []
    for linea in texto.split("\n"):
        cabecera = CABECERA_WHATSAPP.match(linea)
        if cabecera:
            dia, mes, anio, hora, minuto, remitente, cuerpo = cabecera.groups()
            instante = datetime(2000 + int(anio), int(mes), int(dia), int(hora), int(minuto), tzinfo=UTC)
            mensajes.append([instante, remitente, cuerpo])
        elif linea and mensajes:
            mensajes[-1][2] += "\n" + linea
    return [tuple(m) for m in mensajes]


def _parsear_telegram(texto: str) -> list[tuple[datetime, str, str]]:
    exportacion = json.loads(texto)
    return [
        (datetime.fromtimestamp(int(m["date_unixtime"]), tz=UTC), m["from"], m["text"])
        for m in exportacion["messages"]
        if m["type"] == "message"
    ]


def _tripletas(mensajes) -> list[tuple[datetime, str, str]]:
    return [(m.timestamp_utc, m.sender, m.text) for m in mensajes]


def _contiene_amenaza(texto: str) -> bool:
    return any(frase in texto for frase in THREAT_PHRASES)


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _params_pequenos(**cambios) -> DatasetParams:
    return replace(DatasetParams(), messages=1_200, **cambios)


@pytest.fixture(scope="module")
def plan_completo():
    return plan_dataset(7, DatasetParams())


@pytest.fixture(scope="module")
def exportacion_completa(plan_completo, tmp_path_factory):
    destino = tmp_path_factory.mktemp("chats")
    return plan_completo, destino, export_plan_chats(plan_completo, destino)


@pytest.mark.parametrize("cantidad", [0, 1, 7, 250, 2_000])
def test_genera_exactamente_la_cantidad_pedida(cantidad):
    mensajes = generate_chat(seed=3, count=cantidad)

    assert len(mensajes) == cantidad
    assert all(isinstance(m, ChatMessage) for m in mensajes)


def test_misma_semilla_produce_los_mismos_mensajes():
    assert generate_chat(seed=11, count=500) == generate_chat(seed=11, count=500)


def test_semillas_distintas_producen_mensajes_distintos():
    assert generate_chat(seed=11, count=500) != generate_chat(seed=12, count=500)


def test_la_generacion_no_usa_reloj_ni_sleep_ni_random_global(monkeypatch):
    def prohibido(*_args, **_kwargs):
        raise AssertionError("el generador debe ser puro y determinista")

    esperado = generate_chat(seed=5, count=300)
    for nombre in ("time", "monotonic", "sleep"):
        monkeypatch.setattr(time, nombre, prohibido)
    for nombre in ("random", "randint", "choice", "choices", "shuffle", "uniform"):
        monkeypatch.setattr(random, nombre, prohibido)

    assert generate_chat(seed=5, count=300) == esperado


def test_timestamps_en_utc_crecientes_y_a_minuto_exacto():
    mensajes = generate_chat(seed=2, count=400)

    instantes = [m.timestamp_utc for m in mensajes]
    assert all(i.utcoffset() == timedelta(0) for i in instantes)
    assert all(i.second == 0 and i.microsecond == 0 for i in instantes)
    assert instantes == sorted(instantes)


def test_cada_mensaje_tiene_referencia_de_origen():
    mensajes = generate_chat(seed=2, count=50)

    assert all(m.source_ref for m in mensajes)
    assert len({m.source_ref for m in mensajes}) == len(mensajes)


def test_remitentes_son_ficticios_y_varios():
    mensajes = generate_chat(seed=4, count=600)

    remitentes = {m.sender for m in mensajes}
    assert len(SYNTHETIC_SENDERS) >= 3
    assert all("Sintétic" in nombre for nombre in SYNTHETIC_SENDERS)
    assert remitentes <= set(SYNTHETIC_SENDERS)
    assert len(remitentes) >= 3


def test_mensajes_no_contienen_datos_reales():
    mensajes = generate_chat(seed=4, count=1_500)

    assert not [m.text for m in mensajes if DATO_REAL.search(m.text)]
    assert not [m.sender for m in mensajes if DATO_REAL.search(m.sender)]


def test_amenazas_ficticias_en_la_proporcion_declarada():
    mensajes = generate_chat(seed=9, count=2_000)

    amenazas = [m for m in mensajes if _contiene_amenaza(m.text)]
    assert len(THREAT_PHRASES) >= 3
    assert len(set(THREAT_PHRASES)) == len(THREAT_PHRASES)
    assert 0 < THREAT_RATIO <= 0.2
    assert abs(len(amenazas) / len(mensajes) - THREAT_RATIO) <= 0.01


def test_proporcion_de_amenazas_cero_no_genera_amenazas():
    mensajes = generate_chat(seed=9, count=800, threat_ratio=0.0)

    assert not [m for m in mensajes if _contiene_amenaza(m.text)]


def test_los_adjuntos_no_son_amenazas():
    mensajes = generate_chat(seed=9, count=2_000)

    adjuntos = [m for m in mensajes if m.text == ATTACHMENT_TEXT]
    assert adjuntos
    assert not [m for m in adjuntos if _contiene_amenaza(m.text)]


def test_hay_mensajes_multilinea_y_adjuntos():
    mensajes = generate_chat(seed=1, count=1_000)

    assert any("\n" in m.text for m in mensajes)
    assert any(m.text == ATTACHMENT_TEXT for m in mensajes)
    assert all(m.text.strip() for m in mensajes)


def test_lineas_de_continuacion_no_imitan_una_cabecera():
    mensajes = generate_chat(seed=1, count=3_000)

    continuaciones = [linea for m in mensajes for linea in m.text.split("\n")[1:]]
    assert continuaciones
    assert not [linea for linea in continuaciones if CABECERA_WHATSAPP.match(linea) or not linea.strip()]


def test_exportacion_whatsapp_se_parsea_con_timestamp_y_remitente():
    mensajes = generate_chat(seed=8, count=600)

    exportado = render_whatsapp(mensajes)

    assert _parsear_whatsapp(exportado) == _tripletas(mensajes)
    primera = exportado.split("\n")[0]
    assert CABECERA_WHATSAPP.match(primera)
    assert primera.startswith(
        f"{mensajes[0].timestamp_utc.day}/{mensajes[0].timestamp_utc.month}/{mensajes[0].timestamp_utc:%y}, "
        f"{mensajes[0].timestamp_utc:%H:%M} - {mensajes[0].sender}: "
    )


def test_whatsapp_escribe_los_adjuntos_con_el_marcador_y_multilinea_en_lineas_aparte():
    mensajes = generate_chat(seed=8, count=600)

    lineas = render_whatsapp(mensajes).split("\n")

    assert any(linea.endswith(f": {ATTACHMENT_TEXT}") for linea in lineas)
    multilinea = next(m for m in mensajes if "\n" in m.text)
    primera, *resto = multilinea.text.split("\n")
    indice = next(i for i, linea in enumerate(lineas) if linea.endswith(f": {primera}") and multilinea.sender in linea)
    assert lineas[indice + 1 : indice + 1 + len(resto)] == resto


def test_whatsapp_de_cero_mensajes_es_texto_vacio():
    assert _parsear_whatsapp(render_whatsapp([])) == []


def test_exportacion_telegram_es_json_con_fecha_unix_remitente_y_texto():
    mensajes = generate_chat(seed=8, count=600)

    exportado = render_telegram(mensajes)

    assert _parsear_telegram(exportado) == _tripletas(mensajes)
    primero = json.loads(exportado)["messages"][0]
    assert primero["type"] == "message"
    assert primero["date"] == mensajes[0].timestamp_utc.strftime("%Y-%m-%dT%H:%M:%S")
    assert [m["id"] for m in json.loads(exportado)["messages"]] == list(range(1, 601))


def test_telegram_conserva_utf8_sin_escapes():
    exportado = render_telegram(generate_chat(seed=8, count=100))

    assert "Sintétic" in exportado
    assert "\\u00" not in exportado


def test_whatsapp_conserva_utf8():
    exportado = render_whatsapp(generate_chat(seed=8, count=100))

    assert "Sintétic" in exportado
    assert not exportado.startswith("﻿")


def test_exportaciones_de_los_mismos_mensajes_son_identicas():
    mensajes = generate_chat(seed=6, count=300)

    assert render_whatsapp(mensajes) == render_whatsapp(list(mensajes))
    assert render_telegram(mensajes) == render_telegram(list(mensajes))


def test_los_mensajes_sumados_del_plan_alcanzan_el_parametro(exportacion_completa):
    plan, _, archivos = exportacion_completa

    total = 0
    for caso in plan.cases:
        if caso.messages == 0:
            continue
        ruta = archivos[caso.name]
        texto = ruta.read_text(encoding="utf-8")
        parseados = _parsear_telegram(texto) if ruta.suffix == ".json" else _parsear_whatsapp(texto)
        assert len(parseados) == caso.messages
        total += len(parseados)

    assert total == sum(caso.messages for caso in plan.cases)
    assert total >= DatasetParams().messages


def test_exporta_un_archivo_por_caso_con_mensajes_y_solo_dentro_del_destino(exportacion_completa):
    plan, destino, archivos = exportacion_completa

    assert set(archivos) == {caso.name for caso in plan.cases if caso.messages > 0}
    assert all(ruta.parent == destino for ruta in archivos.values())
    assert set(destino.rglob("*")) == set(archivos.values())


def test_el_plan_usa_ambos_estilos(exportacion_completa):
    _, _, archivos = exportacion_completa

    assert {ruta.suffix for ruta in archivos.values()} == {".txt", ".json"}
    assert all(ruta.name == f"{nombre}-chat{ruta.suffix}" for nombre, ruta in archivos.items())


def test_los_archivos_exportados_son_utf8_validos_sin_datos_reales(exportacion_completa):
    _, _, archivos = exportacion_completa

    for ruta in archivos.values():
        texto = ruta.read_bytes().decode("utf-8")
        assert not DATO_REAL.search(FECHA_UNIX.sub("", texto)), ruta.name


def test_los_casos_no_comparten_el_mismo_contenido(exportacion_completa):
    _, _, archivos = exportacion_completa

    huellas = {nombre: _sha256(ruta) for nombre, ruta in archivos.items()}
    assert len(set(huellas.values())) == len(huellas)


def test_la_exportacion_del_plan_es_reproducible_y_depende_de_la_semilla(tmp_path):
    params = _params_pequenos()
    mismo_a = export_plan_chats(plan_dataset(21, params), tmp_path / "a")
    mismo_b = export_plan_chats(plan_dataset(21, params), tmp_path / "b")
    otro = export_plan_chats(plan_dataset(22, params), tmp_path / "c")

    assert {n: _sha256(r) for n, r in mismo_a.items()} == {n: _sha256(r) for n, r in mismo_b.items()}
    assert {n: _sha256(r) for n, r in mismo_a.items()} != {n: _sha256(r) for n, r in otro.items()}


def test_la_exportacion_crea_el_destino_si_no_existe(tmp_path):
    destino = tmp_path / "no" / "existe"

    archivos = export_plan_chats(plan_dataset(1, _params_pequenos()), destino)

    assert archivos
    assert all(ruta.is_file() for ruta in archivos.values())


def test_la_semilla_del_plan_cambia_el_contenido_con_la_misma_estructura(tmp_path):
    plan = plan_dataset(21, _params_pequenos())
    otra_semilla = replace(plan, seed=plan.seed + 1)

    a = export_plan_chats(plan, tmp_path / "a")
    b = export_plan_chats(otra_semilla, tmp_path / "b")

    assert a.keys() == b.keys()
    assert all(_sha256(a[nombre]) != _sha256(b[nombre]) for nombre in a)


def test_whatsapp_termina_cada_mensaje_con_salto_de_linea():
    exportado = render_whatsapp(generate_chat(seed=8, count=30))

    assert exportado.endswith("\n")
    assert not exportado.endswith("\n\n")


def test_los_renderizadores_normalizan_a_utc_un_mensaje_con_otra_zona():
    costa_rica = timezone(timedelta(hours=-6))
    mensaje = ChatMessage(datetime(2025, 1, 6, 23, 30, tzinfo=costa_rica), "Alma Sintética", "hola", "x-1")

    whatsapp = render_whatsapp([mensaje])
    telegram = json.loads(render_telegram([mensaje]))["messages"][0]

    assert whatsapp.startswith("7/1/25, 05:30 - ")
    assert telegram["date"] == "2025-01-07T05:30:00"


def test_un_nombre_de_caso_no_escribe_fuera_del_destino(tmp_path):
    destino = tmp_path / "salida"
    caso = CasePlan("../escape", "no", ("texto",), 5, 0, 0, 0)
    plan = DatasetPlan(1, (caso,), {}, ())

    try:
        export_plan_chats(plan, destino)
    except ValueError:
        pass

    assert not (tmp_path / "escape-chat.txt").exists()
