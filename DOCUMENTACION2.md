# BeatScript — Guía de Estudio Completa

> Compilador de lenguaje musical → MIDI. Cubre análisis léxico, análisis
> sintáctico, AST, árbol de derivación y generación de MIDI.

---

## Índice

1. [Visión general del proyecto](#1-visión-general-del-proyecto)
2. [Estructura de archivos](#2-estructura-de-archivos)
3. [Etapa 1 — Análisis Léxico (`lexer.py`)](#3-etapa-1--análisis-léxico-lexerpy)
   - Autómatas y expresiones regulares
   - Tokens reconocidos
   - Palabras reservadas
   - Función `tokenize`
4. [Etapa 2 — Análisis Sintáctico (`parser.py`)](#4-etapa-2--análisis-sintáctico-parserpy)
   - Gramática EBNF
   - Nodos del AST
   - Parser recursivo descendente
   - Manejo de errores con columnas
   - Sugerencias con `difflib`
5. [Árbol Sintáctico Abstracto (AST)](#5-árbol-sintáctico-abstracto-ast)
6. [Árbol de Derivación Visual (`generate_visual_tree`)](#6-árbol-de-derivación-visual-generate_visual_tree)
7. [Etapa 4 — Generación MIDI (`midi_gen.py`)](#7-etapa-4--generación-midi-midi_genpy)
8. [Interfaz gráfica (`main_gui.py`)](#8-interfaz-gráfica-main_guipy)
9. [Flujo completo de compilación](#9-flujo-completo-de-compilación)
10. [Tests del lexer](#10-tests-del-lexer)
11. [Dependencias externas](#11-dependencias-externas)

---

## 1. Visión general del proyecto

BeatScript es un lenguaje de dominio específico (DSL) para componer música.
El usuario escribe código como:

```beatscript
# Ejemplo BeatScript
tempo 120
volume 80
instrument violin

track melodia {
    C4 negra
    D4 negra
    E4 blanca
    rest corchea
    chord { C4 E4 G4 blanca }
    repeat 2 {
        G4 negra
        A4 negra
    }
}
```

El compilador lo convierte en un archivo MIDI (`.mid`) que se reproduce
directamente desde la interfaz. Las etapas son:

```
Código fuente
     │
     ▼
[Etapa 1] Lexer     → lista de tokens
     │
     ▼
[Etapa 2] Parser    → AST (árbol sintáctico abstracto)
     │
     ▼
[Etapa 4] MIDI gen  → output.mid
     │
     ▼
pygame.mixer        → reproducción de audio
```

---

## 2. Estructura de archivos

```
BeatScript/
├── main_gui.py                  ← IDE (interfaz gráfica, orquesta todo)
├── beatscript/
│   ├── __init__.py
│   ├── lexer.py                 ← Etapa 1: Analizador léxico (PLY)
│   ├── parser.py                ← Etapa 2: Parser + AST + Graphviz
│   ├── midi_gen.py              ← Etapa 4: Generación de MIDI
│   └── tests/
│       ├── __init__.py
│       └── test_lexer.py        ← Suite de tests del lexer
├── test_suggestions.py
├── test_tree_visual.py
└── ESTUDIO_BEATSCRIPT.md        ← este archivo
```

---

## 3. Etapa 1 — Análisis Léxico (`lexer.py`)

**Archivo:** [beatscript/lexer.py](beatscript/lexer.py)

El lexer transforma el código fuente (una cadena de texto) en una secuencia
de **tokens**. Cada token tiene: `type`, `value`, `lineno`, `lexpos`.

### 3.1 Biblioteca PLY

BeatScript usa **PLY (Python Lex-Yacc)**. PLY construye el lexer a partir
de:
- Cadenas regex asignadas a variables `t_NOMBRE = r"..."`
- Funciones `def t_NOMBRE(t):` que dan mayor prioridad y permiten código
  adicional (transformar el valor, consultar tablas, etc.)

PLY aplica las reglas en este orden de prioridad:

| Prioridad | Tipo de regla | Criterio de desempate |
|-----------|---------------|-----------------------|
| 1 (mayor) | Funciones `def t_X(t)` | Orden de aparición en el archivo |
| 2         | Cadenas `t_X = r"..."` | Longitud del regex (mayor = primero) |

### 3.2 Expresiones regulares y autómatas

Cada token tiene un regex y un autómata finito determinista (AFD) implícito.

---

#### TOKEN: `NOTE` — Nota musical

```
Regex:   [A-Ga-g][#b]?[0-9]
```

**Autómata:**

```
        [A-Ga-g]        [#b]           [0-9]
  q0 ──────────► q1 ──────────► q2 ──────────► q3 (ACCEPT)
                 │                              ▲
                 └──────────── [0-9] ───────────┘
```

- `q0` → estado inicial
- `q1` → leímos la letra de la nota (C, D, E, F, G, A, B)
- `q2` → leímos la alteración opcional (# o b)
- `q3` → ACCEPT, leímos el dígito de la octava

**Ejemplos válidos:** `C4`, `D#3`, `Eb5`, `G0`, `Bb4`, `F#7`
**Ejemplos inválidos:** `C`, `D#`, `bass`, `H4`

El lexer normaliza a mayúsculas: `c4` → `C4`, `eb3` → `EB3`.

**Código:** [lexer.py:139-142](beatscript/lexer.py#L139-L142)

---

#### TOKEN: `NUMBER` — Número entero

```
Regex:   [0-9]+
```

**Autómata:**

```
        [0-9]          [0-9]
  q0 ──────────► q1* ──────────► q1*  (bucle, * = estado final ACCEPT)
```

El valor se convierte a `int` dentro de la función `t_NUMBER`.

**Código:** [lexer.py:150-153](beatscript/lexer.py#L150-L153)

---

#### TOKEN: `IDENTIFIER` / palabras reservadas

```
Regex:   [a-zA-Z_][a-zA-Z0-9_]*
```

**Autómata:**

```
      [a-zA-Z_]       [a-zA-Z0-9_]
  q0 ──────────► q1* ──────────────► q1*  (bucle)
```

Después de capturar el lexema, se consulta la tabla `RESERVED`.
Si el valor (en minúsculas) existe en el diccionario, el tipo cambia
al tipo correspondiente. Si no, queda como `IDENTIFIER`.

```python
# Código en t_IDENTIFIER:
token_type = RESERVED.get(t.value.lower(), "IDENTIFIER")
t.type  = token_type
t.value = t.value.lower() if token_type != "IDENTIFIER" else t.value
```

**Código:** [lexer.py:164-169](beatscript/lexer.py#L164-L169)

---

#### TOKEN: `LBRACE` / `RBRACE`

```
t_LBRACE = r"\{"
t_RBRACE = r"\}"
```

Son cadenas simples (no funciones), por lo que tienen menor prioridad que
las funciones, pero tienen prioridad entre sí por longitud (ambas son `\{`
y `\}`, longitud 2).

---

#### Comentarios (descartados)

```
Regex:   #[^\n]*
```

La función `t_COMMENT` no retorna nada → el token se descarta y no aparece
en la lista de resultados.

---

#### Saltos de línea (tracking de línea)

```
Regex:   \n+
```

`t_newline` incrementa `t.lexer.lineno` en la cantidad de saltos de línea
leídos. No retorna token → se descarta, pero el contador de líneas avanza.

---

### 3.3 Tabla de tokens reconocidos

| Token | Tipo | Ejemplos |
|-------|------|---------|
| `TEMPO_KW` | Keyword | `tempo` |
| `VOLUME_KW` | Keyword | `volume` |
| `INSTRUMENT_KW` | Keyword | `instrument` |
| `TRACK_KW` | Keyword | `track` |
| `REPEAT_KW` | Keyword | `repeat` |
| `CHORD_KW` | Keyword | `chord` |
| `REST` | Keyword | `rest` |
| `NOTE` | Nota musical | `C4` `D#3` `Eb5` |
| `DURATION` | Duración | `negra` `blanca` `corchea` |
| `INSTR_NAME` | Instrumento MIDI | `piano` `violin` `guitar` |
| `NUMBER` | Entero | `120` `2` `80` |
| `IDENTIFIER` | Nombre libre | `melody` `coro` `my_track` |
| `LBRACE` | Delimitador | `{` |
| `RBRACE` | Delimitador | `}` |

### 3.4 Palabras reservadas (`RESERVED`)

El diccionario `RESERVED` en [lexer.py:29-89](beatscript/lexer.py#L29-L89)
mapea literales a tipos de token. Incluye:

- **Comandos:** `tempo`, `volume`, `instrument`, `track`, `repeat`, `chord`, `rest`
- **Duraciones:** `redonda`, `blanca`, `negra`, `corchea`, `semicorchea`, `fusa`, `semifusa`
- **Instrumentos MIDI (32 total):** piano, violin, viola, cello, contrabass, harp, flute, piccolo, recorder, oboe, clarinet, bassoon, saxophone, trumpet, trombone, frenchhorn, tuba, marimba, vibraphone, xylophone, celesta, drums, guitar, bass, banjo, sitar, harpsichord, organ, accordion, harmonica

### 3.5 Cálculo de columna

```python
def _find_column(source: str, token) -> int:
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

`token.lexpos` es el offset absoluto (en bytes) desde el inicio del string.
`rfind("\n", 0, lexpos)` encuentra el último salto de línea antes de la
posición del token. Restar esa posición da la columna (base 1).

**Código:** [lexer.py:243-246](beatscript/lexer.py#L243-L246)

### 3.6 Manejo de errores léxicos

`t_error` reporta el carácter no reconocido y avanza uno para continuar.
Los mensajes se acumulan en `t.lexer.error_list` si está definida.

El diccionario `_ERROR_HINTS` ([lexer.py:207-235](beatscript/lexer.py#L207-L235))
provee mensajes específicos para ~25 caracteres comunes de otros lenguajes
(`@`, `!`, `;`, `(`, `)`, `*`, etc.).

### 3.7 API pública del lexer

```python
from beatscript.lexer import tokenize

# Uso básico
tokens = tokenize(source_code)

# Con recolección de errores léxicos
tokens, errors = tokenize(source_code, collect_errors=True)

# Con tabla de depuración en consola
tokens = tokenize(source_code, debug=True)
```

---

## 4. Etapa 2 — Análisis Sintáctico (`parser.py`)

**Archivo:** [beatscript/parser.py](beatscript/parser.py)

El parser toma la lista de tokens del lexer y construye el **AST
(Árbol Sintáctico Abstracto)** verificando que la estructura gramatical
sea correcta.

### 4.1 Gramática EBNF de BeatScript

```ebnf
programa      ::= (sentencia)*

sentencia     ::= tempo
               |  volume
               |  instrument
               |  track
               |  chord
               |  repeat_stmt

tempo         ::= 'tempo' NUMBER
volume        ::= 'volume' NUMBER
instrument    ::= 'instrument' INSTR_NAME

track         ::= 'track' IDENTIFIER '{' (evento)* '}'

chord         ::= 'chord' '{' NOTE+ DURATION '}'

repeat_stmt   ::= 'repeat' NUMBER '{' (sentencia)* '}'

evento        ::= nota
               |  rest_evento
               |  chord
               |  repeat_evento

nota          ::= NOTE DURATION
rest_evento   ::= 'rest' DURATION
repeat_evento ::= 'repeat' NUMBER '{' (evento)* '}'
```

**Puntos clave:**

- `chord` puede aparecer tanto a nivel de `sentencia` (top-level) como
  dentro de `track` (como `evento`). Ambos usos son válidos.
- `repeat` también es dual: a nivel top se parsea con `_parse_repeat_statement`
  que llama recursivamente a `_parse_statement`; dentro de un track se llama
  `_parse_repeat_event` que llama recursivamente a `_parse_event`.
- La gramática es **LL(1)** — el parser siempre sabe qué regla aplicar
  mirando un solo token hacia adelante (`_current_token()`).

### 4.2 Tipo de parser: recursivo descendente

El parser es un **recursive descent parser** (análisis sintáctico
descendente recursivo). Cada regla gramatical no terminal corresponde a
un método privado del parser:

| Regla gramatical | Método del parser |
|-----------------|-------------------|
| `programa` | `parse()` |
| `sentencia` | `_parse_statement()` |
| `tempo` | `_parse_tempo()` |
| `volume` | `_parse_volume()` |
| `instrument` | `_parse_instrument()` |
| `track` | `_parse_track()` |
| `chord` | `_parse_chord()` |
| `repeat` (sentencia) | `_parse_repeat_statement()` |
| `evento` | `_parse_event()` |
| `nota` | `_parse_note()` |
| `rest` | `_parse_rest()` |
| `repeat` (evento) | `_parse_repeat_event()` |

### 4.3 Métodos de navegación del parser

```python
self.tokens   # lista de tokens
self.pos      # índice del token actual

_current_token()        # tokens[pos], sin avanzar
_peek_token(offset=1)   # tokens[pos + offset], sin avanzar
_advance()              # pos += 1
_is_at_end()            # pos >= len(tokens)
_check(tipo)            # current_token().type == tipo?
_consume(tipo, msg)     # verifica tipo, avanza y retorna el token;
                        # si no coincide, registra error y retorna None
```

**Código de navegación:** [parser.py:196-242](beatscript/parser.py#L196-L242)

### 4.4 Cálculo de columna en el parser

El parser reproduce el mismo algoritmo que el lexer para calcular columnas:

```python
def _get_column(self, token):
    if not self.source_code or not hasattr(token, "lexpos"):
        return "?"
    line_start = self.source_code.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

Por eso el constructor acepta `source_code=""` como segundo parámetro
y se llama desde la GUI como:

```python
parser = BeatScriptParser(tokens, source)
```

**Código:** [parser.py:183-191](beatscript/parser.py#L183-L191)

### 4.5 Manejo de errores sintácticos

Todos los errores incluyen `[LÍNEA X, COL Y]` usando `_get_column`.

**Método principal:**

```python
def _add_error_with_suggestions(self, token, base_message):
    col = self._get_column(token)
    error_line = f"[LÍNEA {token.lineno}, COL {col}] {base_message}"
    if token.type == "IDENTIFIER":
        suggestions = _get_suggestions_for_word(token.value, cutoff=0.6, max_suggestions=2)
        if suggestions:
            sugerencia = " | ".join(f"'{s}'" for s in suggestions)
            error_line += f"\n   💡 Sugerencia: ¿Quisiste decir {sugerencia}?"
    self.errors.append(error_line)
```

**Código:** [parser.py:248-267](beatscript/parser.py#L248-L267)

### 4.6 Sugerencias con `difflib`

La función `_get_suggestions_for_word` usa `difflib.get_close_matches`
para comparar el identificador erróneo contra todas las claves del
diccionario `RESERVED`:

```python
def _get_suggestions_for_word(word, keywords_dict=None, cutoff=0.6, max_suggestions=3):
    candidates = list(keywords_dict.keys())
    suggestions = difflib.get_close_matches(
        word.lower(), candidates, n=max_suggestions, cutoff=cutoff
    )
    return suggestions
```

Si el usuario escribe `tmpo` → `difflib` calcula que `tempo` tiene
similitud > 0.6 → el error dice `💡 Sugerencia: ¿Quisiste decir 'tempo'?`

**Algoritmo de `difflib`:** usa el algoritmo de Ratcliff/Obershelp que
mide el porcentaje de caracteres coincidentes entre dos cadenas.

**Código:** [parser.py:31-54](beatscript/parser.py#L31-L54)

---

## 5. Árbol Sintáctico Abstracto (AST)

**Archivo:** [beatscript/parser.py:61-157](beatscript/parser.py#L61-L157)

El AST es una jerarquía de objetos Python. Todos heredan de `ASTNode`.

### 5.1 Jerarquía de clases

```
ASTNode (clase base)
├── Program            → nodo raíz
│   └── statements: list[ASTNode]
├── Tempo              → tempo <bpm>
│   └── bpm: int
├── Volume             → volume <level>
│   └── level: int
├── Instrument         → instrument <name>
│   └── name: str
├── Track              → track <name> { eventos }
│   ├── name: str
│   └── events: list[Note | Rest | Chord | Repeat]
├── Note               → <pitch> <duration>
│   ├── pitch: str     ("C4", "D#3", "Eb5", ...)
│   └── duration: str  ("negra", "blanca", ...)
├── Rest               → rest <duration>
│   └── duration: str
├── Chord              → chord { NOTE+ DURATION }
│   ├── notes: list[str]   (["C4", "E4", "G4"])
│   └── duration: str
└── Repeat             → repeat <count> { eventos/sentencias }
    ├── count: int
    └── events: list[ASTNode]
```

### 5.2 Representación visual del AST (texto)

La función `ast_to_tree_string` convierte el AST en un árbol de
directorios usando caracteres Unicode:

```
📋 Program
├── ⏱️  Tempo: 120 BPM
├── 🔊 Volume: 80
├── 🎹 Instrument: violin
└── 📁 Track 'melodia'
    ├── 🎵 C4 (negra)
    ├── 🎵 D4 (negra)
    ├── 🎼 Chord (blanca)
    │   ├── 🎵 C4
    │   ├── 🎵 E4
    │   └── 🎵 G4
    └── 🔁 Repeat ×2
        ├── 🎵 G4 (negra)
        └── 🎵 A4 (negra)
```

Esta representación aparece en el panel inferior derecho de la GUI
(sección "Árbol Sintáctico — Parser (Etapa 2)").

**Código:** [parser.py:590-662](beatscript/parser.py#L590-L662)

### 5.3 Representación para Treeview (tabla)

`ast_to_table_rows` genera tuplas `(parent_id, node_id, valores, tag)`
listas para insertar en un `ttk.Treeview` de tkinter.

**Código:** [parser.py:533-583](beatscript/parser.py#L533-L583)

---

## 6. Árbol de Derivación Visual (`generate_visual_tree`)

**Archivo:** [beatscript/parser.py:669-891](beatscript/parser.py#L669-L891)

La función `generate_visual_tree(ast_root, output_filename="parse_tree")`
genera un PNG con el **árbol de derivación completo** usando Graphviz.

### 6.1 Diferencia entre AST y árbol de derivación

| | AST | Árbol de derivación |
|--|-----|---------------------|
| Qué muestra | Solo nodos semánticamente relevantes | Muestra explícitamente cada token terminal y cada regla gramatical |
| Nodos hoja | El dato (ej. `120`) | El token con su tipo (ej. `NUMBER '120'`) |
| Nodos internos | El tipo de sentencia (ej. `Tempo`) | El nombre de la regla gramatical (ej. `sentencia\ntempo`) |
| Uso | Generación de código, interpretación | Análisis académico, depuración |

### 6.2 Tipos de nodos en el grafo

```python
nodo_regla(etiqueta, color)      # rectángulo — regla gramatical
nodo_terminal(tipo, valor, color) # elipse     — token terminal
nodo_lista(etiqueta)              # rombo      — contenedor de listas
```

El nodo raíz `programa` usa forma `doubleoctagon`.

### 6.3 Esquema de colores

| Nodo | Forma | Color |
|------|-------|-------|
| `programa` (raíz) | doubleoctagon | `#0d47a1` (azul oscuro) |
| `sentencia tempo/volume/instrument` | box | `#4527a0` (morado) |
| `sentencia track` | box | `#1a237e` (azul marino) |
| `evento nota` | box | `#1b5e20` (verde oscuro) |
| `evento rest` | box | `#33691e` (verde oliva) |
| `evento chord` | box | `#004d40` (verde azulado) |
| `repeat` | box | `#bf360c` (naranja oscuro) |
| Terminal keyword | ellipse | `#6a1b9a` (violeta) |
| Terminal valor | ellipse | `#37474f` (gris azulado) |
| Terminal nota (NOTE) | ellipse | `#2e7d32` (verde) |
| Terminal duración | ellipse | `#388e3c` (verde claro) |
| Terminal llaves | ellipse | `#455a64` (gris) |
| Listas (eventos/cuerpo) | diamond | `#004d40` |

### 6.4 Patrón visitor

Los visitantes son funciones locales dentro de `generate_visual_tree`:

```python
def visitar(node):
    if isinstance(node, Program):    return _v_programa(node)
    if isinstance(node, Tempo):      return _v_tempo(node)
    if isinstance(node, Volume):     return _v_volume(node)
    if isinstance(node, Instrument): return _v_instrument(node)
    if isinstance(node, Track):      return _v_track(node)
    if isinstance(node, Note):       return _v_note(node)
    if isinstance(node, Rest):       return _v_rest(node)
    if isinstance(node, Chord):      return _v_chord(node)
    if isinstance(node, Repeat):     return _v_repeat(node)
```

Cada visitante (`_v_tempo`, `_v_track`, etc.) crea los nodos con
`nodo_regla` / `nodo_terminal`, conecta con `arco(padre, hijo)` y retorna
el ID del nodo raíz de esa subárbol.

### 6.5 Solución al problema de PATH en Windows

Python no siempre hereda el PATH del sistema cuando se lanza desde un IDE.
La función inyecta programáticamente la ruta de Graphviz al inicio:

```python
if _os.name == "nt":
    for _candidato in [
        r"C:\Program Files\Graphviz\bin",
        r"C:\Program Files (x86)\Graphviz\bin",
    ]:
        if _os.path.isfile(_os.path.join(_candidato, "dot.exe")):
            _os.environ["PATH"] = _candidato + _os.pathsep + _os.environ.get("PATH", "")
            break
```

### 6.6 Flujo de generación

```
AST (Program)
   │
   ▼
visitar(ast_root)          ← construye el Digraph con todos los nodos y aristas
   │
   ▼
dot.render(filename, format="png", cleanup=True)
   │                       ← dot.exe genera el PNG y elimina el .gv intermedio
   ▼
os.startfile(ruta_png)     ← abre el PNG con el visor predeterminado de Windows
```

El PNG se guarda en la carpeta raíz del proyecto (`BeatScript/parse_tree.png`).

---

## 7. Etapa 4 — Generación MIDI (`midi_gen.py`)

**Archivo:** [beatscript/midi_gen.py](beatscript/midi_gen.py)

Esta etapa toma **directamente los tokens** (no el AST) y genera un archivo
`.mid` usando la biblioteca `midiutil`.

### 7.1 Tablas de conversión

```python
NOTE_SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

DURATION_BEATS = {
    'redonda': 4.0, 'blanca': 2.0, 'negra': 1.0,
    'corchea': 0.5, 'semicorchea': 0.25,
    'fusa': 0.125, 'semifusa': 0.0625,
}

INSTRUMENT_PROGRAM = {
    'piano': 0, 'violin': 40, 'guitar': 25,
    # ... (32 instrumentos mapeados a programas MIDI General)
}
```

### 7.2 Conversión de nota a número MIDI

```python
def note_to_midi(note_str: str) -> int:
    # "C4" → pitch MIDI 60
    # Fórmula: semitono_de_la_letra + (octava + 1) * 12 + alteración
```

La fórmula estándar MIDI: C4 = 60, C5 = 72, C3 = 48, etc.

### 7.3 Procesamiento de tokens

`tokens_to_midi` recorre la lista de tokens con un índice `j` y un tiempo
acumulado `t` (en beats). Cada tipo de token produce una acción:

| Token | Acción |
|-------|--------|
| `VOLUME_KW` + `NUMBER` | Actualiza `velocity` (0-127) |
| `TEMPO_KW` + `NUMBER` | Actualiza `tempo` y llama `midi.addTempo` |
| `INSTRUMENT_KW` + `INSTR_NAME` | Llama `midi.addProgramChange` |
| `TRACK_KW` | Extrae el bloque `{...}` y lo procesa recursivamente |
| `REPEAT_KW` + `NUMBER` | Extrae el bloque y lo procesa `n` veces |
| `CHORD_KW` | Extrae el bloque, agrega todas las notas en el mismo tiempo `t` |
| `NOTE` + `DURATION` | `midi.addNote` y avanza `t` |
| `REST` + `DURATION` | Solo avanza `t` (silencio) |

La función `_collect_block` maneja llaves anidadas usando un contador
de profundidad `depth` para encontrar el `}` que cierra el bloque.

---

## 8. Interfaz gráfica (`main_gui.py`)

**Archivo:** [main_gui.py](main_gui.py)

Framework: **customtkinter (CTk)** — wrapper de tkinter con modo oscuro.

### 8.1 Estructura de la ventana

```
┌─────────────────────────────────────────────────────────────┐
│  BeatScript IDE  [▶ Compilar y Reproducir]  [⏹ Detener]     │  ← toolbar
├────────────────────────┬────────────────────────────────────┤
│                        │  Tabla de Tokens (Lexer Etapa 1)   │
│  Editor de código      │  # | TIPO | VALOR | LÍNEA | COL    │
│  (CTkTextbox)          │────────────────────────────────────│
│                        │  Árbol Sintáctico (Parser Etapa 2) │
│                        │  [🌳 Ver Árbol de Derivación]      │
│                        │  📋 Program                        │
│  Línea: X, Col: Y      │    ├── ⏱️ Tempo: 120 BPM           │
│  Líneas totales: Z     │    └── 📁 Track 'melodia'          │
├────────────────────────┴────────────────────────────────────┤
│  Consola                                                     │  ← output
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Componentes principales

| Widget | Clase | Descripción |
|--------|-------|-------------|
| `self.editor` | `CTkTextbox` | Editor de código fuente |
| `self.status_label` | `CTkLabel` | Barra de estado (línea/col) |
| `self.token_tree` | `ttk.Treeview` | Tabla de tokens del lexer |
| `self.ast_textbox` | `CTkTextbox` | Visualización del AST en texto |
| `self.consola` | `CTkTextbox` | Salida de mensajes del compilador |
| `self.current_ast` | `Program \| None` | AST del último compilado exitoso |

### 8.3 Barra de estado del editor

Se actualiza en tiempo real con cada pulsación de tecla o clic del ratón.
Usa el widget interno `self.editor._textbox` (el `tk.Text` subyacente) para
enlazar los eventos, ya que CTkTextbox no los expone directamente:

```python
inner = self.editor._textbox
inner.bind("<KeyRelease>", self._actualizar_estado)
inner.bind("<ButtonRelease>", self._actualizar_estado)
```

`tk.Text.index("insert")` retorna `"linea.columna"` donde columna es base 0.
El código suma 1 para convertirlo a base 1.

**Código:** [main_gui.py:289-308](main_gui.py#L289-L308)

### 8.4 Tabla de tokens (ttk.Treeview con tema oscuro)

`ttk.Treeview` no hereda el tema de CTk. Se aplica manualmente con
`ttk.Style`:

```python
style = ttk.Style()
style.theme_use("clam")
style.configure("Token.Treeview",
    background="#1e1e1e", foreground="#e0e0e0",
    fieldbackground="#1e1e1e", rowheight=22, ...)
```

Las filas alternas usan tags `"par"` / `"impar"` para el efecto zebra.

**Código:** [main_gui.py:158-220](main_gui.py#L158-L220)

### 8.5 Validación post-léxica

`_validar_tokens_extra` ([main_gui.py:465-533](main_gui.py#L465-L533)) detecta
patrones que el lexer acepta pero son semánticamente inválidos:

- `instrument` seguido de `IDENTIFIER` → instrumento no reconocido
- `tempo` no seguido de `NUMBER`
- `volume` con valor fuera de rango 0-127
- Nota o rest sin duración válida
- Identificadores con forma de nota inválida (`C4x`, `D##3`)

Esta validación ocurre **entre** el análisis léxico y el sintáctico.

---

## 9. Flujo completo de compilación

Secuencia en `_compilar()` ([main_gui.py:362-443](main_gui.py#L362-L443)):

```
1. Obtener código fuente del editor
   source = self.editor.get("1.0", "end-1c").strip()

2. ETAPA 1 — Análisis léxico
   tokens, errors = tokenize(source, collect_errors=True)
   → Si hay errores léxicos: mostrar y detener

3. Validación post-léxica
   avisos = _validar_tokens_extra(tokens, source)
   → Si hay avisos: mostrar y detener

4. Llenar tabla de tokens en la GUI
   _llenar_tabla_tokens(tokens, source)

5. ETAPA 2 — Análisis sintáctico
   parser = BeatScriptParser(tokens, source)
   ast = parser.parse()
   → Si hay errores sintácticos: mostrar y detener

6. Mostrar AST en texto
   self.current_ast = ast
   _mostrar_ast(ast)

7. ETAPA 4 — Generar y reproducir MIDI
   tokens_to_midi(tokens, midi_path)
   pygame.mixer.music.load(midi_path)
   pygame.mixer.music.play()
```

---

## 10. Tests del lexer

**Archivo:** [beatscript/tests/test_lexer.py](beatscript/tests/test_lexer.py)

Suite de tests manuales (sin pytest). Cubre:

| Test | Qué verifica |
|------|-------------|
| `test_keywords` | Todas las keywords retornan el tipo correcto |
| `test_tempo_declaration` | `tempo NUMBER` y que el valor es `int` |
| `test_instrument_declaration` | 6 instrumentos reconocidos |
| `test_notes_natural` | C0..B8 como `NOTE` |
| `test_notes_sharp` | C#4, D#3, F#5... |
| `test_notes_flat` | Eb5, Bb4, Ab3... |
| `test_notes_normalized` | `c4` → `"C4"`, `eb3` → `"EB3"` |
| `test_notes_no_octave` | `C` sin octava → `IDENTIFIER`, no `NOTE` |
| `test_durations` | Las 7 duraciones musicales |
| `test_note_with_duration` | Pares `NOTE DURATION` |
| `test_rest_with_duration` | `REST DURATION` |
| `test_numbers` | `NUMBER` con valor `int` |
| `test_identifiers` | Nombres libres + que `bass` es `INSTR_NAME` |
| `test_braces` | `LBRACE` y `RBRACE` |
| `test_track_block` | `track melody {` |
| `test_repeat_block` | `repeat N {` |
| `test_chord_block` | `chord {` y `NOTE NOTE NOTE DURATION` |
| `test_comments_ignored` | Comentarios no producen tokens |
| `test_multiline_program` | Programa completo de 20 tokens |
| `test_line_numbers` | `lineno` correcto por línea |
| `test_debug_mode` | `debug=True` no lanza excepciones |

Para ejecutar:
```
python -m beatscript.tests.test_lexer
```

---

## 11. Dependencias externas

| Paquete | Instalación | Uso |
|---------|-------------|-----|
| `ply` | `pip install ply` | Motor del lexer |
| `customtkinter` | `pip install customtkinter` | GUI con modo oscuro |
| `pygame` | `pip install pygame` | Reproducción de MIDI |
| `midiutil` | `pip install midiutil` | Escritura de archivos .mid |
| `graphviz` (Python) | `pip install graphviz` | Binding a `dot.exe` |
| Graphviz (binario) | [graphviz.org/download](https://graphviz.org/download/) | Renderiza el PNG del árbol |
| `difflib` | stdlib | Sugerencias de palabras reservadas |

> El binario de Graphviz (`dot.exe`) debe instalarse con la opción
> "Add to PATH for all users". Si la sesión de Python se inició antes
> de esa instalación, la función `generate_visual_tree` inyecta el path
> programáticamente en `os.environ["PATH"]`.

---

*Este documento fue generado a partir del código fuente real del proyecto.*
