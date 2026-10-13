"""
Demo en consola — Análisis Semántico (Fase 3)
================================================
No es un test de pytest (no empieza con "test_" a propósito, para que
pytest no lo intente correr como suite de aserciones): es un script para
EJECUTAR Y VER en vivo, pensado para la presentación al profesor.

Por cada regla S1 a S8 muestra:
    1) un ejemplo de código BeatScript que la viola  -> el error real que produce el compilador
    2) un ejemplo equivalente pero válido             -> confirma que no genera error

Ejecutar (desde la raíz del proyecto, como módulo para que encuentre el
paquete "beatscript" — ejecutarlo como script suelto con
"python beatscript/tests/demo_semantico.py" da ModuleNotFoundError):
    python -X utf8 -m beatscript.tests.demo_semantico
"""

from beatscript.lexer import tokenize
from beatscript.parser import BeatScriptParser
from beatscript.semantic import analyze, SEMANTIC_ERRORS

ANCHO = 78


def compilar(codigo: str):
    """Corre lexer -> parser -> semántico y devuelve el resultado del análisis.

    Si hay errores léxicos o sintácticos los imprime y devuelve None,
    porque en ese caso el análisis semántico ni siquiera llegaría a correr
    sobre un AST válido (así es como funciona el pipeline real).
    """
    tokens, lex_errors = tokenize(codigo, collect_errors=True)
    if lex_errors:
        for e in lex_errors:
            print("  ", e["msg"])
        return None

    parser = BeatScriptParser(tokens, codigo)
    ast = parser.parse()
    if parser.errors:
        for e in parser.errors:
            print("  ", e)
        return None

    return analyze(ast)


def mostrar_caso(etiqueta: str, codigo: str, se_espera_error: bool):
    print(f"  [{etiqueta}]")
    for linea in codigo.strip("\n").splitlines():
        print(f"    {linea}")

    resultado = compilar(codigo)
    if resultado is None:
        print("    -> (no llegó a análisis semántico: hubo error léxico/sintáctico antes)")
        print()
        return

    if not resultado.diagnostics:
        estado = "sin errores ni warnings"
        print(f"    -> {estado}")
    else:
        for d in resultado.diagnostics:
            print(f"    -> {d}")

    if resultado.symbols.rows():
        nombres = ", ".join(s.name for s in resultado.symbols.rows())
        print(f"    (tabla de símbolos: {nombres})")
    print()


def seccion(codigo_regla: str):
    ficha = SEMANTIC_ERRORS[codigo_regla]
    print("=" * ANCHO)
    print(f" Regla {codigo_regla} — {ficha['rule']}  [{ficha['severity']}]")
    print("=" * ANCHO)
    print(f" Causa típica: {ficha['cause']}")
    print(f" Cómo corregir: {ficha['fix']}")
    print()


# ---------------------------------------------------------------------------
# Un caso inválido + uno válido por cada regla S1-S8
# ---------------------------------------------------------------------------

CASOS = {
    "S1": {
        "invalido": "tempo 5000\n",
        "valido":   "tempo 120\n",
    },
    "S2": {
        "invalido": "volume 150\n",
        "valido":   "volume 90\n",
    },
    "S3": {
        "invalido": "instrument piano\ntrack t { C10 negra }\n",
        "valido":   "instrument piano\ntrack t { G9 negra }\n",
    },
    "S4": {
        "invalido": "instrument piano\nrepeat 0 { C4 negra }\n",
        "valido":   "instrument piano\nrepeat 2 { C4 negra }\n",
    },
    "S5": {
        "invalido": "instrument piano\ntrack melodia { C4 negra }\ntrack melodia { D4 negra }\n",
        "valido":   "instrument piano\ntrack melodia { C4 negra }\ntrack acompanamiento { D4 negra }\n",
    },
    "S6": {
        "invalido": "instrument piano\nchord { C4 E4 negra blanca }\n",
        "valido":   "instrument piano\nchord { C4 E4 G4 blanca }\n",
    },
    "S7": {
        "invalido": "track t { C4 negra }\n",
        "valido":   "instrument piano\ntrack t { C4 negra }\n",
    },
    "S8": {
        "invalido": "instrument piano\nchord { H4 E4 blanca }\n",
        "valido":   "instrument piano\nchord { C4 E4 blanca }\n",
    },
}


def main():
    print()
    print("#" * ANCHO)
    print(" DEMO — ANÁLISIS SEMÁNTICO BEATSCRIPT (reglas S1 a S8)".center(ANCHO, " "))
    print("#" * ANCHO)
    print()

    for codigo_regla, casos in CASOS.items():
        seccion(codigo_regla)
        mostrar_caso("INVÁLIDO — debe marcar la regla " + codigo_regla, casos["invalido"], True)
        mostrar_caso("VÁLIDO — no debe marcar nada (o solo otro warning aparte)", casos["valido"], False)

    print("=" * ANCHO)
    print(" Fin de la demo. Las 8 reglas quedaron ejercitadas arriba.".center(ANCHO))
    print("=" * ANCHO)


if __name__ == "__main__":
    main()
