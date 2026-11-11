import argparse
import os
import sys
from pathlib import Path

from src.adapters.dataset_truth_files import (
    read_manifest_records,
    read_observed,
    read_sample_records,
    read_sample_truth,
    render_markdown,
    render_text,
)
from src.domain.ground_truth import compare
from src.domain.provenance import SourceRecord, validate_provenance

INTERRUPTED = 130
RENDERERS = {"texto": render_text, "markdown": render_markdown}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 1
    except KeyboardInterrupt:
        return INTERRUPTED
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _procedencia(args: argparse.Namespace) -> int:
    reader = read_manifest_records if args.manifiesto else read_sample_records
    records = reader(Path(args.manifiesto or args.muestra))
    return _report_provenance(records)


def _report_provenance(records: list[SourceRecord]) -> int:
    defects = validate_provenance(records)
    print("\n".join(defects) if defects else f"{len(records)} fuentes cumplen la procedencia")
    return 1 if defects else 0


def _comparar(args: argparse.Namespace) -> int:
    muestra = Path(args.muestra)
    _require_distinct_output(args.salida, muestra, Path(args.salidas))
    defects = validate_provenance(read_sample_records(muestra))
    if defects:
        print("\n".join(defects))
        return 1
    comparison = compare(read_sample_truth(muestra), read_observed(Path(args.salidas)))
    table = RENDERERS[args.formato](comparison)
    if args.salida:
        Path(args.salida).write_text(table + "\n", encoding="utf-8")
    else:
        print(table)
    return 0


def _require_distinct_output(output: str | None, *inputs: Path) -> None:
    if output and any(_same_file(Path(output), source) for source in inputs):
        raise ValueError(f"--salida {output} es una de las entradas; elige otro archivo")


def _same_file(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second)
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Procedencia y verdad de referencia de F-04.")
    commands = parser.add_subparsers(dest="comando", required=True)
    _add_procedencia(commands.add_parser("procedencia", help="valida origen y licencia"))
    _add_comparar(commands.add_parser("comparar", help="compara la muestra con las salidas"))
    return parser


def _add_procedencia(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifiesto", help="manifest.json de F-03")
    source.add_argument("--muestra", help="muestra etiquetada en JSON")
    parser.set_defaults(run=_procedencia)


def _add_comparar(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--muestra", required=True, help="muestra etiquetada en JSON")
    parser.add_argument("--salidas", required=True, help="salidas del analisis en JSON")
    parser.add_argument("--formato", choices=sorted(RENDERERS), default="texto")
    parser.add_argument("--salida", help="archivo donde escribir la tabla")
    parser.set_defaults(run=_comparar)


if __name__ == "__main__":
    sys.exit(main())
