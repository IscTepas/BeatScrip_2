# GUÍA COMPLETA DE ESTUDIO — BEATSCRIPT
## Todo lo que necesitas saber para tu defensa oral

> **BeatScript** es un compilador de lenguaje musical que transforma código fuente
> escrito por el usuario en música real (archivo `.mid`).  
> Tiene 3 fases de compilación: **Léxico → Validación → Sintáctico**, y luego genera MIDI.

---

## ÍNDICE

1. [¿Qué es BeatScript y qué hace?](#1-qué-es-beatscript-y-qué-hace)
2. [Pipeline completo: qué pasa cuando presionas Compilar](#2-pipeline-completo)
3. [Estructura de archivos](#3-estructura-de-archivos)
4. [ETAPA 1 — Análisis Léxico (lexer.py)](#4-etapa-1--análisis-léxico)
   - Qué es un token
   - La biblioteca PLY
   - Expresiones regulares y autómatas
   - Todos los tokens definidos
   - Palabras reservadas (RESERVED)
   - Manejo de errores léxicos
   - Función tokenize
5. [FILTRO DE VALIDACIÓN — _validar_tokens_extra](#5-filtro-de-validación)
6. [ETAPA 2 — Análisis Sintáctico (parser.py)](#6-etapa-2--análisis-sintáctico)
   - Gramática EBNF completa
   - Qué es un parser recursivo descendente
   - Todos los métodos del parser
   - Construcción del AST
   - Manejo de errores con línea y columna
   - Sugerencias con difflib
   - Recuperación de errores: Modo Pánico
7. [El AST — Árbol Sintáctico Abstracto](#7-el-ast--árbol-sintáctico-abstracto)
   - Todas las clases de nodos
   - Representación visual en texto
   - Representación para tabla (Treeview)
8. [Árbol de Derivación Visual (Graphviz)](#8-árbol-de-derivación-visual)
9. [ETAPA 3 — Generación MIDI (midi_gen.py)](#9-etapa-3--generación-midi)
10. [Interfaz Gráfica (main_gui.py)](#10-interfaz-gráfica)
11. [Resaltado de Sintaxis en Tiempo Real](#11-resaltado-de-sintaxis-en-tiempo-real)
12. [Catálogo de Errores](#12-catálogo-de-errores)
13. [Tests del proyecto](#13-tests-del-proyecto)
14. [Resumen contra la Rúbrica de Evaluación](#14-resumen-contra-la-rúbrica)
15. [Preguntas trampa y respuestas blindadas](#15-preguntas-trampa-y-respuestas-blindadas)

---

## 1. ¿Qué es BeatScript y qué hace?

BeatScript es un **lenguaje de dominio específico (DSL)** diseñado para componer música.
Un DSL es un lenguaje de programación creado para un dominio muy concreto — en este caso,
la composición musical.

El usuario escribe código como este:

```
# Mi primera canción
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

Y el compilador lo convierte en un archivo `.mid` (MIDI) que se reproduce como música real.

### ¿Por qué es un compilador?

Porque tiene todas las etapas clásicas:
1. **Análisis Léxico** → divide el texto en unidades mínimas (tokens)
2. **Análisis Sintáctico** → verifica que la estructura gramatical sea correcta y construye un árbol
3. **Generación de código** → produce el archivo MIDI a partir de los tokens

---

## 2. Pipeline Completo

Cuando el usuario presiona **"Compilar y Reproducir"**, el método `_compilar()` en
`main_gui.py` ejecuta este flujo en orden estricto:

```
[CÓDIGO FUENTE del editor]
           │
           ▼
┌──────────────────────────────────────────────┐
│  ETAPA 1 — ANÁLISIS LÉXICO                   │
│  tokenize(source, collect_errors=True)        │
│  Archivo: beatscript/lexer.py                 │
│  Resultado: Lista de LexTokens + errores      │
└──────────────────────────────────────────────┘
           │
           │  ¿Hay errores léxicos?
           │  SÍ → mostrar [ERROR LÉXICO] y DETENER
           │  NO → continuar
           ▼
┌──────────────────────────────────────────────┐
│  FILTRO DE VALIDACIÓN (Cortafuegos)          │
│  _validar_tokens_extra(tokens, source)        │
│  Archivo: main_gui.py                         │
│  Resultado: Lista de avisos semánticos        │
└──────────────────────────────────────────────┘
           │
           │  ¿Hay avisos?
           │  SÍ → mostrar [AVISO] y DETENER
           │  NO → continuar
           ▼
┌──────────────────────────────────────────────┐
│  ETAPA 2 — ANÁLISIS SINTÁCTICO               │
│  BeatScriptParser(tokens, source).parse()    │
│  Archivo: beatscript/parser.py               │
│  Resultado: AST (árbol de objetos Python)    │
└──────────────────────────────────────────────┘
           │
           │  ¿Hay errores sintácticos?
           │  SÍ → mostrar [ERROR SINTÁCTICO] y DETENER
           │  NO → continuar
           ▼
┌──────────────────────────────────────────────┐
│  GENERACIÓN MIDI                             │
│  tokens_to_midi(tokens, output_path)         │
│  Archivo: beatscript/midi_gen.py             │
│  Resultado: archivo output.mid               │
└──────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  REPRODUCCIÓN                                │
│  pygame.mixer.music.load(midi_path)          │
│  pygame.mixer.music.play()                   │
└──────────────────────────────────────────────┘
```

**PUNTO CLAVE:** El pipeline es **secuencial con corte temprano**. Si la Etapa 1 falla,
las etapas siguientes NUNCA se ejecutan. Esto es correcto: no tiene sentido parsear
tokens que ya se sabe que son inválidos.

---

## 3. Estructura de Archivos

```
BeatScript/
├── main_gui.py                  ← IDE completo: interfaz, botones, pipeline
├── beatscript/
│   ├── __init__.py
│   ├── lexer.py                 ← ETAPA 1: Analizador léxico con PLY
│   ├── parser.py                ← ETAPA 2: Parser + AST + Graphviz
│   ├── midi_gen.py              ← ETAPA 3: Generador de archivos .mid
│   └── tests/
│       ├── __init__.py
│       └── test_lexer.py        ← 20 tests del lexer
├── test_suggestions.py          ← Tests de sugerencias del parser
├── test_tree_visual.py          ← Test del árbol Graphviz
├── requirements.txt             ← Dependencias del proyecto
├── DOCUMENTACION.md             ← Documentación técnica
└── output.mid                   ← Último archivo MIDI generado
```

---

## 4. ETAPA 1 — Análisis Léxico

**Archivo:** `beatscript/lexer.py`

### ¿Qué es el análisis léxico?

El análisis léxico es la **primera fase** del compilador. Su función es leer el código
fuente carácter por carácter y agrupar esos caracteres en unidades con significado
llamadas **tokens** (lexemas).

Por ejemplo, el código fuente `tempo 120` se convierte en:
- Token 1: tipo=`TEMPO_KW`, valor=`"tempo"`, línea=1
- Token 2: tipo=`NUMBER`, valor=`120`, línea=1

### ¿Qué es un token?

Un token es la unidad mínima con significado en un lenguaje. Tiene:
- **type**: el tipo o categoría (`NOTE`, `DURATION`, `TEMPO_KW`, etc.)
- **value**: el valor concreto (`"C4"`, `"negra"`, `"tempo"`)
- **lineno**: número de línea donde aparece
- **lexpos**: posición absoluta (en bytes) desde el inicio del archivo

### La biblioteca PLY

BeatScript usa **PLY (Python Lex-Yacc)**, que es una implementación en Python de las
herramientas clásicas de compiladores `lex` y `yacc`.

PLY construye internamente un **Autómata Finito Determinista (AFD)** a partir de las
reglas que le defines. Este AFD procesa el texto en tiempo **O(n)** — lineal en el
tamaño del código fuente — sin retrocesos (backtracking).

#### Cómo PLY determina prioridades entre reglas

PLY aplica las reglas en este orden:

| Prioridad | Tipo de regla | Criterio de desempate |
|---|---|---|
| 1 (MAYOR) | Funciones `def t_X(t):` | Orden de aparición en el archivo (arriba = mayor prioridad) |
| 2 | Cadenas `t_X = r"..."` | Longitud del regex (más largo = mayor prioridad) |

**Por eso `t_NOTE` se define ANTES que `t_IDENTIFIER` en el archivo.** Si estuviera
después, PLY intentaría `t_IDENTIFIER` primero y `C4` se convertiría en
`IDENTIFIER("C4")` en lugar de `NOTE("C4")`.

---

### Expresiones Regulares y Autómatas en BeatScript

#### TOKEN: `NOTE` — Nota musical

```
Regex:   [A-Ga-g][#b]?[0-9]
```

Esta regex significa:
- `[A-Ga-g]` → una letra entre A y G (mayúscula o minúscula) — la nota musical
- `[#b]?` → opcionalmente, un sostenido `#` o un bemol `b`
- `[0-9]` → exactamente un dígito — la octava (0 a 9)

**Autómata Finito Determinista (AFD) correspondiente:**

```
              [A-Ga-g]           [#b]              [0-9]
  INICIO ─────────────► q1 ──────────────► q2 ──────────────► ACEPTA
                         │                                        ▲
                         └──────────────── [0-9] ─────────────────┘
```

- **q1**: leímos la letra de la nota (estado intermedio)
- **q2**: leímos la alteración (estado intermedio, opcional)
- **ACEPTA**: leímos el dígito de octava — token válido

**Ejemplos válidos:** `C4`, `D#3`, `Eb5`, `G0`, `Bb4`, `F#7`, `A9`

**Ejemplos INVÁLIDOS:** `C` (sin octava), `D#` (sin octava), `H4` (H no es nota), `bass` (palabra)

**Normalización:** el lexer convierte a mayúsculas: `c4` → `C4`, `eb5` → `EB5`

**Código en lexer.py:**
```python
def t_NOTE(t):
    r"[A-Ga-g][#b]?[0-9]"
    t.value = t.value.upper()   # normalizar: c4 → C4
    return t
```

---

#### POR QUÉ `E44` SE DIVIDE EN `NOTE + NUMBER`

Este es un caso importante. El regex de `t_NOTE` solo consume **un dígito** de octava.
Al ver `E44`:

1. `t_NOTE` captura `E4` (la E más el primer 4) → `NOTE("E4")`
2. Queda `4` en el buffer de lectura → `t_NUMBER` lo captura → `NUMBER(4)`
3. Resultado: **dos tokens válidos** individualmente

**¿Por qué es un error entonces?** Porque `NOTE` seguido de `NUMBER` no es una
secuencia válida en la gramática de BeatScript. Una nota debe ir seguida de una
DURACIÓN (`negra`, `blanca`, etc.), no de un número.

El **filtro de validación** (`_validar_tokens_extra`) detecta exactamente este patrón:
`NOTE` seguido de `NUMBER` → genera `[AVISO]`.

---

#### TOKEN: `NUMBER` — Número entero

```
Regex:   [0-9]+
```

Significa: uno o más dígitos del 0 al 9.

**Autómata:**
```
              [0-9]             [0-9]
  INICIO ─────────────► q1* ─────────────► q1*   (bucle, * = ACEPTA)
```

El `+` indica que el estado final también puede repetirse (bucle). El valor se
convierte a `int` dentro de la función:

```python
def t_NUMBER(t):
    r"[0-9]+"
    t.value = int(t.value)   # "120" → 120 (entero)
    return t
```

---

#### TOKEN: `IDENTIFIER` / Palabras Reservadas

```
Regex:   [a-zA-Z_][a-zA-Z0-9_]*
```

Significa:
- `[a-zA-Z_]` → empieza con letra o guión bajo
- `[a-zA-Z0-9_]*` → seguido de cero o más letras, dígitos o guiones bajos

**Autómata:**
```
              [a-zA-Z_]         [a-zA-Z0-9_]
  INICIO ─────────────► q1* ─────────────────► q1*   (bucle)
```

**El truco de las palabras reservadas:** después de capturar el lexema, el lexer
consulta el diccionario `RESERVED`:

```python
def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    token_type = RESERVED.get(t.value.lower(), "IDENTIFIER")
    t.type  = token_type
    t.value = t.value.lower() if token_type != "IDENTIFIER" else t.value
    return t
```

Si `t.value` existe en `RESERVED` → cambia el tipo al tipo reservado.
Si no existe → el tipo queda como `IDENTIFIER`.

Por ejemplo: `tempo` → busca en `RESERVED` → encuentra `"TEMPO_KW"` → cambia tipo.
Por ejemplo: `melodia` → no existe en `RESERVED` → queda como `IDENTIFIER("melodia")`.

---

#### TOKEN: `LBRACE` y `RBRACE` — Llaves

```python
t_LBRACE = r"\{"
t_RBRACE = r"\}"
```

Son cadenas simples (no funciones), tienen menor prioridad. Las llaves `{` y `}` se
deben escapar en regex porque tienen significado especial en la sintaxis de regex.

---

#### COMENTARIOS — Descartados, no generan token

```python
def t_COMMENT(t):
    r"\#[^\n]*"
    pass  # no retorna → token descartado
```

Regex: `#[^\n]*` significa: el carácter `#` seguido de cualquier cosa que NO sea
un salto de línea. La función no retorna nada, así que PLY descarta el token.

---

#### SALTOS DE LÍNEA — Solo actualizan el contador de líneas

```python
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
```

`\n+` captura uno o más saltos de línea. La función actualiza `lineno` pero no
retorna el token, así que también se descarta. Esto permite reportar en qué
línea está cada error.

---

#### CARACTERES IGNORADOS — Espacios, tabs, retorno de carro

```python
t_ignore = " \t\r"
```

Todos los espacios, tabulaciones y retornos de carro se ignoran silenciosamente
sin generar token ni error.

---

### Todos los Tokens Reconocidos

| Token | Tipo | Ejemplos | Cómo se reconoce |
|---|---|---|---|
| `TEMPO_KW` | Keyword | `tempo` | Via RESERVED desde IDENTIFIER |
| `VOLUME_KW` | Keyword | `volume` | Via RESERVED |
| `INSTRUMENT_KW` | Keyword | `instrument` | Via RESERVED |
| `TRACK_KW` | Keyword | `track` | Via RESERVED |
| `REPEAT_KW` | Keyword | `repeat` | Via RESERVED |
| `CHORD_KW` | Keyword | `chord` | Via RESERVED |
| `REST` | Keyword | `rest` | Via RESERVED |
| `NOTE` | Nota musical | `C4`, `D#3`, `Eb5` | `t_NOTE` función con alta prioridad |
| `DURATION` | Duración | `negra`, `blanca`, `corchea` | Via RESERVED desde IDENTIFIER |
| `INSTR_NAME` | Instrumento | `piano`, `violin`, `guitar` | Via RESERVED |
| `NUMBER` | Entero | `120`, `2`, `80` | `t_NUMBER` función |
| `IDENTIFIER` | Nombre libre | `melodia`, `coro` | `t_IDENTIFIER` (fallback) |
| `LBRACE` | Delimitador | `{` | Cadena string `t_LBRACE` |
| `RBRACE` | Delimitador | `}` | Cadena string `t_RBRACE` |

---

### Diccionario RESERVED — La tabla de palabras reservadas

```python
RESERVED: dict[str, str] = {
    # Comandos
    "tempo":       "TEMPO_KW",
    "instrument":  "INSTRUMENT_KW",
    "track":       "TRACK_KW",
    "repeat":      "REPEAT_KW",
    "chord":       "CHORD_KW",
    "rest":        "REST",
    "volume":      "VOLUME_KW",
    # Duraciones musicales
    "redonda":     "DURATION",
    "blanca":      "DURATION",
    "negra":       "DURATION",
    "corchea":     "DURATION",
    "semicorchea": "DURATION",
    "fusa":        "DURATION",
    "semifusa":    "DURATION",
    # Instrumentos MIDI (32 total)
    "piano":       "INSTR_NAME",
    "violin":      "INSTR_NAME",
    "guitar":      "INSTR_NAME",
    "drums":       "INSTR_NAME",
    # ... y 28 más
}
```

Este diccionario es **centralizado y extensible**: agregar un nuevo instrumento
o duración al lenguaje es tan simple como agregar una línea al diccionario.

---

### Manejo de Errores Léxicos

```python
def t_error(t):
    col  = _find_column(t.lexer.lexdata, t)
    char = t.value[0]
    msg  = _build_error_msg(char, t.lineno, col)
    if hasattr(t.lexer, "error_list"):
        t.lexer.error_list.append({"line": t.lineno, "col": col, "char": char, "msg": msg})
    else:
        print(msg)
    t.lexer.skip(1)   # ← avanza 1 carácter y continúa
```

Cuando se encuentra un carácter no reconocido:
1. Calcula la columna exacta con `_find_column`
2. Construye un mensaje descriptivo con `_build_error_msg`
3. Agrega el error a `error_list` (para que la GUI lo muestre)
4. **Avanza 1 carácter** (`skip(1)`) y continúa — no se detiene

El diccionario `_ERROR_HINTS` tiene mensajes específicos para ~25 caracteres comunes:

```python
_ERROR_HINTS = {
    "@":  "El símbolo '@' no pertenece al alfabeto de BeatScript.",
    ";":  "El ';' no es necesario — cada instrucción va en su propia línea.",
    "(":  "Paréntesis no válido — los bloques se delimitan con { }",
    "/":  "Para comentarios usa '#', no '/' ni '//'.",
    # ... 20 más
}
```

**Formato del error:** `[ERROR LÉXICO] Línea X, Col Y: carácter 'X' no reconocido — <mensaje de ayuda>`

---

### Cálculo de Columna

```python
def _find_column(source: str, token) -> int:
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

- `token.lexpos` = posición absoluta en bytes desde el inicio del texto
- `rfind("\n", 0, lexpos)` = encuentra el último salto de línea ANTES del token
- La columna = posición del token - posición del inicio de la línea + 1 (base 1)

**Ejemplo:** si el texto tiene `"tempo 120\nC4 blancaa"` y el token `blancaa` está
en `lexpos=13`:
- El último `\n` está en posición 9
- `line_start = 9 + 1 = 10`
- Columna = `13 - 10 + 1 = 4`

---

### Función Principal: `tokenize`

```python
def tokenize(source_code: str, *, debug: bool = False, collect_errors: bool = False):
```

Esta es la API pública del lexer. Parámetros:
- `source_code`: el texto a tokenizar
- `debug=True`: imprime la tabla de tokens en consola
- `collect_errors=True`: retorna `(tokens, errores)` en lugar de solo `tokens`

**Uso desde la GUI:**
```python
tokens, errors = tokenize(source, collect_errors=True)
```

Internamente:
1. Crea un nuevo lexer con `build_lexer()` → `lex.lex()`
2. Le asigna una lista vacía para errores: `lx.error_list = errors`
3. Le pasa el código: `lx.input(source_code)`
4. Consume todos los tokens: `result = list(lx)`
5. Retorna los tokens y los errores acumulados

---

## 5. Filtro de Validación

**Función:** `_validar_tokens_extra(tokens, source)` en `main_gui.py`

Este filtro corre DESPUÉS del lexer y ANTES del parser. Su propósito es detectar
patrones de tokens que son léxicamente válidos pero semánticamente sospechosos.

Es como un **cortafuegos** entre las dos etapas principales.

### Qué detecta:

#### 1. Instrumento no reconocido
```python
if tok.type == "INSTRUMENT_KW":
    siguiente = tokens[i + 1]
    if siguiente.type == "IDENTIFIER":   # no es INSTR_NAME, es IDENTIFIER
        avisos.append("[AVISO] ... instrumento no reconocido")
```
Ejemplo: `instrument guitarra_electrica` → `guitarra_electrica` no está en RESERVED,
entonces es `IDENTIFIER`, no `INSTR_NAME`. El filtro lo detecta.

#### 2. Nota inválida tipo E44
```python
elif tok.type in ("NOTE", "REST"):
    siguiente = tokens[i + 1]
    if siguiente.type == "NUMBER":    # nota seguida de número = E44, E4444, etc.
        avisos.append("[AVISO] ... parece una nota inválida")
```
Ejemplo: `E44` → lexer lo divide en `NOTE(E4) + NUMBER(4)` → filtro detecta el patrón.

#### 3. Duración inválida
```python
    elif siguiente.type == "IDENTIFIER":  # nota seguida de texto desconocido
        avisos.append("[AVISO] ... no es una duración válida")
```
Ejemplo: `C4 blancaa` → `blancaa` es IDENTIFIER (no está en RESERVED como DURATION).

#### 4. Volume fuera de rango MIDI
```python
elif tok.type == "VOLUME_KW":
    if siguiente.type == "NUMBER" and not (0 <= siguiente.value <= 127):
        avisos.append("[AVISO] ... volumen fuera de rango")
```
El MIDI solo acepta velocidades de 0 a 127.

#### 5. Identificador con forma de nota inválida
```python
elif tok.type == "IDENTIFIER":
    if re.match(r"^[A-Ga-g].+\d$", val):  # empieza con letra de nota y termina en dígito
        avisos.append("[AVISO] ... parece una nota inválida")
```
Ejemplo: `Ertr4` → no fue capturado como NOTE (porque `r` después de `E` no es `#` ni dígito),
quedó como IDENTIFIER, pero el regex lo identifica como probable nota mal escrita.

### Comportamiento del filtro

Si encuentra **cualquier aviso**, la compilación se **detiene** y muestra todos los
avisos antes de llegar al parser. Esto es intencional: el parser no debería intentar
construir un AST a partir de tokens con este tipo de problemas.

---

## 6. ETAPA 2 — Análisis Sintáctico

**Archivo:** `beatscript/parser.py`

### ¿Qué es el análisis sintáctico?

El análisis sintáctico (parsing) toma la lista plana de tokens del lexer y verifica
que su **orden y estructura** correspondan a la gramática del lenguaje.

Si el lexer verificaba que cada "palabra" existe, el parser verifica que las "frases"
estén bien construidas.

El resultado es el **AST (Árbol Sintáctico Abstracto)** — una representación
jerárquica del programa que refleja su estructura lógica.

---

### Gramática EBNF de BeatScript

EBNF significa "Extended Backus-Naur Form" — la notación estándar para describir
gramáticas formales.

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

**Puntos clave de la gramática:**
- `*` = cero o más veces
- `+` = una o más veces
- `|` = alternativas (OR)
- `chord` puede aparecer tanto a nivel de sentencia global como dentro de un track
- `repeat` también es dual: a nivel global y dentro de un track
- La gramática es **LL(1)** — siempre se puede decidir qué regla aplicar mirando
  solo el token actual

---

### Parser Recursivo Descendente

El parser de BeatScript es un **parser recursivo descendente** (recursive descent parser).

Esto significa que **cada regla gramatical tiene su propio método Python**:

| Regla gramatical | Método del parser |
|---|---|
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

El parser es **LL(1)** porque siempre decide qué método llamar mirando **un solo token
hacia adelante** con `_current_token()`.

---

### Métodos de Navegación del Parser

El parser mantiene una lista de tokens y un índice de posición:

```python
class BeatScriptParser:
    def __init__(self, tokens, source_code=""):
        self.tokens = tokens      # lista de LexTokens del lexer
        self.source_code = source_code  # texto original (para calcular columnas)
        self.pos = 0              # índice del token actual
        self.errors = []          # errores sintácticos encontrados
```

Métodos de navegación:

```python
def _current_token(self):
    # Retorna el token en self.tokens[self.pos] sin avanzar
    # Retorna None si llegamos al final
    
def _peek_token(self, offset=1):
    # Retorna el token N posiciones adelante sin avanzar
    
def _advance(self):
    # Avanza al siguiente token: self.pos += 1
    
def _is_at_end(self):
    # True si self.pos >= len(self.tokens)
    
def _check(self, token_type):
    # True si el token actual es del tipo especificado
    
def _consume(self, token_type, message=None):
    # Si el token actual es del tipo correcto: lo retorna y avanza
    # Si NO es del tipo correcto: registra error y retorna None
```

`_consume` es el método más importante — es el que "consume" tokens esperados:

```python
def _consume(self, token_type, message=None):
    if self._check(token_type):      # ¿es el tipo correcto?
        token = self._current_token()
        self._advance()              # avanzar al siguiente
        return token                 # retornar el token consumido
    
    # No era el tipo correcto → error
    current = self._current_token()
    error_msg = message or f"Se esperaba '{token_type}', se encontró '{current.type}'"
    if current:
        self._add_error_with_suggestions(current, error_msg)
    else:
        self._add_error(f"Fin de archivo inesperado — {error_msg}")
    return None
```

---

### Todos los Métodos del Parser en Detalle

#### `parse()` — Punto de entrada

```python
def parse(self):
    program = Program()           # crear nodo raíz del AST
    while not self._is_at_end():  # mientras haya tokens
        stmt = self._parse_statement()
        if stmt:
            program.statements.append(stmt)
    return program
```

Recorre todos los tokens llamando a `_parse_statement()` en un bucle.
Retorna el nodo `Program` que es la raíz del AST.

---

#### `_parse_statement()` — Decide qué tipo de sentencia parsear

```python
def _parse_statement(self):
    current = self._current_token()
    
    if self._check("TEMPO_KW"):      return self._parse_tempo()
    elif self._check("VOLUME_KW"):   return self._parse_volume()
    elif self._check("INSTRUMENT_KW"): return self._parse_instrument()
    elif self._check("TRACK_KW"):    return self._parse_track()
    elif self._check("CHORD_KW"):    return self._parse_chord()
    elif self._check("REPEAT_KW"):   return self._parse_repeat_statement()
    else:
        # token inesperado → registrar error + modo pánico
        self._add_error("...", token=current)
        self._synchronize({"TEMPO_KW", "VOLUME_KW", "INSTRUMENT_KW",
                           "TRACK_KW", "REPEAT_KW"})
        return None
```

Esto es el **mecanismo LL(1)**: mira el token actual y decide qué regla aplicar.

---

#### `_parse_tempo()` — Parsea `tempo NUMBER`

```python
def _parse_tempo(self):
    self._consume("TEMPO_KW")          # consume 'tempo'
    num_token = self._consume("NUMBER", "Se esperaba un número después de 'tempo'")
    if num_token:
        return Tempo(num_token.value)  # crea nodo AST
    return None
```

---

#### `_parse_track()` — Parsea `track IDENTIFIER { eventos }`

```python
def _parse_track(self):
    self._consume("TRACK_KW")
    name_token = self._consume("IDENTIFIER", "Se esperaba un nombre de track")
    self._consume("LBRACE", "Se esperaba '{'")
    
    events = []
    while not self._check("RBRACE") and not self._is_at_end():
        event = self._parse_event()  # parsea cada evento dentro
        if event:
            events.append(event)
    
    self._consume("RBRACE", "Se esperaba '}'")
    
    if name_token:
        return Track(name_token.value, events)
    return None
```

---

#### `_parse_chord()` — Parsea `chord { NOTE+ DURATION }`

```python
def _parse_chord(self):
    kw_token = self._current_token()
    self._consume("CHORD_KW")
    self._consume("LBRACE", "Se esperaba '{' después de 'chord'")
    
    notas = []
    while self._check("NOTE") and not self._is_at_end():
        note_token = self._consume("NOTE")
        if note_token:
            notas.append(note_token.value)  # acumular notas
    
    duration_token = self._consume("DURATION", "Se esperaba una duración al final del acorde")
    self._consume("RBRACE", "Se esperaba '}'")
    
    if not notas:  # chord vacío es inválido
        self._add_error("El acorde debe contener al menos una nota", token=kw_token)
        return None
    
    return Chord(notas, duration_token.value)
```

El `while self._check("NOTE")` acumula todas las notas del acorde hasta encontrar
la duración al final: `chord { C4 E4 G4 blanca }` → notas=["C4","E4","G4"], dur="blanca"

---

#### `_parse_event()` — Decide qué tipo de evento parsear (dentro de track)

```python
def _parse_event(self):
    if self._check("NOTE"):     return self._parse_note()
    elif self._check("REST"):   return self._parse_rest()
    elif self._check("CHORD_KW"): return self._parse_chord()
    elif self._check("REPEAT_KW"): return self._parse_repeat_event()
    else:
        # token inválido dentro de track → error + modo pánico
        self._add_error("...", token=current)
        self._synchronize({"NOTE", "REST", "CHORD_KW", "REPEAT_KW", "RBRACE"})
        return None
```

---

#### `_parse_note()` — Parsea `NOTE DURATION`

```python
def _parse_note(self):
    note_token = self._consume("NOTE")
    duration_token = self._consume("DURATION", "Se esperaba una duración después de la nota")
    if note_token and duration_token:
        return Note(note_token.value, duration_token.value)
    return None
```

---

### Manejo de Errores Sintácticos — Con Línea y Columna

El parser usa `_get_column` para calcular la columna exacta del error:

```python
def _get_column(self, token):
    if not self.source_code or not hasattr(token, "lexpos"):
        return "?"
    line_start = self.source_code.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

El método `_add_error` formatea todos los mensajes de error uniformemente:

```python
def _add_error(self, message, token=None):
    if token is not None:
        col = self._get_column(token)
        self.errors.append(
            f"[ERROR SINTÁCTICO] Línea {token.lineno}, Col {col}: {message}"
        )
    else:
        self.errors.append(f"[ERROR SINTÁCTICO] {message}")
```

**Formato de salida:** `[ERROR SINTÁCTICO] Línea 3, Col 5: 'tracck' no es una palabra reservada válida.`

---

### Sugerencias de Corrección con difflib

El método `_get_suggestions_for_word` usa `difflib.get_close_matches` para
encontrar palabras reservadas similares al error del usuario:

```python
def _get_suggestions_for_word(word, keywords_dict=None, cutoff=0.6, max_suggestions=3):
    candidates = list(keywords_dict.keys())  # todas las palabras reservadas
    suggestions = difflib.get_close_matches(
        word.lower(),       # la palabra errónea
        candidates,         # candidatos (RESERVED)
        n=max_suggestions,  # máximo 3 sugerencias
        cutoff=0.6          # umbral de similitud 60%
    )
    return suggestions
```

**Algoritmo Ratcliff/Obershelp** de `difflib`: mide el porcentaje de caracteres
coincidentes entre dos strings. Un cutoff de 0.6 significa que al menos el 60% de
los caracteres deben coincidir.

**Ejemplo:** `tracck` vs `track` → similitud ~0.91 (alta) → se sugiere `track`

El mensaje de error con sugerencia se ve así:
```
[ERROR SINTÁCTICO] Línea 4, Col 1: 'tracck' no es una palabra reservada válida.
   💡 Sugerencia: ¿Quisiste decir 'track'?
```

---

### Recuperación de Errores: Modo Pánico (_synchronize)

**El problema sin modo pánico:** un solo typo puede generar una cascada de 5, 10 o
más errores falsos porque el parser intenta parsear tokens que no tienen sentido
después del error.

Por ejemplo, `tracck melodia { C4 negra }` sin modo pánico generaría:
- Error 1: `tracck` no es válido
- Error 2: `melodia` no esperado
- Error 3: `{` no esperado
- Error 4: `C4` no esperado
- Error 5: `negra` no esperado
- Error 6: `}` no esperado

**Con modo pánico:** solo 1 error real.

```python
def _synchronize(self, sync_tokens):
    """
    Recuperación de errores en Modo Pánico.
    Descarta tokens hasta encontrar uno 'seguro' (token de sincronización)
    desde donde el parser puede reanudar limpiamente.
    """
    sync_set = set(sync_tokens)  # set para búsqueda O(1)
    while not self._is_at_end():
        if self._current_token().type in sync_set:
            return      # encontramos punto seguro → detener descarte
        self._advance() # descartar token y seguir buscando
```

#### ¿Por qué usar `set` en lugar de `list`?

La búsqueda en un `set` es **O(1)** (constante) vs **O(n)** en una lista.
Como `_synchronize` puede llamarse muchas veces en un archivo con muchos errores,
la eficiencia importa.

#### Tokens de sincronización según el contexto

Se usan tokens diferentes según dónde ocurra el error:

**En `_parse_statement` (nivel global):**
```python
self._synchronize({"TEMPO_KW", "VOLUME_KW", "INSTRUMENT_KW", "TRACK_KW", "REPEAT_KW"})
```
Son las únicas palabras que pueden iniciar una sentencia válida.

**En `_parse_event` (dentro de un track):**
```python
self._synchronize({"NOTE", "REST", "CHORD_KW", "REPEAT_KW", "RBRACE"})
```
`RBRACE` es especialmente importante: si el bloque entero está roto, el modo pánico
llega al `}` y el parser cierra el track correctamente.

#### ¿Qué pasa si nunca aparece el token de sincronización?

El `while not self._is_at_end()` garantiza que si no hay token de sincronización,
el bucle termina cuando se acaban los tokens. El parser llega al final limpiamente
sin colgarse.

---

## 7. El AST — Árbol Sintáctico Abstracto

**Archivo:** `beatscript/parser.py` (líneas 61-157)

El AST es la representación interna del programa como un **árbol de objetos Python**.
A diferencia de la lista plana de tokens, el AST tiene **estructura jerárquica** que
refleja la lógica del programa.

### Todas las Clases de Nodos

Todas heredan de `ASTNode` (clase base):

```python
class ASTNode:
    def __repr__(self):
        return f"<{self.__class__.__name__}>"
```

---

#### `Program` — Nodo raíz
```python
class Program(ASTNode):
    def __init__(self):
        self.statements = []  # lista de sentencias del programa
```
Es el nodo raíz del árbol. Contiene todas las sentencias de nivel superior.

---

#### `Tempo` — Velocidad musical
```python
class Tempo(ASTNode):
    def __init__(self, bpm):
        self.bpm = bpm  # int, ej. 120
```
Representa `tempo 120`. `bpm` = beats per minute.

---

#### `Volume` — Volumen MIDI
```python
class Volume(ASTNode):
    def __init__(self, level):
        self.level = level  # int, 0-127
```
Representa `volume 80`. Controla la velocidad (intensidad) de las notas MIDI.

---

#### `Instrument` — Instrumento MIDI
```python
class Instrument(ASTNode):
    def __init__(self, name):
        self.name = name  # str, ej. "violin"
```
Representa `instrument violin`. El nombre se usará para buscar el programa MIDI.

---

#### `Track` — Pista musical
```python
class Track(ASTNode):
    def __init__(self, name, events):
        self.name = name      # str, nombre del track (ej. "melodia")
        self.events = events  # list[Note|Rest|Chord|Repeat]
```
Representa un bloque `track melodia { ... }`. Contiene los eventos musicales.

---

#### `Note` — Nota musical individual
```python
class Note(ASTNode):
    def __init__(self, pitch, duration):
        self.pitch = pitch        # str, ej. "C4", "D#3", "Eb5"
        self.duration = duration  # str, ej. "negra", "blanca"
```
Representa `C4 negra`. Es el evento musical más básico.

---

#### `Rest` — Silencio
```python
class Rest(ASTNode):
    def __init__(self, duration):
        self.duration = duration  # str, ej. "corchea"
```
Representa `rest corchea`. Un silencio de la duración especificada.

---

#### `Chord` — Acorde (múltiples notas simultáneas)
```python
class Chord(ASTNode):
    def __init__(self, notes, duration):
        self.notes = notes        # list[str], ej. ["C4", "E4", "G4"]
        self.duration = duration  # str, duración compartida por todas las notas
```
Representa `chord { C4 E4 G4 blanca }`. Todas las notas suenan al mismo tiempo.

---

#### `Repeat` — Repetición de bloque
```python
class Repeat(ASTNode):
    def __init__(self, count, events):
        self.count = count    # int, número de repeticiones
        self.events = events  # list[ASTNode], contenido a repetir
```
Representa `repeat 2 { C4 negra D4 negra }`. El contenido se repite `count` veces.

---

### Representación Visual del AST en Texto

La función `ast_to_tree_string(node, indent, is_last)` convierte el AST en
una representación visual de árbol usando caracteres Unicode:

```
Program
├── Tempo: 120 BPM
├── Volume: 80
├── Instrument: violin
└── Track 'melodia'
    ├── Nota: C4 (negra)
    ├── Nota: D4 (negra)
    ├── Chord (blanca)
    │   ├── C4
    │   ├── E4
    │   └── G4
    └── Repeat x2
        ├── Nota: G4 (negra)
        └── Nota: A4 (negra)
```

Se usa en el panel "Árbol Sintáctico — Parser (Etapa 2)" de la GUI.

### Representación para Tabla

La función `ast_to_table_rows(node, parent_id)` genera tuplas
`(parent_id, node_id, valores, tag)` para el `ttk.Treeview` de la GUI.

---

## 8. Árbol de Derivación Visual

**Función:** `generate_visual_tree(ast_root, output_filename="parse_tree")` en `parser.py`

Esta función genera un PNG del árbol de derivación usando **Graphviz**.

### Diferencia entre AST y Árbol de Derivación

| | AST | Árbol de Derivación |
|---|---|---|
| Muestra | Solo nodos semánticos | Reglas gramaticales + tokens terminales |
| Nodos hoja | El dato (`120`) | El token con tipo (`NUMBER '120'`) |
| Nodos internos | Tipo de sentencia (`Tempo`) | Nombre de la regla (`sentencia\ntempo`) |
| Uso principal | Generación de código | Análisis académico, depuración |

### Tipos de Nodos en el Grafo

```python
nodo_regla(etiqueta, color)        # rectángulo — regla gramatical
nodo_terminal(tipo, valor, color)  # elipse     — token terminal
nodo_lista(etiqueta)               # rombo      — contenedor de listas
```

El nodo raíz `programa` usa forma especial `doubleoctagon`.

### Patrón Visitor

La función usa el **patrón de diseño Visitor** para recorrer el AST:

```python
def visitar(node):
    if isinstance(node, Program):    return _v_programa(node)
    if isinstance(node, Tempo):      return _v_tempo(node)
    if isinstance(node, Track):      return _v_track(node)
    # etc...
```

Cada visitante crea los nodos del grafo y los conecta con `arco(padre, hijo)`.

### Solución al Problema del PATH en Windows

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

Python no siempre hereda el PATH del sistema. La función inyecta la ruta de
Graphviz programáticamente para garantizar que `dot.exe` sea encontrado.

---

## 9. ETAPA 3 — Generación MIDI

**Archivo:** `beatscript/midi_gen.py`

### ¿Qué es MIDI?

MIDI (Musical Instrument Digital Interface) es un protocolo estándar para
representar música de forma digital. No almacena audio, sino instrucciones:
"toca la nota 60 con el instrumento 0 durante 1 beat".

### Tablas de Conversión

**Notas a semitonos:**
```python
NOTE_SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
```

**Duraciones a beats:**
```python
DURATION_BEATS = {
    'redonda':     4.0,   # 4 beats
    'blanca':      2.0,   # 2 beats
    'negra':       1.0,   # 1 beat
    'corchea':     0.5,   # 0.5 beats
    'semicorchea': 0.25,
    'fusa':        0.125,
    'semifusa':    0.0625,
}
```

**Instrumentos a programas MIDI General:**
```python
INSTRUMENT_PROGRAM = {
    'piano': 0, 'violin': 40, 'guitar': 25, 'drums': 0, # ...32 instrumentos
}
```

---

### `note_to_midi(note_str)` — Convierte nota a número MIDI

```python
def note_to_midi(note_str: str) -> int:
    s = note_str.upper()
    letter = s[0]           # la letra: C, D, E, F, G, A, B
    rest   = s[1:]
    if rest and rest[0] in ('#', 'B') and len(rest) > 1:
        alt, octave = rest[0], int(rest[1])   # con alteración
    else:
        alt, octave = '', int(rest[0])         # sin alteración
    
    pitch = NOTE_SEMITONES[letter] + (octave + 1) * 12
    if alt == '#': pitch += 1   # sostenido: sube 1 semitono
    if alt == 'B': pitch -= 1   # bemol: baja 1 semitono
    return pitch
```

**Fórmula MIDI estándar:** `semitono_de_la_letra + (octava + 1) * 12`

Ejemplos:
- `C4` = 0 + (4+1)*12 = 0 + 60 = **60** (Do central)
- `A4` = 9 + (4+1)*12 = 9 + 60 = **69** (La de afinar)
- `D#3` = 2 + 1 + (3+1)*12 = 3 + 48 = **51**

---

### `_collect_block(tokens, start)` — Extrae contenido entre llaves

```python
def _collect_block(tokens: list, start: int):
    depth, end = 1, start
    while end < len(tokens) and depth > 0:
        if   tokens[end].type == 'LBRACE': depth += 1   # abre: incrementar
        elif tokens[end].type == 'RBRACE': depth -= 1   # cierra: decrementar
        end += 1
    return tokens[start:end - 1], end   # tokens dentro del bloque, índice siguiente
```

Usa un contador de **profundidad** para manejar bloques anidados correctamente.
Cuando `depth` llega a 0, encontramos el `}` que cierra el bloque.

---

### `tokens_to_midi(tokens, output_path)` — Función principal

Esta función recorre la lista de tokens con una variable de tiempo `t` (en beats)
y genera el archivo MIDI:

```python
def tokens_to_midi(tokens: list, output_path: str = "output.mid") -> str:
    midi     = MIDIFile(1)   # archivo MIDI con 1 track
    track    = 0
    channel  = 0
    tempo    = 120           # BPM por defecto
    program  = 0             # piano por defecto
    velocity = 80            # volumen por defecto
    
    def process(tok_list, t):   # función recursiva interna
        ...
    
    process(tokens, 0.0)    # procesar desde el tiempo 0
    
    with open(output_path, 'wb') as f:
        midi.writeFile(f)
    
    return output_path
```

La función `process` interna maneja cada tipo de token:

| Token encontrado | Acción |
|---|---|
| `VOLUME_KW + NUMBER` | Actualiza `velocity` (0-127) |
| `TEMPO_KW + NUMBER` | Actualiza `tempo` y llama `midi.addTempo(track, t, tempo)` |
| `INSTRUMENT_KW + INSTR_NAME` | Llama `midi.addProgramChange(track, channel, t, program)` |
| `TRACK_KW` | Extrae el bloque `{}` y lo procesa recursivamente con `process(block, t)` |
| `REPEAT_KW + NUMBER` | Extrae el bloque y lo ejecuta `n` veces en bucle |
| `CHORD_KW` | Agrega todas las notas del bloque en el mismo tiempo `t`, luego avanza `t` |
| `NOTE + DURATION` | Llama `midi.addNote(...)` y avanza `t` en la duración |
| `REST + DURATION` | Solo avanza `t` — silencio |

---

## 10. Interfaz Gráfica

**Archivo:** `main_gui.py`

**Framework:** `customtkinter` (CTk) — wrapper de tkinter con modo oscuro y widgets modernos.

### Estructura de la Ventana

```
┌──────────────────────────────────────────────────────────────────────┐
│  BeatScript IDE  [Compilar y Reproducir] [Detener] [Abrir] [Guardar] │ ← toolbar
├───────────────────────────┬──────────────────────────────────────────┤
│                           │  Tabla de Tokens — Lexer (Etapa 1)       │
│  Editor de código         │  # | TIPO | VALOR | LÍNEA | COL          │
│  (CTkTextbox)             │──────────────────────────────────────────│
│  con resaltado de         │  Árbol Sintáctico — Parser (Etapa 2)     │
│  sintaxis en tiempo real  │  [Ver Arbol de Derivacion]               │
│                           │  Program                                  │
│  Línea: X, Col: Y         │    ├── Tempo: 120 BPM                    │
│  Líneas totales: Z        │    └── Track 'melodia'                   │
├───────────────────────────┴──────────────────────────────────────────┤
│  Consola                                                              │
│  Iniciando análisis léxico...                                         │
│  Análisis léxico completado — 24 tokens encontrados.                  │
└──────────────────────────────────────────────────────────────────────┘
```

### Componentes Principales

| Atributo | Widget | Función |
|---|---|---|
| `self.editor` | `CTkTextbox` | Editor de código fuente con resaltado |
| `self._line_canvas` | `tk.Canvas` | Números de línea alineados con el editor |
| `self.status_label` | `CTkLabel` | Barra de estado: Línea/Col/Total |
| `self.token_tree` | `ttk.Treeview` | Tabla de tokens con columnas |
| `self.ast_textbox` | `CTkTextbox` | Árbol sintáctico en texto |
| `self.consola` | `CTkTextbox` | Mensajes del compilador |
| `self.current_ast` | `Program/None` | AST del último compilado exitoso |

### Método `_compilar()` — Orquesta todo el pipeline

```python
def _compilar(self):
    self._log("", clear=True)                          # limpiar consola
    source = self.editor.get("1.0", "end-1c").strip()  # obtener código
    
    # ETAPA 1: Léxico
    tokens, errors = tokenize(source, collect_errors=True)
    if errors:
        for err in errors:
            self._log(f"  {err['msg']}")
        return                # DETENER
    
    # Filtro de validación
    avisos = self._validar_tokens_extra(tokens, source)
    if avisos:
        for av in avisos:
            self._log(f"  {av}")
        return                # DETENER
    
    self._llenar_tabla_tokens(tokens, source)          # mostrar tokens en tabla
    
    # ETAPA 2: Sintáctico
    parser = BeatScriptParser(tokens, source)
    ast = parser.parse()
    if parser.errors:
        for err in parser.errors:
            self._log(f"  {err}")
        return                # DETENER
    
    self.current_ast = ast
    self._mostrar_ast(ast)                             # mostrar árbol en GUI
    
    # Generar y reproducir MIDI
    tokens_to_midi(tokens, midi_path)
    pygame.mixer.music.load(midi_path)
    pygame.mixer.music.play()
```

### Barra de Estado del Editor

```python
def _actualizar_estado(self, event=None):
    inner = self.editor._textbox    # widget tk.Text interno
    pos = inner.index("insert")     # posición del cursor: "linea.columna"
    linea, col_raw = pos.split(".")
    col = int(col_raw) + 1          # tk.Text usa columna base 0, convertir a base 1
    total = inner.get("1.0", "end-1c").split("\n")... # contar líneas reales
    self.status_label.configure(text=f"  Línea: {linea}, Col: {col}  |  Líneas totales: {total}")
```

### Números de Línea con Canvas

Los números de línea usan `tk.Canvas` + `dlineinfo()` para alinear perfectamente
con el editor:

```python
def _actualizar_lineas(self):
    inner  = self.editor._textbox
    canvas = self._line_canvas
    canvas.delete("all")
    
    # Offset entre canvas y textbox (CTkTextbox añade padding interno)
    offset = inner.winfo_rooty() - canvas.winfo_rooty()
    
    first = int(inner.index("@0,0").split(".")[0])           # primera línea visible
    last  = int(inner.index(f"@0,{inner.winfo_height()}").split(".")[0])  # última
    
    for lineno in range(first, last + 2):
        info = inner.dlineinfo(f"{lineno}.0")    # posición Y exacta en píxeles
        if info is None:
            break
        y_center = info[1] + info[3] // 2 + offset
        canvas.create_text(cw, y_center, text=str(lineno), ...)
```

`dlineinfo` retorna `(x, y, width, height, baseline)` — la posición y dimensiones
de la línea en el viewport del widget. Esto garantiza alineación perfecta
independientemente del padding interno del CTkTextbox.

---

## 11. Resaltado de Sintaxis en Tiempo Real

El editor tiene resaltado de sintaxis que se actualiza con cada tecla presionada.

### Cómo funciona

1. En cada `<KeyRelease>`, se llama `_aplicar_resaltado()`
2. Se obtiene el código del editor
3. Se llama al **lexer real** (`tokenize()`) para obtener los tokens
4. Para cada token, se calcula su posición en el editor con `lexpos`
5. Se aplica el tag de color correspondiente con `inner.tag_add(tag, start, end)`

```python
def _aplicar_resaltado(self):
    inner  = self.editor._textbox
    source = inner.get("1.0", "end-1c")
    
    # Limpiar colores anteriores
    for tag in self._TOKEN_TAG.values():
        inner.tag_remove(tag, "1.0", "end")
    inner.tag_remove("hl_comment", "1.0", "end")
    
    # Colorear comentarios con regex (el lexer los descarta)
    for m in re.finditer(r"#[^\n]*", source):
        inner.tag_add("hl_comment", f"1.0 + {m.start()} chars", f"1.0 + {m.end()} chars")
    
    # Colorear tokens del lexer
    tokens, _ = tokenize(source, collect_errors=True)
    for tok in tokens:
        tag = self._TOKEN_TAG.get(tok.type)
        if tag is None:
            continue
        tok_len = len(str(tok.value))
        start   = f"1.0 + {tok.lexpos} chars"
        end     = f"1.0 + {tok.lexpos + tok_len} chars"
        inner.tag_add(tag, start, end)
```

### Tabla de Colores

```python
_TOKEN_TAG = {
    "TEMPO_KW": "hl_keyword",      # Azul-morado  #7986cb
    "TRACK_KW": "hl_keyword",
    "REPEAT_KW": "hl_keyword",
    # ... todos los keywords
    "NOTE":      "hl_note",        # Verde         #66bb6a
    "DURATION":  "hl_duration",    # Naranja       #ffb74d
    "INSTR_NAME":"hl_instrument",  # Cian          #4dd0e1
    "NUMBER":    "hl_number",      # Naranja claro #ff8a65
    "LBRACE":    "hl_brace",       # Blanco suave  #e0e0e0
    "RBRACE":    "hl_brace",
    "IDENTIFIER":"hl_identifier",  # Gris claro    #cfd8dc
}
```

### Diferencia entre los dos "lexers"

| | Lexer Visual (resaltado) | Lexer Formal (compilación) |
|---|---|---|
| **Cuándo corre** | Cada `<KeyRelease>` | Al presionar "Compilar" |
| **Qué hace** | Colorear tokens en pantalla | Producir AST completo + errores |
| **Si hay error** | Colorea lo que puede, ignora el resto | Detiene la compilación |
| **Usa** | El mismo `tokenize()` | `tokenize()` + `BeatScriptParser` |

Ambos usan el **mismo lexer real** (`tokenize`), pero solo el formal construye el AST.

---

## 12. Catálogo de Errores

El botón "Catalogo de Errores" abre una ventana con documentación técnica de todos
los tipos de error, implementada con **tarjetas** (`CTkFrame` con `corner_radius=10`).

### Tipos de errores documentados

#### Errores de Validación Lógica (Warnings)
- **ERR-VAL-01**: Token de Identificador Corrupto (E44, Er21)
- **ERR-VAL-02**: Tipo de Dato Duración Desconocido (blancaa, negra1)

#### Errores Léxicos
- **ERR-LEX-01**: Carácter Ilegal Detectado (@, $, &)

#### Errores Sintácticos
- **ERR-SIN-01**: Violación de Estructura de Evento (NUMBER donde se esperaba DURATION)
- **ERR-SIN-02**: EOF Inesperado / Bloque No Cerrado (falta `}`)
- **ERR-SIN-03**: Comando Global No Reconocido + Modo Pánico

---

## 13. Tests del Proyecto

### `beatscript/tests/test_lexer.py` — 20 funciones de prueba

Suite de tests manuales del lexer. Cubre:

| Test | Verifica |
|---|---|
| `test_keywords` | Las 6 keywords retornan el tipo correcto |
| `test_tempo_declaration` | `tempo NUMBER` y que el valor es `int` |
| `test_notes_natural` | Notas C0 a B8 como `NOTE` |
| `test_notes_sharp` | Notas con sostenido: C#4, D#3... |
| `test_notes_flat` | Notas con bemol: Eb5, Bb4... |
| `test_notes_normalized` | `c4` → `"C4"` (normalización) |
| `test_notes_no_octave` | `C` sin octava → `IDENTIFIER`, NO `NOTE` |
| `test_durations` | Las 7 duraciones musicales |
| `test_comments_ignored` | Comentarios no generan tokens |
| `test_multiline_program` | Programa completo de 20 tokens |
| `test_line_numbers` | `lineno` correcto por línea |

Para ejecutar: `python -m beatscript.tests.test_lexer`

### `test_suggestions.py` — Tests de sugerencias del parser

Prueba que el parser genera sugerencias correctas para typos comunes:
- `tempp` → sugiere `tempo`
- `instrumento` → sugiere `instrument`
- `traack` → sugiere `track`
- `repet` → sugiere `repeat`
- `volumen` → sugiere `volume`

---

## 14. Resumen contra la Rúbrica de Evaluación

| Criterio | Puntos | Estado | Evidencia en el código |
|---|---|---|---|
| **1.1** Correctitud tokens | 5/5 | Excelente | 13 tipos de tokens, todos reconocidos |
| **1.2** Manejo errores léxicos | 5/5 | Excelente | `t_error` + `_ERROR_HINTS` (25 chars) |
| **1.3** Eficiencia lexer | 4/5 | Muy bueno | PLY/DFA O(n), sin backtracking |
| **1.4** Espacios y comentarios | 5/5 | Excelente | `t_ignore`, `t_COMMENT`, `t_newline` |
| **1.5** Expresiones regulares | 5/5 | Excelente | Regexes con autómatas documentados |
| **1.6** Flexibilidad lexer | 4/5 | Muy bueno | Diccionario RESERVED centralizado |
| **2.1** Correctitud AST | 5/5 | Excelente | 9 clases de nodos, parser completo |
| **2.2** Tipo de parser | 4/5 | Muy bueno | Recursivo descendente = LL(1) |
| **2.3** Errores sintácticos | 5/5 | Excelente | Línea+Col, sugerencias difflib |
| **2.4** Generación AST | 5/5 | Excelente | AST + texto + Graphviz PNG |
| **2.5** Modularidad parser | 5/5 | Excelente | Un método por regla gramatical |
| **2.6** Recuperación errores | 5/5 | Excelente | `_synchronize` modo pánico |
| **3.1** Integración lexer+parser | 5/5 | Excelente | Pipeline claro en `_compilar()` |
| **3.2** Pruebas integración | 3/5 | Regular | `test_lexer.py` + `test_suggestions.py` |
| **3.3** Casos complejos | 4/5 | Muy bueno | Repeat anidado, chord en track |
| **3.4** Pruebas de error | 3/5 | Regular | Tests parciales, no sistemáticos |
| **4.1** Innovación | 4/5 | Muy bueno | DSL musical + Graphviz + resaltado |
| **4.2** Escalabilidad | 4/5 | Muy bueno | RESERVED extensible, clases modulares |
| **Presentación** | /10 | TBD | — |
| **TOTAL ESTIMADO** | **~82/100** | Bueno | — |

---

## 15. Preguntas Trampa y Respuestas Blindadas

### TRAMPA 1
**"Tu compilador dice que hace análisis semántico, pero eso requiere tabla de símbolos. ¿Realmente lo tienes implementado?"**

**Respuesta:** No tenemos un analizador semántico clásico con tabla de símbolos. Lo que tenemos es un **filtro de validación temprana** — un pre-procesamiento sobre la lista de tokens que detecta anomalías semánticas antes de construir el AST. Es un **análisis semántico ad-hoc** adaptado a las necesidades de BeatScript. Hacemos verificaciones contextuales: notas malformadas (patrón NOTE+NUMBER), duraciones inválidas (NOTE seguido de IDENTIFIER), instrumentos desconocidos, y rango MIDI del volume. No necesitamos tabla de símbolos completa porque BeatScript no tiene variables, funciones ni scope — es un lenguaje imperativo lineal donde no hay referencias cruzadas.

---

### TRAMPA 2
**"¿Por qué `t_NOTE` tiene que ir ANTES que `t_IDENTIFIER`? ¿No podrías poner `t_IDENTIFIER` primero?"**

**Respuesta:** No, y es un punto crítico de diseño. PLY determina la prioridad de funciones-token por orden de aparición en el archivo. Si `t_IDENTIFIER` estuviera primero, su regex `[a-zA-Z_][a-zA-Z0-9_]*` capturaría `C4` completo — porque `C` es letra válida y `4` es alfanumérico en ese contexto — produciendo `IDENTIFIER("C4")` en lugar de `NOTE("C4")`. Al poner `t_NOTE` primero con regex `[A-Ga-g][#b]?[0-9]`, PLY intenta ese patrón antes y lo captura correctamente. Esto implementa la **regla del lexema más largo con prioridad explícita**: le decimos explícitamente al AFD qué patrón tiene precedencia cuando hay ambigüedad.

---

### TRAMPA 3
**"Tu modo pánico en `_synchronize` usa un `set`. ¿Qué pasa si el token de sincronización nunca aparece? ¿El compilador se cuelga infinitamente?"**

**Respuesta:** No, está completamente controlado. El bucle tiene la condición `while not self._is_at_end()`. Si ningún token de sincronización aparece en el resto del archivo, `_is_at_end()` eventualmente devuelve `True` y el bucle termina. El parser llega al final del archivo limpiamente sin colgarse. Usé `set` en lugar de lista específicamente por eficiencia: la búsqueda en `set` es O(1) vs O(n) en lista, lo cual importa cuando el modo pánico puede invocarse múltiples veces en un archivo con varios errores. El único escenario de "silencio total" es cuando el error ocurre en la última sentencia del archivo — el parser consume todo y termina normalmente sin reportar errores adicionales.

---

### TRAMPA 4
**"¿Por qué el generador MIDI trabaja con tokens en lugar del AST que construiste?"**

**Respuesta:** Es una limitación arquitectónica del proyecto. El generador MIDI fue implementado de forma independiente operando directamente sobre tokens, lo que crea redundancia con el trabajo del parser. Lo correcto sería que `midi_gen.py` recibiera el AST y lo recorriera con el patrón Visitor — similar a cómo `generate_visual_tree` hace exactamente eso con Graphviz. En una versión mejorada, `tokens_to_midi` sería `ast_to_midi(ast)` que recorre el árbol jerárquico ya construido, eliminando el re-análisis de tokens y aprovechando toda la información estructural del AST.

---

### TRAMPA 5
**"La gramática de BeatScript, ¿es ambigua? ¿Cómo lo sabes?"**

**Respuesta:** No es ambigua. Lo sé porque el parser es **LL(1)** — en cada punto de decisión, hay exactamente un token hacia adelante que determina unívocamente qué regla aplicar. En `_parse_statement`, los tokens `TEMPO_KW`, `VOLUME_KW`, `INSTRUMENT_KW`, `TRACK_KW`, `CHORD_KW` y `REPEAT_KW` son todos distintos y no hay solapamiento — el parser siempre sabe sin ambigüedad qué método llamar. Lo mismo ocurre dentro de un track: `NOTE`, `REST`, `CHORD_KW` y `REPEAT_KW` son tokens mutuamente excluyentes como prefijos de evento. Si la gramática fuera ambigua, habría conflictos de este tipo: "con el token X, ¿aplico la regla A o la B?" — y no los hay.

---

## DEPENDENCIAS DEL PROYECTO

| Paquete | Instalación | Para qué se usa |
|---|---|---|
| `ply` | `pip install ply` | Motor del lexer (AFD + tokenización) |
| `customtkinter` | `pip install customtkinter` | GUI con modo oscuro |
| `pygame` | `pip install pygame` | Reproducción de archivos MIDI |
| `midiutil` | `pip install midiutil` | Escritura de archivos .mid |
| `graphviz` (Python) | `pip install graphviz` | Binding Python a dot.exe |
| Graphviz (binario) | graphviz.org/download | Renderiza el PNG del árbol |
| `difflib` | stdlib Python | Sugerencias de corrección (ya incluido) |

---

*Guía generada a partir del análisis completo del código fuente de BeatScript.*  
*Cubre: lexer.py, parser.py, midi_gen.py, main_gui.py, test_lexer.py, test_suggestions.py*
