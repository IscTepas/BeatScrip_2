"""
BeatScript — Análisis Semántico (Fase 3)
========================================
El parser solo comprueba la gramática (que las "oraciones" estén bien formadas).
Este módulo comprueba el SIGNIFICADO y la COHERENCIA del programa: recorre el AST
(no los tokens), construye una tabla de símbolos y aplica reglas de contexto y rango.

Salida de errores:
    [ERROR SEMÁNTICO]   Línea X, Col Y: ...
    [WARNING SEMÁNTICO] Línea X, Col Y: ...

Los errores detienen la compilación; los warnings NO.

Uso:
    from beatscript.semantic import analyze
    result = analyze(ast)
    result.errors      # list[SemanticDiagnostic]
    result.warnings    # list[SemanticDiagnostic]
    result.symbols     # SymbolTable (tracks definidos)
"""

import re
from dataclasses import dataclass

from beatscript.parser import (
    Program, Tempo, Volume, Instrument, Track, Note, Rest, Chord, Repeat,
)

# ---------------------------------------------------------------------------
# 1. LÍMITES 
# ---------------------------------------------------------------------------
TEMPO_MIN, TEMPO_MAX = 20, 400
VOLUME_MIN, VOLUME_MAX = 0, 127
MIDI_MIN, MIDI_MAX = 0, 127
REPEAT_MIN = 1
DEFAULT_INSTRUMENT = "piano"   # programa MIDI 0

# ---------------------------------------------------------------------------
# 2. TABLA DE ERRORES SEMÁNTICOS 
# ---------------------------------------------------------------------------
SEMANTIC_ERRORS = {
    "S1": {"severity": "Error", "rule": "tempo debe ser entero en [20, 400]",
           "example": "tempo 0  /  tempo 5000",
           "cause": "El BPM está fuera del rango permitido.",
           "fix": "Usar un tempo entre 20 y 400."},
    "S2": {"severity": "Error", "rule": "volume debe estar en [0, 127]",
           "example": "volume 150",
           "cause": "El volumen sale del rango de velocity MIDI. (Los negativos, como volume -5, ya los rechaza el lexer.)",
           "fix": "Usar un volumen entre 0 y 127."},
    "S3": {"severity": "Error", "rule": "Toda nota debe caer en MIDI [0, 127]",
           "example": "C10 negra  (MIDI 132)",
           "cause": "La octava hace que el número MIDI de la nota quede fuera de 0-127.",
           "fix": "Bajar la octava (la nota más alta posible es G9)."},
    "S4": {"severity": "Error", "rule": "repeat N requiere N >= 1",
           "example": "repeat 0 { C4 negra }",
           "cause": "Un bloque repetido 0 veces no se ejecuta nunca.",
           "fix": "Usar repeat con un número mayor o igual a 1."},
    "S5": {"severity": "Error", "rule": "Nombres de track únicos (tabla de símbolos)",
           "example": "track melodia {..}  track melodia {..}",
           "cause": "Ya existe un track con ese nombre en la tabla de símbolos.",
           "fix": "Renombrar uno de los dos tracks."},
    "S6": {"severity": "Error", "rule": "chord con >= 1 nota y 1 sola duración, al final",
           "example": "chord { }  /  chord { C4 E4 negra blanca }",
           "cause": "El acorde está vacío, no tiene duración, o la duración compartida está repetida/mal ubicada.",
           "fix": "Escribir todas las notas y UNA duración al final: chord { C4 E4 G4 negra }."},
    "S7": {"severity": "Warning", "rule": "Definir instrumento antes de usarlo (opcional)",
           "example": "track t { C4 negra }  (sin instrument)",
           "cause": "Se usan notas sin haber definido instrumento.",
           "fix": "Escribir 'instrument <nombre>' antes del track. Si no, se usa piano (programa 0)."},
    "S8": {"severity": "Error", "rule": "chord con notas válidas (letra A-G y alteración # o b)",
           "example": "chord { H4 E4 blanca }",
           "cause": "Una de las notas del acorde no es una nota musical válida.",
           "fix": "Usar letras A-G con alteración opcional (# o b) y octava: C4, D#3, Eb5."},
}


# ---------------------------------------------------------------------------
# 3. DIAGNÓSTICOS
# ---------------------------------------------------------------------------
@dataclass
class SemanticDiagnostic:
    code: str          # "S1" ... "S8"
    severity: str      # "Error" | "Warning"
    line: int
    col: int
    message: str

    def __str__(self):
        etiqueta = "ERROR SEMÁNTICO" if self.severity == "Error" else "WARNING SEMÁNTICO"
        pos = f"Línea {self.line}, Col {self.col}" if self.line else "Posición desconocida"
        return f"[{etiqueta}] {pos}: {self.message}  ({self.code})"


# ---------------------------------------------------------------------------
# 4. TABLA DE SÍMBOLOS
# ---------------------------------------------------------------------------
@dataclass
class Symbol:
    name: str
    kind: str          # "track"
    line: int
    col: int
    instrument: str    # instrumento activo al definirse ("piano*" = por defecto)
    events: int        # cantidad de eventos directos del track


class SymbolTable:
    def __init__(self):
        self._symbols: dict[str, Symbol] = {}

    def define(self, symbol: Symbol):
        """Registra el símbolo. Si ya existía devuelve el anterior (duplicado), si no None."""
        previo = self._symbols.get(symbol.name)
        if previo is not None:
            return previo
        self._symbols[symbol.name] = symbol
        return None

    def lookup(self, name):
        return self._symbols.get(name)

    def rows(self):
        return list(self._symbols.values())

    def __len__(self):
        return len(self._symbols)


# ---------------------------------------------------------------------------
# 5. UTILIDAD: nota → número MIDI (misma fórmula que midi_gen, pero con octavas de N dígitos)
# ---------------------------------------------------------------------------
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_RE = re.compile(r"^([A-G])([#B]?)(\d+)$")


def pitch_to_midi(pitch: str) -> int:
    """'C4' → 60, 'D#3' → 51, 'C10' → 132 (el lexer ya normaliza a mayúsculas)."""
    letra, alt, octava = _NOTE_RE.match(pitch.upper()).groups()
    return _SEMITONES[letra] + (int(octava) + 1) * 12 + (1 if alt == "#" else -1 if alt == "B" else 0)


# ---------------------------------------------------------------------------
# 6. ANALIZADOR
# ---------------------------------------------------------------------------
class SemanticAnalyzer:
    """Recorre el AST una sola vez y acumula errores/warnings )."""

    def __init__(self):
        self.diagnostics: list[SemanticDiagnostic] = []
        self.symbols = SymbolTable()
        self._instrument = None    # instrumento vigente mientras se recorre

    # -- resultados ---------------------------------------------------------
    @property
    def errors(self):
        return [d for d in self.diagnostics if d.severity == "Error"]

    @property
    def warnings(self):
        return [d for d in self.diagnostics if d.severity == "Warning"]

    def _report(self, code, line, col, message):
        sev = SEMANTIC_ERRORS[code]["severity"]
        self.diagnostics.append(SemanticDiagnostic(code, sev, line, col, message))

    # -- punto de entrada ---------------------------------------------------
    def analyze(self, program: Program):
        for stmt in program.statements:
            self._visit(stmt)
        self.diagnostics.sort(key=lambda d: (d.line or 0, d.col or 0))
        return self

    # -- despacho -----------------------------------------------------------
    def _visit(self, node, top_level=True):
        if isinstance(node, Tempo):        self._tempo(node)
        elif isinstance(node, Volume):     self._volume(node)
        elif isinstance(node, Instrument): self._instrument = node.name
        elif isinstance(node, Track):      self._track(node)
        elif isinstance(node, Repeat):     self._repeat(node, top_level)
        elif isinstance(node, Chord):      self._chord(node, top_level)
        elif isinstance(node, Note):       self._note(node.pitch, node.arg_line, node.arg_col)
       

    # -- reglas -------------------------------------------------------------
    def _tempo(self, n):                                                    # S1
        if not (TEMPO_MIN <= n.bpm <= TEMPO_MAX):
            lado = "bajo" if n.bpm < TEMPO_MIN else "alto"
            self._report("S1", n.arg_line, n.arg_col,
                         f"BPM {n.bpm} demasiado {lado}: debe estar entre {TEMPO_MIN} y {TEMPO_MAX}")

    def _volume(self, n):                                                   # S2
        if not (VOLUME_MIN <= n.level <= VOLUME_MAX):
            self._report("S2", n.arg_line, n.arg_col,
                         f"volumen {n.level} fuera de rango {VOLUME_MIN}-{VOLUME_MAX}")

    def _note(self, pitch, line, col):                                      # S3
        midi = pitch_to_midi(pitch)
        if not (MIDI_MIN <= midi <= MIDI_MAX):
            self._report("S3", line, col,
                         f"{pitch} = MIDI {midi}, fuera del rango MIDI {MIDI_MIN}-{MIDI_MAX}")

    def _repeat(self, n, top_level):                                        # S4
        if n.count < REPEAT_MIN:
            self._report("S4", n.arg_line, n.arg_col,
                         f"repeat {n.count}: repeat debe ser mayor o igual a {REPEAT_MIN}")
        for hijo in n.events:
            self._visit(hijo, top_level)

    def _track(self, n):                                                    # S5 + S7
        usado = self._instrument or f"{DEFAULT_INSTRUMENT}*"
        previo = self.symbols.define(
            Symbol(n.name, "track", n.arg_line, n.arg_col, usado, len(n.events)))
        if previo is not None:
            self._report("S5", n.arg_line, n.arg_col,
                         f"track '{n.name}' ya está definido (primera definición: "
                         f"línea {previo.line}, col {previo.col})")
        self._warn_sin_instrumento(n.line, n.col, f"track '{n.name}'")
        for ev in n.events:
            self._visit(ev, top_level=False)

    def _chord(self, n, top_level):                                         # S3 + S6 + S8
        for pitch, (l, c) in zip(n.notes, n.note_pos):
            self._note(pitch, l, c)

        for texto, l, c in n.invalid_notes:                                 # S8
            if texto[0].upper() not in _SEMITONES:
                motivo = f"la letra '{texto[0]}' no existe (solo A-G)"
            else:
                motivo = "alteración inválida (solo '#' o 'b')"
            self._report("S8", l, c, f"'{texto}' no es una nota válida: {motivo}")

        n_dur = len(n.durations)                                            # S6
        if not n.notes and not n.invalid_notes:
            self._report("S6", n.line, n.col, "el acorde no tiene notas")
        if n_dur == 0 and (n.notes or n.invalid_notes):
            self._report("S6", n.line, n.col, "el acorde no tiene duración")
        elif n_dur > 1:
            _, l, c = n.durations[1]
            self._report("S6", l, c, "la duración compartida va una sola vez al final")
        elif n.misplaced_pos:
            self._report("S6", *n.misplaced_pos, "la duración compartida va una sola vez al final")

        if top_level:
            self._warn_sin_instrumento(n.line, n.col, "chord")

    def _warn_sin_instrumento(self, line, col, donde):                      # S7
        if self._instrument is None:
            self._report("S7", line, col,
                         f"{donde}: no se definió instrumento; se usará {DEFAULT_INSTRUMENT} (programa 0)")


# ---------------------------------------------------------------------------
# 7. FUNCIÓN PÚBLICA
# ---------------------------------------------------------------------------
def analyze(program: Program) -> SemanticAnalyzer:
    """Ejecuta el análisis semántico completo sobre un AST y devuelve el analizador con resultados."""
    return SemanticAnalyzer().analyze(program)
