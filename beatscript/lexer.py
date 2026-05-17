"""
BeatScript — Analizador Léxico (Etapa 1)
========================================
Compilador de lenguaje de composición musical → MIDI

Tokens reconocidos:
  TEMPO_KW       keyword 'tempo'
  INSTRUMENT_KW  keyword 'instrument'
  TRACK_KW       keyword 'track'
  REPEAT_KW      keyword 'repeat'
  CHORD_KW       keyword 'chord'
  REST           keyword 'rest' (silencio)
  NOTE           nota musical  [A-G][#b]?[0-9]   ej: C4, D#3, Eb5
  DURATION       duración      redonda|blanca|negra|corchea|semicorchea|fusa|semifusa
  INSTR_NAME     nombre MIDI   piano|guitar|violin|...
  NUMBER         entero        [0-9]+
  IDENTIFIER     nombre libre  [a-zA-Z_][a-zA-Z0-9_]*
  LBRACE         {
  RBRACE         }
"""

import ply.lex as lex

# =============================================================
# 1. PALABRAS RESERVADAS
#    Mapa: valor_literal -> tipo_de_token
# =============================================================

RESERVED: dict[str, str] = {
    # Comandos
    "tempo"       : "TEMPO_KW",
    "instrument"  : "INSTRUMENT_KW",
    "track"       : "TRACK_KW",
    "repeat"      : "REPEAT_KW",
    "chord"       : "CHORD_KW",
    "rest"        : "REST",
    "volume"      : "VOLUME_KW",

    # Duraciones musicales
    "redonda"     : "DURATION",
    "blanca"      : "DURATION",
    "negra"       : "DURATION",
    "corchea"     : "DURATION",
    "semicorchea" : "DURATION",
    "fusa"        : "DURATION",
    "semifusa"    : "DURATION",

    # Instrumentos MIDI — cuerdas
    "piano"       : "INSTR_NAME",
    "violin"      : "INSTR_NAME",
    "viola"       : "INSTR_NAME",
    "cello"       : "INSTR_NAME",
    "contrabass"  : "INSTR_NAME",
    "harp"        : "INSTR_NAME",

    # Instrumentos MIDI — vientos madera
    "flute"       : "INSTR_NAME",
    "piccolo"     : "INSTR_NAME",
    "recorder"    : "INSTR_NAME",
    "oboe"        : "INSTR_NAME",
    "clarinet"    : "INSTR_NAME",
    "bassoon"     : "INSTR_NAME",
    "saxophone"   : "INSTR_NAME",

    # Instrumentos MIDI — vientos metal
    "trumpet"     : "INSTR_NAME",
    "trombone"    : "INSTR_NAME",
    "frenchhorn"  : "INSTR_NAME",
    "tuba"        : "INSTR_NAME",

    # Instrumentos MIDI — percusión melódica
    "marimba"     : "INSTR_NAME",
    "vibraphone"  : "INSTR_NAME",
    "xylophone"   : "INSTR_NAME",
    "celesta"     : "INSTR_NAME",
    "drums"       : "INSTR_NAME",

    # Instrumentos MIDI — cuerdas pulsadas / folk
    "guitar"      : "INSTR_NAME",
    "bass"        : "INSTR_NAME",
    "banjo"       : "INSTR_NAME",
    "sitar"       : "INSTR_NAME",
    "harpsichord" : "INSTR_NAME",

    # Instrumentos MIDI — teclados y otros
    "organ"       : "INSTR_NAME",
    "accordion"   : "INSTR_NAME",
    "harmonica"   : "INSTR_NAME",
}

# =============================================================
# 2. LISTA DE TIPOS DE TOKENS
#    PLY requiere esta tupla con todos los nombres de tokens.
# =============================================================

tokens = (
    "TEMPO_KW",
    "INSTRUMENT_KW",
    "TRACK_KW",
    "REPEAT_KW",
    "CHORD_KW",
    "REST",
    "VOLUME_KW",
    "NOTE",
    "DURATION",
    "INSTR_NAME",
    "NUMBER",
    "IDENTIFIER",
    "LBRACE",
    "RBRACE",
)

# =============================================================
# 3. REGLAS LÉXICAS
#
#    Orden de prioridad PLY:
#    1. Funciones: por orden de aparición en el archivo
#       (más arriba = mayor prioridad)
#    2. Strings: por longitud de la cadena regex
#       (más larga = mayor prioridad)
#
#    CRÍTICO: t_NOTE debe definirse ANTES de t_IDENTIFIER
#    para que "C4" sea NOTE y no IDENTIFIER.
# =============================================================

# --- Tokens de un solo carácter (string rules) ---------------
t_LBRACE = r"\{"
t_RBRACE = r"\}"

# --- Nota musical (función = alta prioridad) -----------------
# Regex: [A-Ga-g][#b]?[0-9]
#
# Autómata:
#   q0 --[A-Ga-g]--> q1 --[#b]--> q2 --[0-9]--> q3 (ACCEPT)
#   q0                q1 --[0-9]-------------->  q3 (ACCEPT)
#
# Ejemplos válidos:  C4  D#3  Eb5  G0  Bb4  F#7
# Ejemplos inválidos: C  D#  bass  B (sin octava)
def t_NOTE(t):
    r"[A-Ga-g][#b]?[0-9]"
    t.value = t.value.upper()   # normalizar: c4 → C4, eb3 → EB3
    return t


# --- Número entero -------------------------------------------
# Regex: [0-9]+
#
# Autómata:
#   q0 --[0-9]--> q1* --[0-9]--> q1* (bucle, * = estado final)
def t_NUMBER(t):
    r"[0-9]+"
    t.value = int(t.value)
    return t


# --- Identificador / Palabra reservada ----------------------
# Regex: [a-zA-Z_][a-zA-Z0-9_]*
#
# Autómata:
#   q0 --[a-zA-Z_]--> q1* --[a-zA-Z0-9_]--> q1* (bucle)
#
# Después de capturar el lexema se consulta la tabla RESERVED;
# si existe, se sustituye el tipo; si no, queda como IDENTIFIER.
def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    token_type = RESERVED.get(t.value.lower(), "IDENTIFIER")
    t.type  = token_type
    t.value = t.value.lower() if token_type != "IDENTIFIER" else t.value
    return t


# --- Comentarios (ignorados, no generan token) ---------------
# Regex: #[^\n]*
def t_COMMENT(t):
    r"\#[^\n]*"
    pass  # descartar


# --- Saltos de línea (tracking de número de línea) -----------
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    # No retorna → token descartado, lineno actualizado


# --- Caracteres ignorados (espacios, tabs, retorno) ----------
t_ignore = " \t\r"


# --- Manejo de errores léxicos -------------------------------
def t_error(t):
    col  = _find_column(t.lexer.lexdata, t)
    char = t.value[0]
    msg  = _build_error_msg(char, t.lineno, col)
    if hasattr(t.lexer, "error_list"):
        t.lexer.error_list.append({"line": t.lineno, "col": col, "char": char, "msg": msg})
    else:
        print(msg)
    t.lexer.skip(1)


# =============================================================
# 4. UTILIDADES
# =============================================================

# Mensajes de error específicos por carácter
_ERROR_HINTS: dict[str, str] = {
    "@":  "El símbolo '@' no pertenece al alfabeto de BeatScript.",
    "!":  "El operador '!' no existe en BeatScript.",
    "$":  "El símbolo '$' no es válido.",
    "%":  "El símbolo '%' no es válido.",
    "^":  "El símbolo '^' no es válido.",
    "&":  "El símbolo '&' no es válido.",
    "*":  "Para repetir bloques usa: repeat N { ... }",
    "(":  "Paréntesis no válido — los bloques se delimitan con { }",
    ")":  "Paréntesis no válido — los bloques se delimitan con { }",
    "[":  "Corchete no válido — los bloques se delimitan con { }",
    "]":  "Corchete no válido — los bloques se delimitan con { }",
    ";":  "El ';' no es necesario — cada instrucción va en su propia línea.",
    ":":  "El ':' no es válido en BeatScript.",
    '"':  "Las cadenas de texto no son válidas en BeatScript.",
    "'":  "Las cadenas de texto no son válidas en BeatScript.",
    "+":  "El operador '+' no existe en BeatScript.",
    "-":  "El operador '-' no existe — los valores negativos no son válidos.",
    "=":  "El operador '=' no existe en BeatScript.",
    "<":  "El operador '<' no existe en BeatScript.",
    ">":  "El operador '>' no existe en BeatScript.",
    ",":  "Separa notas con espacios, no con comas: C4 E4 G4 blanca",
    ".":  "El '.' no es válido — BeatScript no usa decimales.",
    "/":  "Para comentarios usa '#', no '/' ni '//'.",
    "\\":  "El '\\' no es válido en BeatScript.",
    "|":  "El '|' no es válido en BeatScript.",
    "~":  "El '~' no es válido en BeatScript.",
    "?":  "El '?' no es válido en BeatScript.",
}


def _build_error_msg(char: str, line: int, col: int) -> str:
    hint = _ERROR_HINTS.get(char, f"'{char}' no pertenece al alfabeto de BeatScript.")
    return f"[ERROR LÉXICO] Línea {line}, Col {col}: carácter '{char}' no reconocido — {hint}"


def _find_column(source: str, token) -> int:
    """Calcula la columna de un token dentro de su línea."""
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1


def build_lexer() -> lex.Lexer:
    """Construye y retorna el objeto lexer de PLY."""
    return lex.lex()


def tokenize(source_code: str, *, debug: bool = False, collect_errors: bool = False):
    """
    Tokeniza el código fuente BeatScript.

    Args:
        source_code:    Texto del programa.
        debug:          Si True, imprime la tabla de tokens por consola.
        collect_errors: Si True, retorna (tokens, errores) en vez de solo tokens.

    Returns:
        Lista de LexToken, o tupla (lista, lista_errores) si collect_errors=True.
    """
    errors = []
    lx = build_lexer()
    lx.error_list = errors
    lx.input(source_code)

    result = list(lx)

    if debug:
        _print_token_table(result, source_code)

    if collect_errors:
        return result, errors
    return result


def _print_token_table(token_list: list, source: str = "") -> None:
    """Imprime la tabla de tokens con formato de consola."""
    W = 68
    print("\n" + "=" * W)
    print(f"{'TABLA DE TOKENS — BeatScript Lexer':^{W}}")
    print("=" * W)
    print(f"{'#':<5} {'TIPO':<18} {'VALOR':<20} {'LÍNEA':<7} {'COL'}")
    print("-" * W)
    for i, tok in enumerate(token_list, 1):
        col = _find_column(source, tok) if source else "-"
        print(f"{i:<5} {tok.type:<18} {str(tok.value):<20} {tok.lineno:<7} {col}")
    print("=" * W)
    print(f"  Total: {len(token_list)} tokens")
    print("=" * W + "\n")


# =============================================================
# 5. DEMO — ejecución directa
# =============================================================

if __name__ == "__main__":
    SAMPLE = """\
# ---- Ejemplo completo BeatScript ----
tempo 120

instrument piano

track melody {
    C4 negra
    D4 negra
    E4 blanca
    F4 corchea
    rest corchea
}

repeat 2 {
    G4 negra
    A4 corchea
    Bb4 semicorchea
}

chord {
    C4 E4 G4 blanca
}
"""
    print("Código fuente:")
    print("-" * 50)
    print(SAMPLE)

    tokenize(SAMPLE, debug=True)
