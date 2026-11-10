import hashlib
import json
import re
from pathlib import Path

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, build_manifest, main, validate_manifest
from src.adapters.document_generator import generate_documents
from src.adapters.heavy_case_generator import generate_heavy_cases
from src.adapters.media_generator import generate_media
from src.domain.dataset_plan import IMAGE_CATEGORIES, MIB, DatasetParams, plan_dataset

FIELDS = {
    "case",
    "kind",
    "path",
    "bytes",
    "sha256",
    "origen",
    "licencia",
    "semilla",
    "etiqueta",
    "heterogeneo",
    "categoria",
    "positivo",
    "duracion_s",
}
LICENCIA = "generado por el equipo, uso academico"
KINDS = {"texto", "imagen", "audio", "video", "documento"}
ETIQUETAS = {"imagen": {"positivo", "neutro"}, "audio": {"tono", "ruido"}}
REDUCED = {
    "cases": 8,
    "light_heterogeneous": 2,
    "heavy_heterogeneous": 2,
    "messages": 200,
    "images": 60,
    "audios": 24,
    "heavy_bytes": 1024,
}
VIDEO_SUFFIX = ".mpg"


class FakeRunner:
    def __init__(self, video_bytes: int = 2048):
        self.calls: list[list[str]] = []
        self.video_bytes = video_bytes

    def __call__(self, args: list[str]) -> None:
        self.calls.append(list(args))
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix == VIDEO_SUFFIX:
            with output.open("wb") as handle:
                handle.truncate(self.video_bytes)
            return
        output.write_bytes(hashlib.sha256(" ".join(args[:-1]).encode()).digest())


class ForbiddenRunner:
    def __call__(self, args: list[str]) -> None:
        raise AssertionError("--validar no debe generar archivos")


def _params_file(tmp_path: Path, **overrides) -> Path:
    path = tmp_path / "params.json"
    path.write_text(json.dumps({**REDUCED, **overrides}), encoding="utf-8")
    return path


def _generate(out: Path, tmp_path: Path, seed: int = 1, runner=None, params: Path | None = None) -> int:
    argv = ["--seed", str(seed), "--out", str(out), "--params", str(params or _params_file(tmp_path))]
    return main(argv, runner=runner or FakeRunner())


def _rows(out: Path) -> list[dict]:
    return json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(MIB), b""):
            digest.update(block)
    return digest.hexdigest()


def _tipos_por_caso(rows: list[dict], nivel: str) -> dict[str, set[str]]:
    tipos: dict[str, set[str]] = {r["case"]: set() for r in rows if r["heterogeneo"] == nivel}
    for row in rows:
        if row["case"] in tipos:
            tipos[row["case"]].add(row["kind"])
    return tipos


def _guardar(out: Path, rows: list[dict]) -> None:
    (out / MANIFEST_NAME).write_text(json.dumps(rows), encoding="utf-8")


def _files_on_disk(out: Path) -> set[str]:
    return {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file() and p.name != MANIFEST_NAME}


@pytest.fixture
def reduced(tmp_path):
    out = tmp_path / "out"
    assert _generate(out, tmp_path) == 0
    return out


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    out = tmp_path_factory.mktemp("completo") / "out"
    runner = FakeRunner(video_bytes=200 * MIB)
    assert main(["--seed", "1", "--out", str(out)], runner=runner) == 0
    return out, _rows(out)


def test_el_manifiesto_tiene_los_campos_exactos_y_valores_fijos(reduced):
    rows = _rows(reduced)

    assert rows
    for row in rows:
        assert set(row) == FIELDS
        assert row["origen"] == "sintetico"
        assert row["licencia"] == LICENCIA
        assert row["semilla"] == 1
        assert row["kind"] in KINDS
        assert row["heterogeneo"] in {"liviano", "pesado", "no"}
        assert isinstance(row["bytes"], int) and row["bytes"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])


def test_el_manifiesto_no_lleva_marca_de_tiempo(reduced):
    texto = (reduced / MANIFEST_NAME).read_text(encoding="utf-8")

    assert not re.search(r"\d{4}-\d{2}-\d{2}", texto)
    assert not any(re.search(r"time|fecha|generated|date", name) for row in _rows(reduced) for name in row)


def test_las_etiquetas_solo_existen_en_imagenes_y_audios(reduced):
    for row in _rows(reduced):
        if row["kind"] in ETIQUETAS:
            assert row["etiqueta"] in ETIQUETAS[row["kind"]]
        else:
            assert row["etiqueta"] is None


def test_categoria_y_positivo_solo_existen_en_imagenes(reduced):
    for row in _rows(reduced):
        if row["kind"] == "imagen":
            assert row["categoria"] in IMAGE_CATEGORIES
            assert row["positivo"] is (row["etiqueta"] == "positivo")
        else:
            assert row["categoria"] is None
            assert row["positivo"] is None


def test_duracion_solo_existe_en_audios_y_es_un_entero_positivo(reduced):
    for row in _rows(reduced):
        if row["kind"] == "audio":
            assert isinstance(row["duracion_s"], int) and not isinstance(row["duracion_s"], bool)
            assert row["duracion_s"] > 0
        else:
            assert row["duracion_s"] is None


def test_los_audios_declaran_duraciones_distintas(reduced):
    duraciones = {r["duracion_s"] for r in _rows(reduced) if r["kind"] == "audio"}

    assert len(duraciones) >= 2


def test_cada_categoria_de_imagen_declara_positivos_y_no_positivos(reduced):
    rows = [r for r in _rows(reduced) if r["kind"] == "imagen"]

    for categoria in IMAGE_CATEGORIES:
        positivos = {r["positivo"] for r in rows if r["categoria"] == categoria}
        assert positivos == {True, False}


def test_las_rutas_son_relativas_y_el_manifiesto_describe_cada_archivo_del_disco(reduced):
    rows = _rows(reduced)

    assert all(not Path(row["path"]).is_absolute() and ".." not in Path(row["path"]).parts for row in rows)
    assert {row["path"] for row in rows} == _files_on_disk(reduced)
    assert len({row["path"] for row in rows}) == len(rows)


def test_bytes_y_sha256_coinciden_con_el_disco(reduced):
    for row in _rows(reduced):
        path = reduced / row["path"]
        assert row["bytes"] == path.stat().st_size
        assert row["sha256"] == _sha256(path)


def test_las_filas_estan_ordenadas_por_caso_y_ruta(reduced):
    rows = _rows(reduced)

    assert rows == sorted(rows, key=lambda row: (row["case"], row["path"]))


def test_las_filas_unifican_chat_imagenes_audios_y_videos_del_plan(reduced):
    plan = plan_dataset(1, DatasetParams(**REDUCED))
    rows = _rows(reduced)
    por_tipo = {kind: [r for r in rows if r["kind"] == kind] for kind in KINDS}

    assert len(por_tipo["imagen"]) == REDUCED["images"]
    assert len(por_tipo["audio"]) == REDUCED["audios"]
    assert {r["case"] for r in por_tipo["texto"]} == {c.name for c in plan.cases if c.messages}
    assert {r["case"] for r in por_tipo["video"]} == {c.name for c in plan.cases if c.heavy_bytes}
    assert {r["case"] for r in por_tipo["documento"]} == {c.name for c in plan.cases if c.heterogeneo == "liviano"}
    assert {r["case"] for r in rows} <= {c.name for c in plan.cases}
    assert {r["heterogeneo"] for r in rows if r["case"] == plan.cases[0].name} == {plan.cases[0].heterogeneo}


def test_las_filas_conservan_etiqueta_y_bytes_de_los_generadores(tmp_path, reduced):
    plan = plan_dataset(1, DatasetParams(**REDUCED))
    media = generate_media(plan, tmp_path / "media", FakeRunner())
    heavy = generate_heavy_cases(plan, tmp_path / "heavy", FakeRunner())
    documentos = generate_documents(plan, tmp_path / "docs")
    rows = _rows(reduced)

    etiquetas = sorted((f.case, f.kind, f.etiqueta, f.categoria, f.duration_s) for f in media)
    assert etiquetas == sorted(
        (r["case"], r["kind"], r["etiqueta"], r["categoria"], r["duracion_s"]) for r in rows if r["kind"] in ETIQUETAS
    )
    assert sorted(f.case for f in documentos) == sorted(r["case"] for r in rows if r["kind"] == "documento")
    assert sorted((f.case, f.bytes) for f in heavy) == sorted((r["case"], r["bytes"]) for r in rows if r["kind"] == "video")


def test_build_manifest_devuelve_las_filas_que_escribe_la_cli(tmp_path, reduced):
    plan = plan_dataset(1, DatasetParams(**REDUCED))

    assert build_manifest(plan, tmp_path / "otro", FakeRunner()) == _rows(reduced)


def test_la_misma_semilla_produce_el_mismo_manifiesto(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    assert _generate(first, tmp_path, seed=3) == 0
    assert _generate(second, tmp_path, seed=3) == 0

    assert (first / MANIFEST_NAME).read_bytes() == (second / MANIFEST_NAME).read_bytes()


def test_semillas_distintas_producen_manifiestos_distintos(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    assert _generate(first, tmp_path, seed=3) == 0
    assert _generate(second, tmp_path, seed=4) == 0

    assert _rows(first) != _rows(second)
    assert {r["sha256"] for r in _rows(first) if r["kind"] == "imagen"} != {
        r["sha256"] for r in _rows(second) if r["kind"] == "imagen"
    }


def test_hay_cinco_heterogeneos_livianos_y_cinco_pesados(complete):
    _, rows = complete
    niveles = {}
    for row in rows:
        niveles.setdefault(row["heterogeneo"], set()).add(row["case"])

    assert len(niveles["liviano"]) == 5
    assert len(niveles["pesado"]) == 5
    assert niveles["liviano"].isdisjoint(niveles["pesado"])


def test_cada_heterogeneo_pesado_tiene_un_archivo_de_al_menos_200_mib(complete):
    _, rows = complete
    pesados = {r["case"] for r in rows if r["heterogeneo"] == "pesado"}

    for caso in pesados:
        assert any(r["case"] == caso and r["kind"] == "video" and r["bytes"] >= 200 * MIB for r in rows)


def test_los_heterogeneos_livianos_no_tienen_archivos_pesados(complete):
    _, rows = complete

    assert all(r["bytes"] < 200 * MIB for r in rows if r["heterogeneo"] != "pesado")


def test_los_heterogeneos_livianos_incluyen_texto_imagen_audio_y_documento(complete):
    _, rows = complete
    tipos = _tipos_por_caso(rows, "liviano")

    assert len(tipos) == 5
    assert all({"texto", "imagen", "audio", "documento"} <= kinds for kinds in tipos.values())


def test_los_heterogeneos_pesados_incluyen_texto_imagen_audio_y_video(complete):
    _, rows = complete
    tipos = _tipos_por_caso(rows, "pesado")

    assert len(tipos) == 5
    assert all({"texto", "imagen", "audio", "video"} <= kinds for kinds in tipos.values())


def test_el_dataset_por_defecto_cumple_los_minimos_de_b3(complete):
    out, rows = complete

    assert len({r["case"] for r in rows}) >= 40
    assert sum(r["kind"] == "imagen" for r in rows) >= 300
    assert sum(r["kind"] == "audio" for r in rows) >= 150
    assert validate_manifest(out / MANIFEST_NAME) == []


def test_validar_sobre_un_dataset_completo_sale_con_cero(complete, capsys):
    out, _ = complete

    assert main(["--validar", "--out", str(out)], runner=ForbiddenRunner()) == 0
    assert capsys.readouterr().out.strip()


def test_validar_reporta_cada_minimo_incumplido(reduced):
    esperado = {
        "casos: 8 de al menos 40",
        "casos heterogeneos: 4 de al menos 10",
        "casos heterogeneos livianos: 2 de al menos 5",
        "casos heterogeneos pesados: 2 de al menos 5",
        "casos pesados de al menos 200 MiB: 0 de al menos 5",
        "mensajes: 200 de al menos 20000",
        "imagenes: 60 de al menos 300",
        "audios: 24 de al menos 150",
    }

    assert set(validate_manifest(reduced / MANIFEST_NAME)) >= esperado


def test_validar_sale_distinto_de_cero_y_muestra_los_incumplimientos(reduced, capsys):
    antes = _files_on_disk(reduced)

    codigo = main(["--validar", "--out", str(reduced)], runner=ForbiddenRunner())

    salida = capsys.readouterr().out
    assert codigo != 0
    for etiqueta in ("casos:", "mensajes:", "imagenes:", "audios:", "casos heterogeneos pesados:"):
        assert etiqueta in salida
    assert _files_on_disk(reduced) == antes


def test_validar_sin_manifiesto_sale_distinto_de_cero(tmp_path):
    assert main(["--validar", "--out", str(tmp_path / "vacio")], runner=ForbiddenRunner()) != 0


def test_validar_detecta_un_archivo_alterado_con_el_mismo_tamano(reduced):
    fila = next(r for r in _rows(reduced) if r["kind"] == "imagen")
    (reduced / fila["path"]).write_bytes(b"x" * fila["bytes"])

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(fila["path"] in p and "sha256" in p for p in problemas)


def test_validar_detecta_un_archivo_truncado(reduced):
    fila = next(r for r in _rows(reduced) if r["kind"] == "audio")
    (reduced / fila["path"]).write_bytes(b"x")

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(fila["path"] in p and "bytes" in p for p in problemas)


def test_validar_detecta_un_archivo_ausente(reduced):
    fila = next(r for r in _rows(reduced) if r["kind"] == "imagen")
    (reduced / fila["path"]).unlink()

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(fila["path"] in p and "no existe" in p for p in problemas)


@pytest.mark.parametrize("campo,valor", [("origen", "kaggle"), ("licencia", "MIT")])
def test_validar_rechaza_origen_o_licencia_distintos(reduced, campo, valor):
    rows = _rows(reduced)
    rows[0][campo] = valor
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(campo in p and rows[0]["path"] in p for p in problemas)


def test_validar_no_reporta_duraciones_ni_categorias_en_un_dataset_coherente(reduced):
    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert not any("duraciones" in p or "categoria" in p for p in problemas)


def test_validar_reporta_menos_de_dos_duraciones_de_audio_distintas(reduced):
    rows = _rows(reduced)
    for row in rows:
        if row["kind"] == "audio":
            row["duracion_s"] = 30
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert "duraciones de audio distintas: 1 de al menos 2" in problemas


@pytest.mark.parametrize("declarado", [True, False, None])
def test_validar_reporta_una_categoria_sin_proporcion_positiva_declarada(reduced, declarado):
    rows = _rows(reduced)
    for row in rows:
        if row["kind"] == "imagen" and row["categoria"] == "objetos":
            row["positivo"] = declarado
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    asunto = [p for p in problemas if "categoria" in p]
    assert len(asunto) == 1
    assert "objetos" in asunto[0] and "proporcion positiva" in asunto[0]


def test_validar_reporta_una_categoria_de_imagen_sin_filas(reduced):
    rows = [r for r in _rows(reduced) if not (r["kind"] == "imagen" and r["categoria"] == "paisajes")]
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any("paisajes" in p and "proporcion positiva" in p for p in problemas)


def test_la_cli_escribe_en_out_y_no_en_el_directorio_de_trabajo(tmp_path, monkeypatch):
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    monkeypatch.chdir(trabajo)
    out = tmp_path / "salida" / "dataset"

    assert _generate(out, tmp_path) == 0

    assert (out / MANIFEST_NAME).is_file()
    assert list(trabajo.iterdir()) == []


def test_params_ajusta_los_conteos_del_plan(tmp_path):
    out = tmp_path / "out"
    params = _params_file(tmp_path, images=30, audios=12)

    assert _generate(out, tmp_path, params=params) == 0

    rows = _rows(out)
    assert sum(r["kind"] == "imagen" for r in rows) == 30
    assert sum(r["kind"] == "audio" for r in rows) == 12


def test_la_cli_exige_out(tmp_path):
    with pytest.raises(SystemExit) as salida:
        main(["--seed", "1", "--params", str(_params_file(tmp_path))], runner=FakeRunner())

    assert salida.value.code != 0
