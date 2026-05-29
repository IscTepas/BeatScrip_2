"""
BeatScript — Analizador Sintáctico (Etapa 2)
=============================================
Parser recursivo descendente → Árbol Sintáctico (AST)

Gramática (Notación EBNF):
  programa    ::= (sentencia)*
  sentencia   ::= tempo | volume | instrument | track | repeat | chord
  tempo       ::= 'tempo' numero
  volume      ::= 'volume' numero
  instrument  ::= 'instrument' instr_name
  track       ::= 'track' identificador '{' (evento)* '}'
  chord       ::= 'chord' '{' NOTE+ DURATION '}'
  evento      ::= nota duracion | rest duracion | chord | repeat numero '{' (evento)* '}'
  nota        ::= NOTE
  rest        ::= 'rest'
  duracion    ::= DURATION
  instr_name  ::= INSTR_NAME
  identificador ::= IDENTIFIER
  numero      ::= NUMBER
"""

import difflib
from beatscript.lexer import RESERVED

# ═══════════════════════════════════════════════════════════════════════════
# 0. UTILIDADES DE SUGERENCIAS
# ═══════════════════════════════════════════════════════════════════════════

def _get_suggestions_for_word(word, keywords_dict=None, cutoff=0.6, max_suggestions=3):
    """
    Encuentra palabras reservadas similares al texto dado usando difflib.

    Args:
        word:            La palabra para la cual buscar sugerencias.
        keywords_dict:   Diccionario de palabras reservadas (default: RESERVED del lexer).
        cutoff:          Umbral de similitud (0.0–1.0, default: 0.6).
        max_suggestions: Número máximo de sugerencias a retornar.

    Returns:
        Lista de palabras sugeridas, ordenadas por similitud.
    """
    if keywords_dict is None:
        keywords_dict = RESERVED

    candidates = list(keywords_dict.keys())
    suggestions = difflib.get_close_matches(
        word.lower(),
        candidates,
        n=max_suggestions,
        cutoff=cutoff,
    )
    return suggestions


# ═══════════════════════════════════════════════════════════════════════════
# 1. CLASES DE NODOS DEL AST
# ═══════════════════════════════════════════════════════════════════════════

class ASTNode:
    """Clase base para todos los nodos del árbol sintáctico."""
    def __repr__(self):
        return f"<{self.__class__.__name__}>"


class Program(ASTNode):
    """Nodo raíz del programa."""
    def __init__(self):
        self.statements = []  # Lista de sentencias globales


class Tempo(ASTNode):
    """Sentencia: tempo <número>"""
    def __init__(self, bpm):
        self.bpm = bpm

    def __repr__(self):
        return f"Tempo({self.bpm})"


class Volume(ASTNode):
    """Sentencia: volume <número>"""
    def __init__(self, level):
        self.level = level

    def __repr__(self):
        return f"Volume({self.level})"


class Instrument(ASTNode):
    """Sentencia: instrument <nombre>"""
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Instrument({self.name})"


class Track(ASTNode):
    """Sentencia: track <nombre> { eventos }"""
    def __init__(self, name, events):
        self.name = name
        self.events = events  # Lista de Note, Rest, Chord, Repeat

    def __repr__(self):
        return f"Track({self.name})"


class Note(ASTNode):
    """Evento: <nota> <duración>"""
    def __init__(self, pitch, duration):
        self.pitch = pitch      # "C4", "D#3", "Eb5", etc.
        self.duration = duration  # "negra", "blanca", etc.

    def __repr__(self):
        return f"Note({self.pitch} {self.duration})"


class Rest(ASTNode):
    """Evento: rest <duración>"""
    def __init__(self, duration):
        self.duration = duration

    def __repr__(self):
        return f"Rest({self.duration})"


class Chord(ASTNode):
    """
    Sentencia/Evento: chord { NOTE+ DURATION }

    Representa un acorde: varias notas tocadas simultáneamente
    con una duración compartida al final del bloque.

    Ejemplo BeatScript:
        chord {
            C4 E4 G4 blanca
        }
    """
    def __init__(self, notes, duration):
        self.notes = notes        # Lista de strings de pitch ["C4", "E4", "G4"]
        self.duration = duration  # Duración compartida: "blanca", "negra", etc.

    def __repr__(self):
        return f"Chord({'+'.join(self.notes)} {self.duration})"


class Repeat(ASTNode):
    """Evento/Sentencia: repeat <número> { eventos }"""
    def __init__(self, count, events):
        self.count = count
        self.events = events  # Lista de eventos o sentencias a repetir

    def __repr__(self):
        return f"Repeat({self.count})"


# ═══════════════════════════════════════════════════════════════════════════
# 2. PARSER RECURSIVO DESCENDENTE
# ═══════════════════════════════════════════════════════════════════════════

class BeatScriptParser:
    """Parser que convierte tokens en un árbol sintáctico (AST)."""

    def __init__(self, tokens, source_code=""):
        """
        Inicializa el parser.

        Args:
            tokens:      Lista de objetos token (con atributos: type, value, lineno, lexpos).
            source_code: Código fuente original; se usa para calcular columnas en errores.
        """
        self.tokens = tokens
        self.source_code = source_code  # Necesario para calcular columnas
        self.pos = 0        # Posición actual en la lista de tokens
        self.errors = []    # Errores de sintaxis encontrados

    # ─────────────────────────────────────────────────────────────────────────
    # CÁLCULO DE COLUMNA (igual al _find_column del lexer)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_column(self, token):
        """
        Calcula la columna (1-indexada) del token dentro de su línea.
        Retorna '?' si no hay código fuente disponible.
        """
        if not self.source_code or not hasattr(token, "lexpos"):
            return "?"
        line_start = self.source_code.rfind("\n", 0, token.lexpos) + 1
        return token.lexpos - line_start + 1

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS DE NAVEGACIÓN
    # ─────────────────────────────────────────────────────────────────────────

    def _current_token(self):
        """Retorna el token actual sin avanzar."""
        if self._is_at_end():
            return None
        return self.tokens[self.pos]

    def _peek_token(self, offset=1):
        """Retorna el token N posiciones adelante."""
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return None
        return self.tokens[pos]

    def _advance(self):
        """Avanza al siguiente token."""
        if not self._is_at_end():
            self.pos += 1

    def _is_at_end(self):
        """Verifica si hemos llegado al final de los tokens."""
        return self.pos >= len(self.tokens)

    def _check(self, token_type):
        """Verifica si el token actual es del tipo especificado."""
        current = self._current_token()
        return current is not None and current.type == token_type

    def _consume(self, token_type, message=None):
        """Consume un token del tipo especificado o genera un error sintáctico."""
        if self._check(token_type):
            token = self._current_token()
            self._advance()
            return token

        current = self._current_token()
        error_msg = (
            message or
            f"Se esperaba '{token_type}', "
            f"se encontró '{current.type if current else 'EOF'}'"
        )
        if current:
            self._add_error_with_suggestions(current, error_msg)
        else:
            self._add_error(f"[EOF] {error_msg}")

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTRO DE ERRORES
    # ─────────────────────────────────────────────────────────────────────────

    def _add_error_with_suggestions(self, token, base_message):
        """
        Registra un error sintáctico con [LÍNEA X, COL Y] y sugerencias opcionales.

        Si el token es un IDENTIFIER similar a una palabra reservada,
        agrega una sugerencia útil al mensaje.
        """
        col = self._get_column(token)
        error_line = f"[LÍNEA {token.lineno}, COL {col}] {base_message}"

        # Buscar palabras reservadas parecidas si el token es un IDENTIFIER
        if token.type == "IDENTIFIER":
            suggestions = _get_suggestions_for_word(
                token.value, cutoff=0.6, max_suggestions=2
            )
            if suggestions:
                sugerencia = " | ".join(f"'{s}'" for s in suggestions)
                error_line += f"\n   💡 Sugerencia: ¿Quisiste decir {sugerencia}?"

        self.errors.append(error_line)

    def _add_error(self, message):
        """Registra un error de sintaxis (mensaje ya formateado)."""
        self.errors.append(message)

    # ─────────────────────────────────────────────────────────────────────────
    # PUNTO DE ENTRADA
    # ─────────────────────────────────────────────────────────────────────────

    def parse(self):
        """
        Parsea el programa completo y retorna el AST.

        Returns:
            Program: Árbol sintáctico del programa.
        """
        program = Program()

        while not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                program.statements.append(stmt)

        return program

    # ─────────────────────────────────────────────────────────────────────────
    # SENTENCIAS (nivel superior)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_statement(self):
        """Parsea una sentencia principal: tempo, volume, instrument, track, chord, repeat."""
        current = self._current_token()

        if current is None:
            return None

        if self._check("TEMPO_KW"):
            return self._parse_tempo()
        elif self._check("VOLUME_KW"):
            return self._parse_volume()
        elif self._check("INSTRUMENT_KW"):
            return self._parse_instrument()
        elif self._check("TRACK_KW"):
            return self._parse_track()
        elif self._check("CHORD_KW"):
            return self._parse_chord()
        elif self._check("REPEAT_KW"):
            return self._parse_repeat_statement()
        else:
            # Token inesperado: reportar error con columna y sugerencias
            col = self._get_column(current)
            if current.type == "IDENTIFIER":
                suggestions = _get_suggestions_for_word(current.value, cutoff=0.5)
                if suggestions:
                    sugerencia = " | ".join(f"'{s}'" for s in suggestions)
                    self._add_error(
                        f"[LÍNEA {current.lineno}, COL {col}] "
                        f"'{current.value}' no es una palabra reservada válida.\n"
                        f"   💡 Sugerencia: ¿Quisiste decir {sugerencia}?"
                    )
                else:
                    self._add_error(
                        f"[LÍNEA {current.lineno}, COL {col}] "
                        f"'{current.value}' no es una palabra reservada válida."
                    )
            else:
                self._add_error(
                    f"[LÍNEA {current.lineno}, COL {col}] "
                    f"Token inesperado: '{current.type}' con valor '{current.value}'"
                )
            self._advance()
            return None

    def _parse_tempo(self):
        """Parsea: tempo <número>"""
        self._consume("TEMPO_KW")
        num_token = self._consume("NUMBER", "Se esperaba un número después de 'tempo'")

        if num_token:
            return Tempo(num_token.value)
        return None

    def _parse_volume(self):
        """Parsea: volume <número>"""
        self._consume("VOLUME_KW")
        num_token = self._consume("NUMBER", "Se esperaba un número después de 'volume'")

        if num_token:
            return Volume(num_token.value)
        return None

    def _parse_instrument(self):
        """Parsea: instrument <nombre_instrumento>"""
        self._consume("INSTRUMENT_KW")
        instr_token = self._consume("INSTR_NAME", "Se esperaba un nombre de instrumento")

        if instr_token:
            return Instrument(instr_token.value)
        return None

    def _parse_track(self):
        """Parsea: track <identificador> { <eventos> }"""
        self._consume("TRACK_KW")
        name_token = self._consume("IDENTIFIER", "Se esperaba un nombre de track")
        self._consume("LBRACE", "Se esperaba '{'")

        events = []
        while not self._check("RBRACE") and not self._is_at_end():
            event = self._parse_event()
            if event:
                events.append(event)

        self._consume("RBRACE", "Se esperaba '}'")

        if name_token:
            return Track(name_token.value, events)
        return None

    def _parse_chord(self):
        """
        Parsea: chord { NOTE+ DURATION }

        Un acorde es un bloque que contiene una o más notas seguidas
        de una única duración compartida por todas ellas.

        Ejemplo:
            chord { C4 E4 G4 blanca }
        """
        kw_token = self._current_token()  # Guardar token 'chord' para errores
        self._consume("CHORD_KW")
        self._consume("LBRACE", "Se esperaba '{' después de 'chord'")

        # Leer todas las notas hasta encontrar una duración o '}'
        notas = []
        while self._check("NOTE") and not self._is_at_end():
            note_token = self._consume("NOTE")
            if note_token:
                notas.append(note_token.value)

        # La duración va al final, compartida por todas las notas
        duration_token = self._consume(
            "DURATION", "Se esperaba una duración al final del acorde"
        )
        self._consume("RBRACE", "Se esperaba '}'")

        if not notas and kw_token:
            col = self._get_column(kw_token)
            self._add_error(
                f"[LÍNEA {kw_token.lineno}, COL {col}] "
                f"El acorde debe contener al menos una nota antes de la duración."
            )
            return None

        if duration_token:
            return Chord(notas, duration_token.value)
        return None

    def _parse_repeat_statement(self):
        """Parsea repeat a nivel de sentencia: repeat <número> { <sentencias> }"""
        self._consume("REPEAT_KW")
        count_token = self._consume("NUMBER", "Se esperaba un número después de 'repeat'")
        self._consume("LBRACE", "Se esperaba '{'")

        statements = []
        while not self._check("RBRACE") and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)

        self._consume("RBRACE", "Se esperaba '}'")

        if count_token:
            return Repeat(count_token.value, statements)
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # EVENTOS (dentro de tracks)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_event(self):
        """Parsea un evento dentro de un track: nota, rest, chord o repeat."""
        current = self._current_token()

        if current is None:
            return None

        if self._check("NOTE"):
            return self._parse_note()
        elif self._check("REST"):
            return self._parse_rest()
        elif self._check("CHORD_KW"):
            return self._parse_chord()
        elif self._check("REPEAT_KW"):
            return self._parse_repeat_event()
        else:
            # Token inesperado: reportar error con columna y sugerencias
            col = self._get_column(current)
            if current.type == "IDENTIFIER":
                suggestions = _get_suggestions_for_word(current.value, cutoff=0.5)
                if suggestions:
                    sugerencia = " | ".join(f"'{s}'" for s in suggestions)
                    self._add_error(
                        f"[LÍNEA {current.lineno}, COL {col}] "
                        f"'{current.value}' no es válido en este contexto.\n"
                        f"   💡 Sugerencia: ¿Quisiste decir {sugerencia}?"
                    )
                else:
                    self._add_error(
                        f"[LÍNEA {current.lineno}, COL {col}] "
                        f"'{current.value}' no es válido en este contexto.\n"
                        f"   (Esperado: nota musical, 'rest', 'chord' o 'repeat')"
                    )
            else:
                self._add_error(
                    f"[LÍNEA {current.lineno}, COL {col}] "
                    f"Evento inesperado: '{current.type}' con valor '{current.value}'"
                )
            self._advance()
            return None

    def _parse_note(self):
        """Parsea: <nota> <duración>"""
        note_token = self._consume("NOTE")
        duration_token = self._consume(
            "DURATION", "Se esperaba una duración después de la nota"
        )

        if note_token and duration_token:
            return Note(note_token.value, duration_token.value)
        return None

    def _parse_rest(self):
        """Parsea: rest <duración>"""
        self._consume("REST")
        duration_token = self._consume(
            "DURATION", "Se esperaba una duración después de 'rest'"
        )

        if duration_token:
            return Rest(duration_token.value)
        return None

    def _parse_repeat_event(self):
        """Parsea repeat a nivel de evento: repeat <número> { <eventos> }"""
        self._consume("REPEAT_KW")
        count_token = self._consume("NUMBER", "Se esperaba un número después de 'repeat'")
        self._consume("LBRACE", "Se esperaba '{'")

        events = []
        while not self._check("RBRACE") and not self._is_at_end():
            event = self._parse_event()
            if event:
                events.append(event)

        self._consume("RBRACE", "Se esperaba '}'")

        if count_token:
            return Repeat(count_token.value, events)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 3. FUNCIÓN DE UTILIDAD PARA CONVERTIR AST A REPRESENTACIÓN DE TABLA
# ═══════════════════════════════════════════════════════════════════════════

def ast_to_table_rows(node, parent_id=""):
    """
    Convierte un nodo AST a una lista de tuplas para insertar en un Treeview.

    Args:
        node:      Nodo AST a convertir.
        parent_id: ID del nodo padre en el Treeview.

    Returns:
        Lista de tuplas (parent_id, node_id, valores, tag).
        tag: "expandable" si tiene hijos, "leaf" si es hoja.
    """
    rows = []

    if isinstance(node, Program):
        for stmt in node.statements:
            rows.extend(ast_to_table_rows(stmt, parent_id))

    elif isinstance(node, Tempo):
        rows.append((parent_id, f"Tempo {node.bpm}", ("Tempo", "Comando", f"{node.bpm} BPM"), "leaf"))

    elif isinstance(node, Volume):
        rows.append((parent_id, f"Volume {node.level}", ("Volume", "Comando", f"{node.level}"), "leaf"))

    elif isinstance(node, Instrument):
        rows.append((parent_id, f"Instrument {node.name}", ("Instrument", "Declaración", node.name), "leaf"))

    elif isinstance(node, Track):
        track_id = f"Track {node.name}"
        rows.append((parent_id, track_id, ("📁 Track", "Declaración", node.name), "expandable"))
        for event in node.events:
            rows.extend(ast_to_table_rows(event, track_id))

    elif isinstance(node, Note):
        rows.append((parent_id, f"Note {node.pitch}", ("🎵 Nota", "Evento", f"{node.pitch} ({node.duration})"), "leaf"))

    elif isinstance(node, Rest):
        rows.append((parent_id, f"Rest {node.duration}", ("⏸️  Silencio", "Evento", node.duration), "leaf"))

    elif isinstance(node, Chord):
        notas_str = " + ".join(node.notes)
        chord_id = f"Chord {notas_str}"
        rows.append((parent_id, chord_id, ("🎼 Chord", "Evento", f"{notas_str} ({node.duration})"), "leaf"))

    elif isinstance(node, Repeat):
        repeat_id = f"Repeat {node.count}"
        rows.append((parent_id, repeat_id, ("🔁 Repeat", "Control", f"{node.count}x"), "expandable"))
        for event in node.events:
            rows.extend(ast_to_table_rows(event, repeat_id))

    return rows


# ═══════════════════════════════════════════════════════════════════════════
# 4. FUNCIÓN DE UTILIDAD PARA VISUALIZACIÓN TIPO ÁRBOL
# ═══════════════════════════════════════════════════════════════════════════

def ast_to_tree_string(node, indent="", is_last=True):
    """
    Convierte un nodo AST a una representación visual estilo árbol de directorios.

    Usa caracteres Unicode:
        ├── rama intermedia
        └── última rama
        │   línea vertical de continuación

    Args:
        node:    Nodo AST a convertir.
        indent:  Espaciado acumulado (para recursión).
        is_last: Si es el último elemento en su nivel.

    Returns:
        String con la representación visual del árbol.
    """
    lines = []

    if isinstance(node, Program):
        lines.append("📋 Program")
        statements = node.statements
        for i, stmt in enumerate(statements):
            is_last_stmt = (i == len(statements) - 1)
            extension = "    " if is_last_stmt else "│   "
            connector = "└── " if is_last_stmt else "├── "
            tree_str = ast_to_tree_string(stmt, indent + extension, is_last_stmt)
            lines.append(indent + connector + tree_str)

    elif isinstance(node, Tempo):
        return f"⏱️  Tempo: {node.bpm} BPM"

    elif isinstance(node, Volume):
        return f"🔊 Volume: {node.level}"

    elif isinstance(node, Instrument):
        return f"🎹 Instrument: {node.name}"

    elif isinstance(node, Track):
        lines.append(f"📁 Track '{node.name}'")
        events = node.events
        for i, event in enumerate(events):
            is_last_event = (i == len(events) - 1)
            extension = "    " if is_last_event else "│   "
            connector = "└── " if is_last_event else "├── "
            tree_str = ast_to_tree_string(event, indent + extension, is_last_event)
            lines.append(indent + connector + tree_str)

    elif isinstance(node, Note):
        return f"🎵 {node.pitch} ({node.duration})"

    elif isinstance(node, Rest):
        return f"⏸️  Silencio ({node.duration})"

    elif isinstance(node, Chord):
        # Mostrar el acorde como un subárbol con sus notas individuales
        lines.append(f"🎼 Chord ({node.duration})")
        for i, pitch in enumerate(node.notes):
            is_last_note = (i == len(node.notes) - 1)
            connector = "└── " if is_last_note else "├── "
            lines.append(indent + connector + f"🎵 {pitch}")

    elif isinstance(node, Repeat):
        lines.append(f"🔁 Repeat ×{node.count}")
        events = node.events
        for i, event in enumerate(events):
            is_last_event = (i == len(events) - 1)
            extension = "    " if is_last_event else "│   "
            connector = "└── " if is_last_event else "├── "
            tree_str = ast_to_tree_string(event, indent + extension, is_last_event)
            lines.append(indent + connector + tree_str)

    return "\n".join(lines) if lines else str(node)
