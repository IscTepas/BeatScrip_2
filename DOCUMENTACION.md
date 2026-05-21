# BeatScript — Documentación Técnica del Compilador

**Materia:** Lenguajes y Autómatas I  
**Semestre:** 6to semestre  
**Proyecto:** Compilador de lenguaje de composición musical → MIDI

---

## Índice

1. [¿Qué es BeatScript?](#1-qué-es-beatscript)
2. [Arquitectura general del compilador](#2-arquitectura-general-del-compilador)
3. [Analizador Léxico (Lexer)](#3-analizador-léxico-lexer)
   - 3.1 ¿Qué hace un lexer?
   - 3.2 Tokens reconocidos
   - 3.3 Palabras reservadas (RESERVED)
   - 3.4 Autómatas finitos y expresiones regulares
   - 3.5 Prioridad de reglas en PLY
   - 3.6 Manejo de errores léxicos
4. [Generador MIDI](#4-generador-midi)
   - 4.1 Mapeos matemáticos
   - 4.2 Conversión nota → número MIDI
   - 4.3 Máquina de estados para procesar tokens
   - 4.4 Balanceo de llaves (bloques anidados)
5. [Interfaz Gráfica (IDE)](#5-interfaz-gráfica-ide)
   - 5.1 Estructura de la ventana
   - 5.2 Flujo de compilación
   - 5.3 Validación semántica adicional
6. [Suite de pruebas](#6-suite-de-pruebas)
7. [Ejemplo completo paso a paso](#7-ejemplo-completo-paso-a-paso)
8. [Dependencias y tecnologías](#8-dependencias-y-tecnologías)

---

## 1. ¿Qué es BeatScript?

BeatScript es un **lenguaje de dominio específico (DSL)** diseñado para describir composiciones musicales con texto plano y compilarlas a archivos MIDI reproducibles.

En lugar de usar un DAW (Digital Audio Workstation) con ratón, el usuario escribe instrucciones en texto:

```
tempo 120
instrument piano

track melodia {
    C4 negra
    E4 negra
    G4 blanca
}
```

Y el compilador convierte eso a un archivo `output.mid` que cualquier reproductor de música puede abrir.

**¿Por qué es un compilador?** Porque sigue exactamente las mismas etapas de un compilador clásico:

```
Código fuente (texto)
        ↓
  [Análisis Léxico]   → convierte texto en tokens
        ↓
  [Análisis Sintáctico] → verifica gramática (pendiente)
        ↓
  [Análisis Semántico]  → verifica significado (pendiente)
        ↓
  [Generación de código] → produce el archivo MIDI
```

Este proyecto implementa la **Etapa 1 (Léxico)** completa y la **Generación de código** directamente desde tokens.

---

## 2. Arquitectura general del compilador

```
d:/BeatScript/
├── main_gui.py              ← IDE visual (la ventana que ven el usuario)
└── beatscript/
    ├── lexer.py             ← Analizador léxico (el corazón del proyecto)
    ├── midi_gen.py          ← Generador de archivos MIDI
    └── tests/
        └── test_lexer.py    ← 74 pruebas automáticas del lexer
```

El flujo de datos es:

```
Usuario escribe código
        ↓
main_gui.py llama a lexer.tokenize()
        ↓
lexer.py devuelve lista de tokens
        ↓
main_gui.py valida los tokens semánticamente
        ↓
midi_gen.tokens_to_midi() procesa los tokens
        ↓
Se escribe output.mid
        ↓
pygame reproduce el archivo
```

---

## 3. Analizador Léxico (Lexer)

**Archivo:** `beatscript/lexer.py`

### 3.1 ¿Qué hace un lexer?

Un **analizador léxico** (lexer o scanner) es el primer paso de cualquier compilador. Su trabajo es tomar el código fuente como una cadena de caracteres y dividirlo en **tokens**.

Un **token** es la unidad mínima con significado en un lenguaje. Es equivalente a las palabras en español:

| Entrada (texto) | Token generado | Tipo |
|-----------------|----------------|------|
| `tempo` | `tempo` | `TEMPO_KW` |
| `120` | `120` | `NUMBER` |
| `C4` | `C4` | `NOTE` |
| `negra` | `negra` | `DURATION` |
| `{` | `{` | `LBRACE` |
| `# comentario` | (descartado) | — |

El lexer **no entiende la estructura** (eso es trabajo del parser). Solo reconoce piezas individuales.

### 3.2 Tokens reconocidos

BeatScript define **14 tipos de tokens**:

| Token | Descripción | Ejemplo |
|-------|-------------|---------|
| `TEMPO_KW` | Palabra clave para tempo | `tempo` |
| `INSTRUMENT_KW` | Palabra clave para instrumento | `instrument` |
| `TRACK_KW` | Palabra clave para pistas | `track` |
| `REPEAT_KW` | Palabra clave para repetición | `repeat` |
| `CHORD_KW` | Palabra clave para acordes | `chord` |
| `REST` | Silencio musical | `rest` |
| `VOLUME_KW` | Control de volumen | `volume` |
| `NOTE` | Nota musical con octava | `C4`, `D#3`, `Eb5` |
| `DURATION` | Duración de nota | `negra`, `blanca`, `corchea` |
| `INSTR_NAME` | Nombre de instrumento MIDI | `piano`, `violin`, `guitar` |
| `NUMBER` | Número entero positivo | `120`, `88`, `2` |
| `IDENTIFIER` | Nombre libre definido por usuario | `melodia`, `coro`, `mi_track` |
| `LBRACE` | Llave de apertura | `{` |
| `RBRACE` | Llave de cierre | `}` |

### 3.3 Palabras reservadas (RESERVED)

El lexer usa un diccionario Python llamado `RESERVED` que mapea cada palabra clave a su tipo de token:

```python
RESERVED: dict[str, str] = {
    "tempo"       : "TEMPO_KW",
    "instrument"  : "INSTRUMENT_KW",
    "track"       : "TRACK_KW",
    "repeat"      : "REPEAT_KW",
    "chord"       : "CHORD_KW",
    "rest"        : "REST",
    "volume"      : "VOLUME_KW",

    # Duraciones musicales
    "redonda"     : "DURATION",   # 4 tiempos
    "blanca"      : "DURATION",   # 2 tiempos
    "negra"       : "DURATION",   # 1 tiempo
    "corchea"     : "DURATION",   # 0.5 tiempos
    "semicorchea" : "DURATION",   # 0.25 tiempos
    "fusa"        : "DURATION",   # 0.125 tiempos
    "semifusa"    : "DURATION",   # 0.0625 tiempos

    # 30 nombres de instrumentos MIDI...
    "piano"  : "INSTR_NAME",
    "violin" : "INSTR_NAME",
    # ... etc
}
```

**¿Para qué sirve esto?** El lexer captura primero cualquier secuencia de letras como `IDENTIFIER`. Luego consulta `RESERVED` para ver si esa palabra tiene un significado especial. Si sí, cambia el tipo del token.

```
Texto: "tempo"
  → El regex de IDENTIFIER captura "tempo"
  → Se consulta RESERVED["tempo"] → "TEMPO_KW"
  → El token queda como tipo TEMPO_KW, no IDENTIFIER
```

Esto es más eficiente que tener un regex diferente para cada palabra clave.

### 3.4 Autómatas finitos y expresiones regulares

Esta es la parte central de la materia de **Lenguajes y Autómatas**. Cada regla del lexer es una **expresión regular** que describe el lenguaje que acepta un **autómata finito determinista (AFD)**.

Recordatorio: un AFD es una máquina con:
- Un conjunto de **estados** (q0, q1, q2...)
- Un **estado inicial** (q0)
- Uno o más **estados de aceptación** (marcados con *)
- **Transiciones** entre estados según el carácter leído

---

#### Token NOTE — Nota musical

**Expresión regular:** `[A-Ga-g][#b]?[0-9]`

En lenguaje natural: "una letra de A a G (mayúscula o minúscula), seguida opcionalmente por # o b, seguida por un dígito del 0 al 9".

**Autómata Finito Determinista:**

```
                [A-G, a-g]          [#, b]           [0-9]
    → q0 ────────────────→ q1 ──────────────→ q2 ──────────→ q3* (ACEPTACIÓN)
                                              
                                   [0-9] (ruta directa sin alteración)
                           q1 ──────────────────────────────→ q3*
```

- **q0**: Estado inicial. Espera una letra de nombre de nota (A-G).
- **q1**: Ya leyó la letra base. Puede venir `#`, `b`, o directamente un dígito.
- **q2**: Ya leyó la alteración (#/b). Ahora **debe** venir un dígito.
- **q3**: Estado de aceptación. La nota es válida.

**Ejemplos de cadenas y su recorrido:**

| Entrada | q0 | q1 | q2 | q3 | Resultado |
|---------|----|----|----|----|-----------|
| `C4` | C | — | — | 4 | ✓ ACEPTA |
| `D#3` | D | # | 3 | — | ✓ ACEPTA |
| `Eb5` | E | b | 5 | — | ✓ ACEPTA |
| `G` | G | — | — | — | ✗ RECHAZA (falta octava) |
| `bass` | b | — | — | — | ✗ RECHAZA (b seguida de 'a', no dígito) |

**Acción adicional:** Después de capturar, el lexer normaliza la nota a mayúsculas:

```python
def t_NOTE(t):
    r"[A-Ga-g][#b]?[0-9]"
    t.value = t.value.upper()   # c4 → C4,  eb3 → EB3
    return t
```

---

#### Token NUMBER — Número entero

**Expresión regular:** `[0-9]+`

"Uno o más dígitos del 0 al 9."

**Autómata Finito Determinista:**

```
           [0-9]          [0-9]
    → q0 ─────────→ q1* ──────→ q1*  (bucle)
```

- **q0**: Estado inicial.
- **q1***: Estado de aceptación. Cada dígito adicional regresa al mismo estado.

El `+` en la regex significa "uno o más", lo cual en el autómata se expresa como: "al menos una transición al estado de aceptación, con bucle opcional".

**Acción adicional:** Convierte el string a entero Python:

```python
def t_NUMBER(t):
    r"[0-9]+"
    t.value = int(t.value)   # "120" → 120
    return t
```

---

#### Token IDENTIFIER — Identificador de usuario

**Expresión regular:** `[a-zA-Z_][a-zA-Z0-9_]*`

"Una letra o guion bajo, seguido de cero o más letras, dígitos o guiones bajos."

**Autómata Finito Determinista:**

```
        [a-zA-Z_]        [a-zA-Z0-9_]
→ q0 ──────────────→ q1* ──────────────→ q1*  (bucle)
```

- **q0**: Estado inicial.
- **q1***: Estado de aceptación con bucle para seguir leyendo caracteres válidos.

**Este es el autómata más general** y captura también las palabras reservadas. Por eso se consulta `RESERVED` después:

```python
def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    token_type = RESERVED.get(t.value.lower(), "IDENTIFIER")
    t.type  = token_type
    t.value = t.value.lower() if token_type != "IDENTIFIER" else t.value
    return t
```

**Ejemplos:**

| Lexema capturado | `RESERVED.get(...)` | Tipo final |
|-----------------|---------------------|------------|
| `melodia` | `None` → default `"IDENTIFIER"` | IDENTIFIER |
| `tempo` | `"TEMPO_KW"` | TEMPO_KW |
| `negra` | `"DURATION"` | DURATION |
| `piano` | `"INSTR_NAME"` | INSTR_NAME |

---

#### Token COMMENT — Comentario

**Expresión regular:** `\#[^\n]*`

"Un `#` seguido de cualquier carácter que no sea salto de línea, cero o más veces."

**Autómata Finito Determinista:**

```
         [#]          [^\n]
→ q0 ─────────→ q1* ──────────→ q1*  (bucle hasta newline)
```

**Acción:** `pass` — el token es descartado. Los comentarios nunca llegan al generador MIDI.

```python
def t_COMMENT(t):
    r"\#[^\n]*"
    pass  # descartado
```

---

#### Token LBRACE / RBRACE — Llaves

**Expresiones regulares:**

```python
t_LBRACE = r"\{"
t_RBRACE = r"\}"
```

Son **autómatas triviales de un solo estado**: el carácter `{` o `}` se lee y se acepta inmediatamente.

```
→ q0 ─── { ───→ q1*   (LBRACE)
→ q0 ─── } ───→ q1*   (RBRACE)
```

---

#### Salto de línea — Tracking de números de línea

**Expresión regular:** `\n+`

No genera token, pero actualiza el contador de líneas del lexer:

```python
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
```

Esto es crucial para los mensajes de error: "Error en Línea 5, Columna 3".

---

#### Caracteres ignorados

```python
t_ignore = " \t\r"
```

Espacios, tabulaciones y retornos de carro se descartan sin generar tokens. No hace falta un autómata para esto — PLY lo maneja directamente.

---

### 3.5 Prioridad de reglas en PLY

PLY (Python Lex-Yacc) es la librería que implementa el lexer. Tiene reglas específicas de prioridad que son **críticas** para que el lexer funcione correctamente:

**Regla 1 — Funciones:** se ordenan por posición en el archivo (más arriba = mayor prioridad).

**Regla 2 — Strings:** se ordenan por longitud del regex (más larga = mayor prioridad).

**El orden crítico en BeatScript:**

```
1. t_NOTE       (función, línea 139) — ALTA PRIORIDAD
2. t_NUMBER     (función, línea 150)
3. t_IDENTIFIER (función, línea 164) — BAJA PRIORIDAD
```

**¿Por qué esto importa?** El string `"bass"` contiene `b` que es un bemol musical, y `b` podría confundirse con el inicio de una nota. Pero `bass` empieza con `b` seguida de `a` (no un dígito), así que el regex de NOTE `[A-Ga-g][#b]?[0-9]` **no lo acepta**, y cae en IDENTIFIER, que sí lo captura. Luego RESERVED lo convierte a `INSTR_NAME`.

Otro ejemplo crítico: `C4` — si IDENTIFIER tuviera mayor prioridad que NOTE, `C4` sería capturado como IDENTIFIER (ya que `[a-zA-Z][a-zA-Z0-9]*` lo acepta). Por eso NOTE **debe ir primero**.

---

### 3.6 Manejo de errores léxicos

Cuando el lexer encuentra un carácter que no encaja en ninguna regla, llama a `t_error`. BeatScript tiene un diccionario `_ERROR_HINTS` con mensajes contextuales para cada símbolo inválido:

```python
_ERROR_HINTS: dict[str, str] = {
    "@":  "El símbolo '@' no pertenece al alfabeto de BeatScript.",
    "*":  "Para repetir bloques usa: repeat N { ... }",
    "(":  "Paréntesis no válido — los bloques se delimitan con { }",
    ";":  "El ';' no es necesario — cada instrucción va en su propia línea.",
    ",":  "Separa notas con espacios, no con comas: C4 E4 G4 blanca",
    ".":  "El '.' no es válido — BeatScript no usa decimales.",
    "/":  "Para comentarios usa '#', no '/' ni '//'.",
    # ... más caracteres
}
```

**¿Cómo se calcula la columna del error?**

```python
def _find_column(source: str, token) -> int:
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

`token.lexpos` es la posición absoluta del token en toda la cadena fuente. Se busca hacia atrás el último `\n` antes de esa posición para saber dónde empieza la línea actual. La diferencia da la columna.

En modo `collect_errors=True`, los errores se acumulan en una lista en lugar de imprimirse, para que la GUI pueda mostrarlos todos juntos.

---

## 4. Generador MIDI

**Archivo:** `beatscript/midi_gen.py`

### 4.1 Mapeos matemáticos

El estándar MIDI representa cada nota como un número del **0 al 127**. El centro de referencia es **C4 (Do central) = 60**.

El generador usa tres diccionarios de mapeo:

**Semitonos por nota (dentro de una octava):**

```python
NOTE_SEMITONES = {
    'C': 0,   # Do
    'D': 2,   # Re  (2 semitonos sobre C)
    'E': 4,   # Mi  (4 semitonos sobre C)
    'F': 5,   # Fa
    'G': 7,   # Sol
    'A': 9,   # La
    'B': 11,  # Si
}
```

Nótese que D=2 (no 1) y E=4 (no 3) porque entre Do-Re y Re-Mi existe un semitono que no tiene nombre en el sistema de notas naturales. Eso explica por qué no hay tecla negra entre E y F en un piano.

**Duraciones en tiempos de negra:**

```python
DURATION_BEATS = {
    'redonda':     4.0,    # cuatro negras
    'blanca':      2.0,    # dos negras
    'negra':       1.0,    # una negra (unidad base)
    'corchea':     0.5,    # mitad de negra
    'semicorchea': 0.25,
    'fusa':        0.125,
    'semifusa':    0.0625, # dieciseisavo de negra
}
```

**Programas MIDI por instrumento (0-127):**

```python
INSTRUMENT_PROGRAM = {
    'piano':      0,    # Grand Piano
    'violin':    40,    # Violin
    'flute':     73,    # Flute
    'trumpet':   56,    # Trumpet
    # ... 30 instrumentos en total
}
```

Estos números son parte del **estándar General MIDI** (GM). Todo reproductor MIDI que soporte GM interpretará el programa 40 como violín.

### 4.2 Conversión nota → número MIDI

**Función:** `note_to_midi(note_str: str) -> int`

La fórmula matemática es:

```
MIDI = semitonos_de_la_nota + (octava + 1) × 12
     + ajuste_por_alteración
```

**Implementación:**

```python
def note_to_midi(note_str: str) -> int:
    s      = note_str.upper()
    letter = s[0]                          # 'C', 'D', etc.
    rest   = s[1:]
    if rest and rest[0] in ('#', 'B') and len(rest) > 1:
        alt, octave = rest[0], int(rest[1])  # con alteración: D#3
    else:
        alt, octave = '', int(rest[0])       # sin alteración: C4
    
    pitch = NOTE_SEMITONES[letter] + (octave + 1) * 12
    if alt == '#': pitch += 1   # sostenido: sube un semitono
    if alt == 'B': pitch -= 1   # bemol: baja un semitono
    return pitch
```

**Ejemplos:**

| Nota | Cálculo | MIDI |
|------|---------|------|
| `C4` | 0 + (4+1)×12 = 60 | 60 |
| `D#3` | 2 + (3+1)×12 + 1 = 51 | 51 |
| `EB5` | 4 + (5+1)×12 − 1 = 75 | 75 |
| `G0` | 7 + (0+1)×12 = 19 | 19 |

### 4.3 Máquina de estados para procesar tokens

**Función:** `tokens_to_midi(tokens, output_path)`

El generador implementa una **máquina de estados** que recorre la lista de tokens en orden, manteniendo un estado global del contexto actual (tempo, instrumento, volumen, tiempo actual).

```
Estado global:
  tempo    = 120 BPM
  program  = 0 (piano)
  velocity = 80 (volumen)
  t        = 0.0 (tiempo actual en el MIDI)
```

La función interna `process(tok_list, t)` es **recursiva**: cuando encuentra un bloque `track {}`, `repeat {}` o `chord {}`, extrae los tokens de dentro y se llama a sí misma con esos tokens.

**Diagrama de la máquina de estados:**

```
         ┌──────────────────────────────────────────────────┐
         ↓                                                  │
    Lee token                                               │
         │                                                  │
    ┌────┴────┐                                             │
    │  tipo?  │                                             │
    └────┬────┘                                             │
         │                                                  │
    VOLUME_KW ──→ lee NUMBER siguiente → actualiza velocity │
         │                                                  │
    TEMPO_KW  ──→ lee NUMBER siguiente → actualiza tempo    │
                   → addTempo() en el MIDI                  │
         │                                                  │
    INSTRUMENT_KW → lee INSTR_NAME → actualiza program      │
                   → addProgramChange() en el MIDI          │
         │                                                  │
    TRACK_KW  ──→ busca LBRACE → extrae bloque              │
                   → process(bloque, t) recursivamente      │
         │                                                  │
    REPEAT_KW ──→ lee N → extrae bloque                     │
                   → process(bloque, t) × N veces           │
         │                                                  │
    CHORD_KW  ──→ extrae bloque → busca todas las NOTEs     │
                   → busca última DURATION                  │
                   → addNote() por cada nota simultánea     │
                   → t += duración                          │
         │                                                  │
    NOTE ───────→ lee DURATION opcional                     │
                   → addNote() en el MIDI                   │
                   → t += duración                          │
         │                                                  │
    REST ───────→ lee DURATION opcional                     │
                   → solo avanza t (no agrega nota)         │
         │                                                  │
         └──────────────────────────────────────────────────┘
```

### 4.4 Balanceo de llaves (bloques anidados)

**Función:** `_collect_block(tokens, start)`

Para extraer el contenido de un bloque `{...}` que puede tener bloques anidados, se usa un **contador de profundidad**:

```python
def _collect_block(tokens: list, start: int):
    depth, end = 1, start
    while end < len(tokens) and depth > 0:
        if   tokens[end].type == 'LBRACE': depth += 1
        elif tokens[end].type == 'RBRACE': depth -= 1
        end += 1
    return tokens[start:end - 1], end
```

**Ejemplo con bloques anidados:**

```
repeat 2 {           ← depth=1 al entrar
    track a {        ← depth=2
        C4 negra
    }                ← depth=1
    chord {          ← depth=2
        E4 G4 blanca
    }                ← depth=1
}                    ← depth=0 → fin del bloque
```

El algoritmo incrementa `depth` en cada `{` y lo decrementa en cada `}`. Cuando llega a 0, encontró el `}` que cierra el bloque original.

---

## 5. Interfaz Gráfica (IDE)

**Archivo:** `main_gui.py`

### 5.1 Estructura de la ventana

La GUI usa **customtkinter** (una versión mejorada de tkinter con tema oscuro) y **tkinter.ttk** para tablas.

```
┌─────────────────────────────────────────────────────────────────┐
│  BeatScript IDE  [▶ Compilar]  [⏹ Detener]  [Ver Detalles]   │  ← Toolbar
├──────────────────────────────────────┬──────────────────────────┤
│                                      │                          │
│        Editor de código              │   Árbol Sintáctico       │
│        (CTkTextbox)                  │   (placeholder Etapa 2)  │
│        Consolas 13pt                 │                          │
│        sin wrap                      │                          │
│                                      │                          │
├──────────────────────────────────────┴──────────────────────────┤
│  Consola  (output de compilación, errores, estado)             │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Flujo de compilación

Cuando el usuario presiona **▶ Compilar y Reproducir**, se ejecuta `_compilar()`:

```python
def _compilar(self):
    # 1. Limpiar consola
    self._log("", clear=True)

    # 2. Obtener código del editor
    source = self.editor.get("1.0", "end-1c").strip()

    # 3. Ejecutar el lexer
    tokens, errors = tokenize(source, collect_errors=True)

    # 4. Si hay errores léxicos → mostrar y parar
    if errors:
        for err in errors:
            self._log(f"✗  {err['msg']}")
        return

    # 5. Validación semántica adicional
    avisos = self._validar_tokens_extra(tokens, source)
    if avisos:
        for av in avisos:
            self._log(f"✗  {av}")
        return

    # 6. Éxito léxico
    self._log(f"✔  {len(tokens)} tokens encontrados.")

    # 7. Generar MIDI y reproducir
    tokens_to_midi(tokens, "output.mid")
    pygame.mixer.music.load("output.mid")
    pygame.mixer.music.play()
```

### 5.3 Validación semántica adicional

El lexer solo verifica que los caracteres formen tokens válidos. Hay errores que el lexer acepta pero que no tienen sentido musical. La GUI los detecta con `_validar_tokens_extra()`:

**Regla 1 — Instrumento desconocido:**
```
instrument xyz  →  ERROR: 'xyz' no es un instrumento reconocido
```
*Cómo se detecta:* Si después de `INSTRUMENT_KW` viene un `IDENTIFIER` (no un `INSTR_NAME`), el instrumento no existe en los mapeos MIDI.

**Regla 2 — Tempo sin número:**
```
tempo allegro  →  ERROR: se esperaba un número después de 'tempo'
```
*Cómo se detecta:* Si después de `TEMPO_KW` no viene un `NUMBER`.

**Regla 3 — Volumen fuera de rango:**
```
volume 200  →  ERROR: volumen 200 fuera de rango (0-127)
```
*Cómo se detecta:* `NUMBER` después de `VOLUME_KW` que no cae en [0, 127].

**Regla 4 — Duración inválida:**
```
C4 rapidito  →  ERROR: 'rapidito' no es una duración válida
```
*Cómo se detecta:* Si después de `NOTE` o `REST` viene un `IDENTIFIER` (no un `DURATION`).

**Regla 5 — Nota mal formada:**
```
C4x  →  AVISO: 'C4x' parece una nota inválida
```
*Cómo se detecta:* Con la expresión regular `^[A-Ga-g].+\d$` sobre el valor de un `IDENTIFIER`. Si un identificador empieza con letra de nota y termina con dígito, probablemente era una nota mal escrita.

---

## 6. Suite de pruebas

**Archivo:** `beatscript/tests/test_lexer.py`

El proyecto incluye **74 pruebas automáticas** usando `pytest`. Cubren:

| Grupo de pruebas | Cantidad | Qué verifica |
|-----------------|----------|--------------|
| Keywords | 6 | Que `tempo`, `instrument`, etc. generen el tipo correcto |
| Declaraciones de tempo | 3 | `tempo 120` → `TEMPO_KW`, `NUMBER(120)` |
| Declaraciones de instrumento | 6 | `instrument piano` → `INSTRUMENT_KW`, `INSTR_NAME` |
| Notas naturales | 8 | `C4`, `D4`, `E4`... hasta extremos `G0`, `A9` |
| Notas con sostenido | 5 | `C#4`, `D#3`, `F#5`... |
| Notas con bemol | 5 | `EB5`, `BB4`, `AB3`... |
| Normalización de notas | 1 | `c4 d#3 eb5` → `C4 D#3 EB5` |
| Notas sin octava | 2 | `C` (sin número) → se trata como `IDENTIFIER` |
| Duraciones | 7 | Todas las duraciones musicales |
| Nota con duración | 4 | `C4 negra`, `E4 blanca`, etc. |
| Silencio con duración | 2 | `rest corchea`, `rest blanca` |
| Números | 3 | `120`, `2`, `0` — verifica tipo Python `int` |
| Identificadores | 4 | `melody`, `coro`, `my_track`, `Track1` |
| Llaves | 3 | `{`, `}`, `{}` |
| Bloque track | 1 | `track melody {` |
| Bloque repeat | 2 | `repeat 2 {`, `repeat 4 {` |
| Bloque chord | 2 | `chord { C4 E4 G4 blanca }` |
| Comentarios ignorados | 3 | `# esto no genera token` |
| Programa completo | 1 | Código BeatScript de múltiples líneas |
| Números de línea | 1 | Verifica que `tok.lineno` se actualiza correctamente |

**Para correr las pruebas:**

```bash
pytest beatscript/tests/test_lexer.py -v
```

---

## 7. Ejemplo completo paso a paso

Tomemos este código BeatScript:

```
tempo 120
instrument piano

track melodia {
    C4 negra
    E4 negra
    G4 blanca
}
```

### Paso 1: El lexer tokeniza el texto

El lexer lee carácter por carácter y produce la siguiente lista de tokens:

| # | Tipo | Valor | Línea | Col |
|---|------|-------|-------|-----|
| 1 | TEMPO_KW | `tempo` | 1 | 1 |
| 2 | NUMBER | `120` | 1 | 7 |
| 3 | INSTRUMENT_KW | `instrument` | 2 | 1 |
| 4 | INSTR_NAME | `piano` | 2 | 12 |
| 5 | TRACK_KW | `track` | 4 | 1 |
| 6 | IDENTIFIER | `melodia` | 4 | 7 |
| 7 | LBRACE | `{` | 4 | 16 |
| 8 | NOTE | `C4` | 5 | 5 |
| 9 | DURATION | `negra` | 5 | 8 |
| 10 | NOTE | `E4` | 6 | 5 |
| 11 | DURATION | `negra` | 6 | 8 |
| 12 | NOTE | `G4` | 7 | 5 |
| 13 | DURATION | `blanca` | 7 | 8 |
| 14 | RBRACE | `}` | 8 | 1 |

**Nota:** Los saltos de línea y espacios son descartados. Los comentarios tampoco aparecen.

### Paso 2: Validación semántica

La GUI revisa los pares `TEMPO_KW → NUMBER`, `INSTRUMENT_KW → INSTR_NAME`, `NOTE → DURATION`. Todo está bien, no hay avisos.

### Paso 3: Generación MIDI

`tokens_to_midi` procesa los tokens:

1. `TEMPO_KW + NUMBER(120)` → `midi.addTempo(track, 0, 120)`
2. `INSTRUMENT_KW + INSTR_NAME(piano)` → `midi.addProgramChange(track, channel, 0, 0)`
3. `TRACK_KW + IDENTIFIER(melodia) + LBRACE` → extrae bloque interno
4. Dentro del bloque:
   - `NOTE(C4) + DURATION(negra)`:
     - `note_to_midi("C4")` = 0 + (4+1)×12 = **60**
     - `DURATION_BEATS["negra"]` = **1.0**
     - `midi.addNote(track, channel, 60, t=0.0, dur=1.0, vel=80)`
     - `t = 1.0`
   - `NOTE(E4) + DURATION(negra)`:
     - `note_to_midi("E4")` = 4 + (4+1)×12 = **64**
     - `midi.addNote(track, channel, 64, t=1.0, dur=1.0, vel=80)`
     - `t = 2.0`
   - `NOTE(G4) + DURATION(blanca)`:
     - `note_to_midi("G4")` = 7 + (4+1)×12 = **67**
     - `DURATION_BEATS["blanca"]` = **2.0**
     - `midi.addNote(track, channel, 67, t=2.0, dur=2.0, vel=80)`
     - `t = 4.0`

### Paso 4: Escritura del archivo

```python
with open("output.mid", "wb") as f:
    midi.writeFile(f)
```

`MIDIFile` (de la librería `midiutil`) serializa todo en el formato binario estándar MIDI.

### Paso 5: Reproducción

```python
pygame.mixer.music.load("output.mid")
pygame.mixer.music.play()
```

pygame usa el sintetizador del sistema para reproducir el archivo MIDI en tiempo real.

---

## 8. Dependencias y tecnologías

| Librería | Versión mínima | Para qué se usa |
|----------|---------------|-----------------|
| `ply` | ≥ 3.11 | Framework para construir lexers y parsers. Implementa la maquinaria de autómatas detrás de las reglas léxicas. |
| `midiutil` | ≥ 1.2.1 | Serialización de eventos musicales al formato binario MIDI estándar. |
| `customtkinter` | ≥ 5.2.0 | Widget toolkit para la interfaz gráfica con tema oscuro moderno. |
| `pygame-ce` | ≥ 2.5.0 | Módulo `mixer` para reproducir archivos MIDI usando el sintetizador del sistema operativo. |

**PLY (Python Lex-Yacc)** es especialmente relevante para esta materia. PLY implementa internamente un **análisis léxico basado en autómatas finitos**: convierte todas las expresiones regulares en un único autómata gigante (autómata de Thompson / NFA → DFA) que puede reconocer cualquier token en tiempo lineal respecto al tamaño del input.

---

*Documentación generada para el proyecto BeatScript — Lenguajes y Autómatas I, 6to semestre.*
