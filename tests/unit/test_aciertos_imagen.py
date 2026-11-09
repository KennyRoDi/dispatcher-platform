import json
import re
import tomllib
from pathlib import Path

import pytest

from scripts.aciertos_imagen import (
    EtiquetaImagen,
    FilaAciertos,
    ResultadoImagen,
    construir_analizador,
    evaluar,
    generar_markdown,
    leer_etiquetas,
    main,
    tabla_aciertos,
)
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.image_detection import Detection

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config" / "imagen.toml"
MUESTRA_REPO = RAIZ / "tests" / "datos" / "imagenes"
ETIQUETAS_REPO = MUESTRA_REPO / "etiquetas.json"
CATEGORIAS = ("arma",)
SHA = "a" * 64
VERSIONES = {"ultralytics": "8.4.208", "torch": "2.15.0"}
PROPIA = {"procedencia": "Foto tomada por el equipo para F-08", "licencia": "CC BY 4.0"}


def escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def imagen(archivo, categoria="arma", **cambios):
    return {"archivo": archivo, "categoria": categoria, **PROPIA, **cambios}


@pytest.fixture
def muestra(tmp_path):
    directorio = tmp_path / "imagenes"
    directorio.mkdir()
    for nombre in ("cuchillo_1.jpg", "cuchillo_2.jpg", "mesa_1.jpg", "mesa_2.jpg"):
        (directorio / nombre).write_bytes(f"bytes sinteticos de {nombre}".encode())
    return directorio


def etiquetas_de_muestra(muestra):
    return escribir_json(
        muestra / "etiquetas.json",
        {
            "imagenes": [
                imagen("cuchillo_1.jpg"),
                imagen("cuchillo_2.jpg"),
                imagen("mesa_1.jpg", None),
                imagen("mesa_2.jpg", None),
            ]
        },
    )


def finding(categoria="arma", confianza=0.9):
    return Finding(categoria, Severity.ALTA, confianza, EvidenceRef(SHA, "caja 1,2,3,4"), "knife ×1")


class FakeAnalyzer:
    def __init__(self, por_archivo):
        self.por_archivo = por_archivo
        self.llamadas = []

    def analyze(self, path):
        self.llamadas.append(Path(path))
        return list(self.por_archivo.get(Path(path).name, ()))


class FakeObjectDetector:
    def __init__(self, por_archivo):
        self.por_archivo = por_archivo

    def detect(self, path):
        return list(self.por_archivo.get(Path(path).name, ()))


def test_lee_etiquetas_con_categoria_procedencia_y_licencia(muestra):
    etiquetas = leer_etiquetas(etiquetas_de_muestra(muestra), muestra, CATEGORIAS)

    assert etiquetas[0] == EtiquetaImagen("cuchillo_1.jpg", "arma", PROPIA["procedencia"], PROPIA["licencia"])
    assert [e.archivo for e in etiquetas] == ["cuchillo_1.jpg", "cuchillo_2.jpg", "mesa_1.jpg", "mesa_2.jpg"]
    assert [e.categoria for e in etiquetas] == ["arma", "arma", None, None]


@pytest.mark.parametrize(
    "entrada",
    [
        {"archivo": "cuchillo_1.jpg", "categoria": "arma", "licencia": "CC BY 4.0"},
        {"archivo": "cuchillo_1.jpg", "categoria": "arma", "procedencia": "Foto propia"},
        imagen("cuchillo_1.jpg", procedencia=""),
        imagen("cuchillo_1.jpg", licencia="   "),
        imagen("no_existe.jpg"),
        imagen("cuchillo_1.jpg", "explosivo"),
        imagen("cuchillo_1.jpg", ""),
        {"archivo": "cuchillo_1.jpg", **PROPIA},
        imagen("../imagenes/cuchillo_1.jpg"),
    ],
    ids=[
        "sin-procedencia",
        "sin-licencia",
        "procedencia-vacia",
        "licencia-en-blanco",
        "archivo-inexistente",
        "categoria-desconocida",
        "categoria-vacia",
        "sin-categoria",
        "ruta-fuera-de-la-muestra",
    ],
)
def test_etiqueta_invalida_se_rechaza(muestra, entrada):
    ruta = escribir_json(muestra / "etiquetas.json", {"imagenes": [entrada]})

    with pytest.raises(ValueError):
        leer_etiquetas(ruta, muestra, CATEGORIAS)


@pytest.mark.parametrize(
    "datos",
    [{}, {"imagenes": []}, {"imagenes": "cuchillo_1.jpg"}, {"imagenes": [imagen("cuchillo_1.jpg"), imagen("cuchillo_1.jpg")]}],
    ids=["sin-imagenes", "lista-vacia", "no-es-lista", "archivo-repetido"],
)
def test_etiquetas_mal_formadas_se_rechazan(muestra, datos):
    with pytest.raises(ValueError):
        leer_etiquetas(escribir_json(muestra / "etiquetas.json", datos), muestra, CATEGORIAS)


def test_evalua_cada_imagen_de_la_muestra_con_el_analizador(muestra):
    etiquetas = leer_etiquetas(etiquetas_de_muestra(muestra), muestra, CATEGORIAS)
    analizador = FakeAnalyzer({"cuchillo_1.jpg": [finding(confianza=0.8)], "mesa_2.jpg": [finding(confianza=0.3)]})

    resultados = evaluar(analizador, muestra, etiquetas)

    assert analizador.llamadas == [muestra / e.archivo for e in etiquetas]
    assert [(r.archivo, r.esperada) for r in resultados] == [
        ("cuchillo_1.jpg", "arma"),
        ("cuchillo_2.jpg", "arma"),
        ("mesa_1.jpg", None),
        ("mesa_2.jpg", None),
    ]
    assert [len(r.hallazgos) for r in resultados] == [1, 0, 0, 1]
    assert resultados[0].hallazgos[0].confidence == pytest.approx(0.8)


def resultado(archivo, esperada, *categorias):
    return ResultadoImagen(archivo, esperada, tuple(finding(categoria) for categoria in categorias))


def resultados_de_ejemplo():
    return [
        resultado("cuchillo_1.jpg", "arma", "arma"),
        resultado("cuchillo_2.jpg", "arma", "arma"),
        resultado("cuchillo_3.jpg", "arma"),
        resultado("mesa_1.jpg", None, "arma"),
        resultado("mesa_2.jpg", None),
        resultado("mesa_3.jpg", None),
        resultado("mesa_4.jpg", None),
    ]


def test_tabla_por_categoria_con_verdaderos_y_falsos_positivos_y_negativos():
    assert tabla_aciertos(resultados_de_ejemplo(), CATEGORIAS) == [
        FilaAciertos("arma", verdaderos_positivos=2, falsos_positivos=1, falsos_negativos=1, verdaderos_negativos=3),
    ]


def test_tabla_incluye_las_categorias_sin_imagenes_positivas():
    filas = tabla_aciertos([resultado("mesa_1.jpg", None)], ("arma", "droga"))

    assert filas == [
        FilaAciertos("arma", 0, 0, 0, 1),
        FilaAciertos("droga", 0, 0, 0, 1),
    ]


def test_hallazgo_de_otra_categoria_es_falso_positivo_de_esa_y_falso_negativo_de_la_esperada():
    filas = tabla_aciertos([resultado("cuchillo_1.jpg", "arma", "droga")], ("arma", "droga"))

    assert filas == [
        FilaAciertos("arma", 0, 0, 1, 0),
        FilaAciertos("droga", 0, 1, 0, 0),
    ]


def leer_config():
    with open(CONFIG, "rb") as archivo:
        return tomllib.load(archivo)


def etiquetas_de_ejemplo():
    otra = {"procedencia": "COCO val2017, imagen 000000000139", "licencia": "CC BY 2.0"}
    return [
        EtiquetaImagen(r.archivo, r.esperada, *(otra.values() if r.archivo == "mesa_4.jpg" else PROPIA.values()))
        for r in resultados_de_ejemplo()
    ]


def test_markdown_de_evidencia_declara_comando_versiones_pesos_umbral_muestra_y_tabla():
    config = leer_config()
    comando = "python -m scripts.aciertos_imagen --muestra m --etiquetas e.json --salida s.md"

    texto = generar_markdown(comando, config, VERSIONES, etiquetas_de_ejemplo(), resultados_de_ejemplo())

    assert comando in texto
    assert "ultralytics" in texto and "8.4.208" in texto
    assert "torch" in texto and "2.15.0" in texto
    assert config["modelo"]["pesos"] in texto
    assert config["modelo"]["sha256"] in texto
    assert re.search(r"[Uu]mbral mínimo\D*0\.25\b", texto)
    assert re.search(r"\b7 imágenes\b", texto)
    assert re.search(r"\b3 positivas\b", texto) and re.search(r"\b4 negativas\b", texto)
    for declarada in ("Foto tomada por el equipo para F-08", "CC BY 4.0", "COCO val2017, imagen 000000000139", "CC BY 2.0"):
        assert declarada in texto
    assert "| Categoría | VP | FP | FN | VN |" in texto
    assert "| arma | 2 | 1 | 1 | 3 |" in texto


def test_markdown_detalla_cada_imagen_con_esperada_obtenida_y_confianza():
    texto = generar_markdown("cmd", leer_config(), VERSIONES, etiquetas_de_ejemplo(), resultados_de_ejemplo())

    for archivo in ("cuchillo_1.jpg", "cuchillo_3.jpg", "mesa_1.jpg", "mesa_4.jpg"):
        assert archivo in texto
    assert "ninguna" in texto
    assert "0.90" in texto


def test_markdown_solo_contiene_lo_que_sale_de_los_resultados():
    config = leer_config()
    todo_bien = [resultado("cuchillo_1.jpg", "arma", "arma"), resultado("mesa_1.jpg", None)]
    etiquetas = [EtiquetaImagen(r.archivo, r.esperada, *PROPIA.values()) for r in todo_bien]

    texto = generar_markdown("cmd", config, VERSIONES, etiquetas, todo_bien)

    assert "| arma | 1 | 0 | 0 | 1 |" in texto
    assert re.search(r"\b2 imágenes\b", texto)
    assert "| arma | 2 | 1 | 1 | 3 |" not in texto


def test_markdown_declara_sus_limites():
    texto = generar_markdown("cmd", leer_config(), VERSIONES, etiquetas_de_ejemplo(), resultados_de_ejemplo())

    assert "## Límites" in texto
    limites = texto.split("## Límites", 1)[1].lower()
    assert re.search(r"\b7 imágenes\b", limites)
    assert "knife" in limites


def test_analizador_usa_la_configuracion_del_repositorio(muestra):
    detector = FakeObjectDetector({"cuchillo_1.jpg": [Detection("knife", 0.9, (1, 2, 3, 4)), Detection("person", 0.9, (0, 0, 5, 5))]})

    analizador = construir_analizador(CONFIG, detector)

    [hallazgo] = analizador.analyze(muestra / "cuchillo_1.jpg")
    assert (hallazgo.category, hallazgo.severity) == ("arma", Severity.ALTA)
    assert analizador.analyze(muestra / "mesa_1.jpg") == []


def argumentos(muestra, etiquetas, salida):
    return ["--muestra", str(muestra), "--etiquetas", str(etiquetas), "--salida", str(salida)]


def test_main_escribe_la_evidencia_con_el_comando_exacto(muestra, tmp_path):
    salida = tmp_path / "evidencia" / "F-08_aciertos.md"
    argv = argumentos(muestra, etiquetas_de_muestra(muestra), salida)
    detector = FakeObjectDetector({"cuchillo_1.jpg": [Detection("knife", 0.9, (1, 2, 3, 4))]})

    assert main(argv, detector=detector, versiones=VERSIONES) == 0

    texto = salida.read_text(encoding="utf-8")
    assert "python -m scripts.aciertos_imagen " + " ".join(argv) in texto
    assert "| arma | 1 | 0 | 1 | 2 |" in texto


def test_main_con_etiquetas_invalidas_falla_sin_escribir(muestra, tmp_path, capsys):
    etiquetas = escribir_json(muestra / "etiquetas.json", {"imagenes": [imagen("cuchillo_1.jpg", licencia="")]})
    salida = tmp_path / "F-08_aciertos.md"

    assert main(argumentos(muestra, etiquetas, salida), detector=FakeObjectDetector({}), versiones=VERSIONES) == 1

    assert "licencia" in capsys.readouterr().err
    assert not salida.exists()


def test_main_con_muestra_que_no_es_directorio_falla_sin_escribir(muestra, tmp_path, capsys):
    etiquetas = etiquetas_de_muestra(muestra)
    salida = tmp_path / "F-08_aciertos.md"

    codigo = main(argumentos(tmp_path / "no_existe", etiquetas, salida), detector=FakeObjectDetector({}), versiones=VERSIONES)

    assert codigo == 1
    assert "no_existe" in capsys.readouterr().err
    assert not salida.exists()


def test_main_con_imagen_ilegible_falla_sin_escribir(muestra, tmp_path, capsys):
    class DetectorQueRechaza:
        def detect(self, path):
            raise ValueError(f"no es una imagen legible: {path}")

    salida = tmp_path / "F-08_aciertos.md"

    assert main(argumentos(muestra, etiquetas_de_muestra(muestra), salida), detector=DetectorQueRechaza(), versiones=VERSIONES) == 1

    assert "legible" in capsys.readouterr().err
    assert not salida.exists()


@pytest.mark.parametrize("faltante", ["--muestra", "--etiquetas", "--salida"])
def test_main_exige_cada_argumento(muestra, tmp_path, faltante):
    argv = argumentos(muestra, etiquetas_de_muestra(muestra), tmp_path / "s.md")
    indice = argv.index(faltante)
    del argv[indice : indice + 2]

    with pytest.raises(SystemExit) as salida:
        main(argv, detector=FakeObjectDetector({}), versiones=VERSIONES)

    assert salida.value.code == 2


def test_muestra_del_repositorio_declara_procedencia_y_licencia_y_tiene_positivas_y_negativas():
    # La muestra son fotos que toma José Andrés en esta parte; sin ellas la parte no puede cerrar [B.3].
    assert ETIQUETAS_REPO.is_file(), "falta tests/datos/imagenes/etiquetas.json con la muestra etiquetada"
    categorias = tuple(sorted(set(leer_config()["clases"].values())))

    etiquetas = leer_etiquetas(ETIQUETAS_REPO, MUESTRA_REPO, categorias)

    positivas = [e for e in etiquetas if e.categoria is not None]
    assert positivas and len(positivas) < len(etiquetas)
