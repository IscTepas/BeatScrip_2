# Cómo funciona BeatScript — visión general del compilador

Este documento explica cómo funciona el proyecto completo: la tubería (pipeline) de compilación, la estructura de archivos, y el análisis léxico y sintáctico a detalle. El análisis semántico se explica en profundidad en el documento aparte [`ANALISIS_SEMANTICO_RESUMEN.md`](ANALISIS_SEMANTICO_RESUMEN.md).

> Si vienes de Java: no hay máquina virtual ni bytecode aquí. La "salida" final del compilador es un archivo `.mid` (MIDI) que cualquier reproductor de audio puede tocar. El compilador traduce **texto → estructura → sonido**, en vez de **texto → bytecode → ejecución**.

---

## 1. Qué es BeatScript

BeatScript es un lenguaje de dominio específico (DSL) para composición musical. Un programa BeatScript se ve así:

```
tempo 120
volume 90
instrument piano

track melodia {
    C4 negra
    D4 negra
    E4 blanca
}

repeat 2 {
    G4 negra
    rest negra
}

chord {
    C4 E4 G4 blanca
}
```

El compilador toma ese texto y produce un archivo `.mid` reproducible.

---

## 2. La tubería de compilación (pipeline)

```
código fuente (.bs)
      │
      ▼
┌─────────────────┐
│  1. LÉXICO       │  lexer.py      texto → lista de tokens
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  2. SINTÁCTICO   │  parser.py     tokens → AST (árbol)
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  3. SEMÁNTICO    │  semantic.py   AST → errores/warnings + tabla de símbolos
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  4. GENERACIÓN   │  midi_gen.py   (ver nota abajo) → archivo .mid
└─────────────────┘
```

**Nota importante sobre la etapa 4:** en un compilador "de libro" (como el que verá tu profesor), después del análisis semántico vendría una etapa de **código intermedio** (ej. código de tres direcciones o cuádruplos) y luego la generación de código final a partir de esa representación intermedia. En este proyecto, `midi_gen.py` es un **atajo**: toma los *tokens crudos* directamente (ni siquiera usa el AST ni la tabla de símbolos) y genera el MIDI de un solo salto. Funciona, pero no es la ruta "textbook". Esa es la etapa que falta construir.

Cada etapa **no detiene** el programa si la anterior tuvo errores menores: el lexer sigue escaneando tras un carácter inválido, el parser sigue intentando parsear tras un error de sintaxis (modo pánico), y el semántico recorre todo el árbol acumulando todos los problemas de una vez. Esto es deliberado: en un IDE es mucho más útil mostrarle al usuario *todos* los errores juntos que detenerse en el primero.

---

## 3. Estructura de archivos

```
BeatScrip_2/
├── main_gui.py                 # IDE visual (Tkinter) — usa las 4 etapas para mostrar resultados
├── ejemplo_completo.bs         # Programa BeatScript de ejemplo
├── requirements.txt
├── README.md
└── beatscript/
    ├── lexer.py                # Etapa 1 — Análisis Léxico
    ├── parser.py                # Etapa 2 — Análisis Sintáctico (+ AST)
    ├── semantic.py              # Etapa 3 — Análisis Semántico
    ├── midi_gen.py               # Etapa 4 (atajo actual) — tokens → .mid
    └── tests/
        ├── test_lexer.py
        ├── test_parser.py
        ├── test_semantic.py
        ├── test_ast_visual.py
        └── test_suggestions.py
```

Cada módulo es **independiente y se puede usar por separado** — esto es importante para entender el diseño: `semantic.py` no sabe nada de MIDI, `parser.py` no sabe nada de análisis semántico, etc. Cada uno solo depende de los anteriores:

```
lexer.py  →  parser.py  →  semantic.py
                 │
                 └──(tokens, no AST)──→  midi_gen.py
```

---

## 4. Etapa 1 — Análisis Léxico (`lexer.py`)

### 4.1 Qué hace un analizador léxico

Un analizador léxico (o **lexer**, o **scanner**) lee el código fuente **carácter por carácter** y lo agrupa en unidades con significado llamadas **tokens**. Es el mismo trabajo que hace el tokenizer de cualquier lenguaje: convierte `"tempo 120"` (una cadena de 9 caracteres) en dos tokens: `TEMPO_KW` y `NUMBER(120)`.

Aquí se usa **PLY** (Python Lex-Yacc), una librería que construye el lexer automáticamente a partir de expresiones regulares — tú no escribes el autómata a mano, PLY lo genera. Es parecido a usar **JFlex o ANTLR** en Java: describes las reglas, la herramienta genera el reconocedor.

### 4.2 Los 13 tokens del lenguaje

| Token | Qué representa | Ejemplo |
|-------|-----------------|---------|
| `TEMPO_KW` | palabra clave `tempo` | `tempo 120` |
| `VOLUME_KW` | palabra clave `volume` | `volume 90` |
| `INSTRUMENT_KW` | palabra clave `instrument` | `instrument piano` |
| `TRACK_KW` | palabra clave `track` | `track melody {` |
| `REPEAT_KW` | palabra clave `repeat` | `repeat 2 {` |
| `CHORD_KW` | palabra clave `chord` | `chord {` |
| `REST` | silencio musical | `rest negra` |
| `NOTE` | nota musical | `C4`, `D#3`, `Eb5` |
| `DURATION` | duración de una nota | `negra`, `blanca` |
| `INSTR_NAME` | nombre de instrumento | `piano`, `violin` |
| `NUMBER` | número entero | `120`, `2` |
| `IDENTIFIER` | nombre libre (de track) | `melody`, `coro` |
| `LBRACE` / `RBRACE` | llaves `{` `}` | — |

### 4.3 Cómo decide el tipo de cada token

Esto es lo más importante de entender del lexer: **todas las palabras (keywords, instrumentos, nombres de track) pasan primero por la misma regla**, `t_IDENTIFIER` ([lexer.py:191](beatscript/lexer.py:191)), que acepta cualquier cosa con forma de identificador (`[a-zA-Z_][a-zA-Z0-9_]*`). Después de capturar el texto, consulta un diccionario llamado `RESERVED` ([lexer.py:45](beatscript/lexer.py:45)):

- Si la palabra está en `RESERVED` (ej. `"tempo"`, `"piano"`) → cambia el tipo de token al que indica el diccionario (`TEMPO_KW`, `INSTR_NAME`).
- Si no está (ej. `"melody"`) → se queda como `IDENTIFIER`.

Esto es el mismo truco que usan la mayoría de los lenguajes reales: no hay una regla separada por cada palabra clave, solo **una** regla de identificador + una tabla de búsqueda.

**Caso especial — las notas:** una nota como `C4` *también* calza con la regex de identificador (una letra seguida de un dígito). Por eso `t_NOTE` ([lexer.py:162](beatscript/lexer.py:162)) está definida **antes** que `t_IDENTIFIER` en el archivo: en PLY, cuando dos reglas-función podrían aplicar, gana la que aparece primero en el código. Si el orden fuera al revés, `C4` se leería como `IDENTIFIER` en vez de `NOTE`, y todo el resto del compilador se rompería.

### 4.4 Manejo de errores léxicos

Cuando aparece un carácter que ninguna regla reconoce (ej. `@`, `;`, `(`), PLY llama automáticamente a `t_error()` ([lexer.py:229](beatscript/lexer.py:229)). En vez de lanzar una excepción (como un `throw` en Java) y detener todo, ese carácter se:

1. Registra en una lista de errores (`error_list`), con línea, columna y un mensaje de ayuda específico (buscado en el diccionario `_ERROR_HINTS`, ej. para `(` sugiere usar `{` en su lugar).
2. Se descarta (`skip(1)`) y el escaneo **continúa** con el siguiente carácter.

Así, un programa con 5 errores léxicos distintos los reporta los 5 de una sola corrida, en vez de obligar al usuario a corregir uno, volver a compilar, ver el siguiente, etc.

### 4.5 Punto de entrada

`tokenize(source_code)` ([lexer.py:344](beatscript/lexer.py:344)) es la función pública: construye el lexer, le pasa el texto completo, y devuelve la lista de tokens (y opcionalmente la lista de errores). Es lo que llaman el parser y el resto del proyecto para obtener tokens a partir de código fuente.

---

## 5. Etapa 2 — Análisis Sintáctico (`parser.py`)

### 5.1 Qué hace un parser

El analizador sintáctico (**parser**) recibe la lista de tokens y comprueba que estén en un **orden válido** según la gramática del lenguaje, construyendo al mismo tiempo un **árbol de sintaxis abstracta (AST)**: una estructura de datos que representa el programa de forma jerárquica, lista para que las siguientes etapas la recorran.

La gramática de BeatScript, en notación EBNF (ver encabezado de [parser.py](beatscript/parser.py)):

```
programa    ::= (sentencia)*
sentencia   ::= tempo | volume | instrument | track | repeat | chord
tempo       ::= 'tempo' numero
volume      ::= 'volume' numero
instrument  ::= 'instrument' instr_name
track       ::= 'track' identificador '{' (evento)* '}'
chord       ::= 'chord' '{' NOTE+ DURATION '}'
evento      ::= nota duracion | rest duracion | chord | repeat numero '{' (evento)* '}'
```

### 5.2 Parser recursivo descendente

BeatScript usa un parser **recursivo descendente**: por cada regla de la gramática hay un método, y esos métodos se llaman entre sí siguiendo la estructura de la gramática. Por ejemplo, `_parse_track()` ([parser.py:403](beatscript/parser.py:403)) espera, en orden: la palabra `track`, un identificador, una `{`, y luego llama repetidamente a `_parse_event()` hasta encontrar `}`. Si estuvieras escribiendo esto a mano en Java, se vería casi igual: un método por regla, que consume tokens y llama a otros métodos.

Esto se diferencia de generadores de parser como **ANTLR o Yacc** (que BeatScript sí usa para el lexer, pero no para el parser): aquí el parser está escrito **a mano**, método por método, en vez de generado desde una gramática declarativa.

### 5.3 El "cursor" y los métodos de navegación

El parser guarda su posición actual en `self.pos` ([parser.py:179](beatscript/parser.py:179)) — como un índice que avanza por la lista de tokens, nunca retrocede. Los métodos de apoyo:

- `_current_token()` — mira el token en la posición actual sin moverse.
- `_check(tipo)` — pregunta "¿el token actual es de este tipo?" sin consumirlo.
- `_consume(tipo)` ([parser.py:250](beatscript/parser.py:250)) — el método más usado: si el token actual es del tipo esperado, lo consume (avanza `pos`) y lo devuelve; si no, genera un error sintáctico.
- `_advance()` — avanza el cursor una posición.

Casi todos los métodos `_parse_X()` son una secuencia de llamadas a `_consume()` en el orden que dicta la gramática.

### 5.4 El AST: los 9 tipos de nodo

Cada nodo es una clase simple que solo guarda datos (como un *record* o un POJO en Java), todas heredan de `ASTNode` ([parser.py:58](beatscript/parser.py:58)):

| Nodo | Representa | Datos que guarda |
|------|------------|-------------------|
| `Program` | la raíz del árbol | `statements` (lista de sentencias) |
| `Tempo` | `tempo N` | `bpm` |
| `Volume` | `volume N` | `level` |
| `Instrument` | `instrument NAME` | `name` |
| `Track` | `track NAME { ... }` | `name`, `events` |
| `Note` | nota + duración | `pitch`, `duration` |
| `Rest` | silencio | `duration` |
| `Chord` | acorde | `notes` (lista), `duration` |
| `Repeat` | `repeat N { ... }` | `count`, `events` |

Cada nodo también guarda su posición en el código (`line`, `col`) — esto es lo que luego usa `semantic.py` para que los mensajes de error apunten a la línea exacta.

### 5.5 Recuperación de errores — "Modo Pánico"

Si el parser encuentra algo inesperado (ej. `tempo abc` en vez de `tempo 120`), no se detiene: registra el error y llama a `_synchronize()` ([parser.py:222](beatscript/parser.py:222)), que **descarta tokens uno por uno** hasta encontrar un punto "seguro" para reanudar (por ejemplo, la siguiente palabra clave `track` o un `}`). Esto evita que un solo error de sintaxis genere una cascada de errores falsos derivados del primero, y permite seguir detectando más errores reales en el resto del archivo.

Además, si el token inesperado es un `IDENTIFIER` parecido a una palabra reservada (ej. el usuario escribió `temp 120` en vez de `tempo 120`), el parser usa `_get_suggestions_for_word()` ([parser.py:30](beatscript/parser.py:30)) — que compara con `difflib` (una utilidad de similitud de texto de la librería estándar de Python) — para sugerir: *"¿Quisiste decir 'tempo'?"*.

### 5.6 Ejemplo: de tokens a AST

Para el código:
```
tempo 120
track t {
    C4 negra
}
```

El AST resultante (de forma simplificada) sería:

```
Program
├── Tempo(120)
└── Track("t")
    └── Note("C4", "negra")
```

### 5.7 Funciones de visualización (no son parte de la lógica del compilador)

Al final de `parser.py` hay tres funciones que **no participan en la compilación**, solo sirven para que el IDE pueda *mostrar* el árbol de formas distintas:

- `ast_to_table_rows()` ([parser.py:585](beatscript/parser.py:585)) — convierte el AST en filas para una tabla (Treeview de Tkinter).
- `ast_to_tree_string()` ([parser.py:640](beatscript/parser.py:640)) — genera un árbol en texto estilo `├──`/`└──` (como el comando `tree` de una terminal).
- `generate_visual_tree()` ([parser.py:716](beatscript/parser.py:716)) — genera una imagen PNG del árbol usando Graphviz, ideal para incluir en la presentación al profesor.

---

## 6. Etapa 3 — Análisis Semántico (`semantic.py`)

Resumen rápido (el detalle completo está en [`ANALISIS_SEMANTICO_RESUMEN.md`](ANALISIS_SEMANTICO_RESUMEN.md)): el parser solo valida la *forma* del programa; `semantic.py` valida el *significado* — por ejemplo que `tempo` esté entre 20 y 400 BPM, que no haya dos tracks con el mismo nombre, o que una nota no se salga del rango MIDI permitido (0-127). Recorre el AST ya construido (no los tokens) usando el patrón **visitor**, y construye una **tabla de símbolos** con los tracks declarados.

---

## 7. Etapa 4 (atajo actual) — Generación de MIDI (`midi_gen.py`)

Como se explicó en la sección 2, esta etapa **no sigue la ruta de un compilador clásico**: en vez de generar el `.mid` a partir del AST validado (o de una representación intermedia), toma la lista de tokens cruda y la recorre con un índice manual, manteniendo un "reloj" (`t`, tiempo acumulado en beats) que avanza con cada nota o silencio.

- `note_to_midi()` ([midi_gen.py:87](beatscript/midi_gen.py:87)) convierte `"C4"` → `60` con la fórmula estándar MIDI.
- `_collect_block()` ([midi_gen.py:120](beatscript/midi_gen.py:120)) extrae el contenido entre `{` y `}`, contando llaves para soportar bloques anidados (ej. `repeat` dentro de `track`).
- `tokens_to_midi()` ([midi_gen.py:145](beatscript/midi_gen.py:145)) recorre el programa completo y escribe cada nota en un objeto `MIDIFile` (de la librería `midiutil`), que al final se guarda a disco como `.mid`.

Esta es la pieza que, en teoría, debería reemplazarse (o complementarse) con un generador que lea desde una representación de código intermedio construida a partir del AST + tabla de símbolos — ese es el trabajo pendiente del proyecto.

---

## 8. Cómo correr el proyecto

```bash
# Instalar dependencias
pip install -r requirements.txt

# Abrir el IDE visual
python main_gui.py

# Probar solo el lexer desde consola
python -X utf8 beatscript/lexer.py

# Correr las pruebas
python -m pytest beatscript/tests/ -v
```
