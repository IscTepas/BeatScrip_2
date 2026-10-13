# Cómo funciona BeatScript — guía completa del compilador

Este documento explica, con el código al lado de cada explicación, cómo funciona **todo** el proyecto: la tubería de compilación completa, la estructura de archivos, y el análisis léxico y sintáctico **línea por línea**. El análisis semántico se explica con el mismo nivel de detalle en el documento aparte [`ANALISIS_SEMANTICO.md`](ANALISIS_SEMANTICO.md) (es demasiado extenso para repetirlo aquí sin duplicar contenido).

> **Cómo leer este documento si vienes de Java:** cada vez que aparezca algo raro de la sintaxis de Python, lo aclaro entre paréntesis con su equivalente en Java. Dos cosas que vas a ver todo el tiempo:
> - `self` = `this`.
> - Una función definida con `def nombre(self, ...):` dentro de una clase = un método de instancia, igual que en Java.
> - Un comentario de una sola línea `# algo` = igual que `// algo` en Java.
> - Un comentario de varias líneas entre `"""..."""` justo debajo de un `def` es especial en Python: se llama **docstring** y es la forma "oficial" de documentar qué hace una función (no es solo un comentario cualquiera, herramientas como `help()` lo leen).

---

## 1. Qué es BeatScript

BeatScript es un **DSL** (*Domain-Specific Language*, lenguaje de dominio específico) para composición musical: un lenguaje pequeño, hecho a medida para un solo propósito (describir música), no para programar de forma general como Java o Python.

Ejemplo de programa BeatScript completo:

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

El compilador recibe este texto y, al final de la tubería, produce un archivo `.mid` (MIDI) reproducible en cualquier reproductor de audio.

---

## 2. La tubería de compilación (pipeline) completa

```
código fuente (.bs)
      │
      ▼
┌──────────────────────┐
│ 1. LÉXICO             │  lexer.py       texto plano → lista de tokens
└──────────────────────┘
      │  lista de objetos LexToken (type, value, lineno, lexpos)
      ▼
┌──────────────────────┐
│ 2. SINTÁCTICO         │  parser.py      tokens → AST (árbol)
└──────────────────────┘
      │  objeto Program (raíz del árbol)
      ▼
┌──────────────────────┐
│ 3. SEMÁNTICO          │  semantic.py    AST → errores/warnings + tabla de símbolos
└──────────────────────┘
      │  (ver ANALISIS_SEMANTICO.md para el detalle completo de esta etapa)
      ▼
┌──────────────────────┐
│ 4. GENERACIÓN MIDI    │  midi_gen.py    (ruta real actual, ver nota) → archivo .mid
└──────────────────────┘
```

### Nota importante sobre la etapa 4 — lo que falta en el proyecto

En un compilador "de libro de texto" (el que tu profesor espera ver), después del análisis semántico vendría una etapa de **generación de código intermedio** (por ejemplo código de tres direcciones, o una lista de cuádruplos) y *luego*, a partir de esa representación intermedia, la generación del código final. Diagrama de cómo "debería" ser:

```
AST + tabla de símbolos  →  [FALTA: código intermedio]  →  código final (.mid)
```

En este proyecto **esa pieza de código intermedio todavía no existe**. Lo que hay hoy es un atajo: `midi_gen.py` genera el `.mid` directamente desde los **tokens crudos** (ni siquiera recibe el AST ni la tabla de símbolos):

```
tokens (de la etapa 1, sin pasar por el AST)  →  midi_gen.py  →  código final (.mid)
```

Esto funciona y produce música correcta, pero **salta** las etapas intermedias que un compilador real encadenaría. Es la pieza pendiente de construir.

### Por qué cada etapa sigue aunque haya errores

Ninguna etapa se detiene ante el primer error que encuentra:

- El **lexer** sigue escaneando después de un carácter inválido (lo salta con `skip(1)` y continúa).
- El **parser** sigue intentando parsear después de un error de sintaxis ("modo pánico": descarta tokens hasta un punto seguro y continúa).
- El **semántico** recorre el árbol completo acumulando *todos* los problemas antes de terminar.

Esto es deliberado: en un IDE es mucho más útil mostrarle al usuario todos sus errores de una vez que obligarlo a corregir uno, volver a compilar, ver el siguiente, y así sucesivamente.

---

## 3. Estructura de archivos del proyecto

```
BeatScrip_2/
├── main_gui.py                 # IDE visual (Tkinter) — usa las 4 etapas para mostrar resultados
├── ejemplo_completo.bs         # Programa BeatScript de ejemplo, usado también en los tests
├── requirements.txt
├── README.md
├── COMO_FUNCIONA_EL_PROYECTO.md    # este documento
├── ANALISIS_SEMANTICO.md           # detalle de la fase 3
└── beatscript/
    ├── __init__.py
    ├── lexer.py                # Etapa 1 — Análisis Léxico
    ├── parser.py                # Etapa 2 — Análisis Sintáctico (+ definición del AST)
    ├── semantic.py              # Etapa 3 — Análisis Semántico
    ├── midi_gen.py               # Etapa 4 (atajo actual) — tokens → .mid
    └── tests/
        ├── test_lexer.py
        ├── test_parser.py
        ├── test_semantic.py
        ├── test_ast_visual.py
        └── test_suggestions.py
```

### Dependencias entre módulos

Cada módulo solo depende de los anteriores en la tubería — esto es importante porque muestra que el diseño respeta la separación de etapas de un compilador real:

```
lexer.py  →  parser.py  →  semantic.py      (ruta "correcta" de un compilador)
     │
     └────────(tokens, SIN pasar por el AST)────────→  midi_gen.py   (atajo actual)
```

`semantic.py` importa de `parser.py` las clases de nodo del AST (`Program`, `Tempo`, etc.) porque necesita reconocerlas con `isinstance()`. `midi_gen.py`, en cambio, **no importa nada de `parser.py` ni de `semantic.py`** — solo necesita la lista de tokens que produce `lexer.py`. Eso es justamente lo que confirma que la generación MIDI actual no pasa por el AST.

---

## 4. Etapa 1 — Análisis Léxico (`beatscript/lexer.py`)

### 4.1 Qué hace un analizador léxico

Un **lexer** (o *scanner*, o analizador léxico) lee el código fuente **carácter por carácter** y lo agrupa en unidades con significado llamadas **tokens**. Por ejemplo, el texto `"tempo 120"` (9 caracteres sueltos) se agrupa en 2 tokens: uno de tipo `TEMPO_KW` y uno de tipo `NUMBER` con valor `120`.

Este proyecto usa **PLY** (*Python Lex-Yacc*), una librería que construye automáticamente el reconocedor (el autómata) a partir de un conjunto de reglas con expresiones regulares — tú no escribes el autómata a mano, PLY lo genera por ti. Es el mismo rol que cumple **JFlex** o **ANTLR** (en su parte léxica) si has usado algo así en Java: describes las reglas con regex, la herramienta construye el reconocedor.

```python
import ply.lex as lex
```

Esta línea importa el módulo `lex` de PLY. Todo el resto del archivo son variables y funciones que PLY va a **inspeccionar automáticamente** (por reflexión, buscando nombres con el patrón `t_ALGO`) para construir el lexer — tú nunca llamas a estas funciones directamente, PLY lo hace por ti cuando corresponda.

### 4.2 El diccionario de palabras reservadas — `RESERVED`

```python
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
    # ... (más instrumentos, mismo patrón)
}
```

Esto es un `dict[str, str]` — en Java sería un `HashMap<String, String>`. La anotación `dict[str, str]` es solo información de tipos para quien lea el código (un *type hint*); Python **no obliga** a que sea así en tiempo de ejecución, a diferencia de Java donde los genéricos sí se comprueban en compilación. Es documentación, no una regla forzada.

La idea clave: **todas** las palabras (comandos, duraciones, instrumentos) se guardan aquí mapeadas a su tipo de token real. Esto permite que una sola regla léxica (la de identificadores, que ves en la sección 4.5) reconozca cualquier palabra, y que después se consulte este diccionario para saber de qué tipo es en realidad.

### 4.3 La lista obligatoria `tokens`

```python
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
```

Esto es una **tupla** (en Python, una lista inmutable — no se puede modificar después de creada, a diferencia de una lista normal `[...]`). PLY **exige** que exista una variable llamada exactamente `tokens` con todos los tipos de token posibles; si una regla produce un tipo que no está aquí, PLY lanza un error al construir el lexer. Es el equivalente a declarar de antemano "estos son todos los tipos de token que puede haber", como una enumeración (`enum`) en Java.

### 4.4 Orden de prioridad de las reglas en PLY

PLY aplica las reglas en este orden:
1. **Funciones** (`def t_NOMBRE(t): ...`): se prueban en el orden en que aparecen escritas en el archivo. La primera definida gana si varias podrían aplicar.
2. **Strings** (`t_NOMBRE = r"..."`): se ordenan por longitud de la expresión regular — la más larga tiene prioridad.

Esto es **crítico** para entender por qué `t_NOTE` está definida antes que `t_IDENTIFIER` en el archivo (lo vas a ver en la sección 4.6).

### 4.5 Tokens de un solo carácter

```python
t_LBRACE = r"\{"
t_RBRACE = r"\}"
```

Estas son "reglas-string": como no necesitan lógica adicional (no hay nada que calcular, solo reconocer el carácter), se definen directamente como una variable con el patrón regex, en vez de una función completa. El `\` antes de `{` y `}` es necesario porque en una expresión regular esos caracteres normalmente tienen un significado especial (inician un cuantificador, como en `a{2,3}`); el `\` le dice a la regex "trátalo como el carácter literal, no como sintaxis de regex".

### 4.6 La regla de las notas musicales — `t_NOTE`

```python
def t_NOTE(t):
    r"[A-Ga-g][#b]?[0-9]+"
    # Normaliza a mayúsculas para que c4, C4 y C4 sean equivalentes
    # y el resto del pipeline trabaje con un formato uniforme.
    t.value = t.value.upper()   # c4 → C4, eb3 → EB3
    return t
```

Aquí pasan varias cosas que es importante notar:

- El **docstring** `r"[A-Ga-g][#b]?[0-9]+"` (la cadena justo debajo del `def`) **no es un comentario normal que PLY ignore**: PLY lo lee específicamente como la expresión regular de esta regla. Esta es una particularidad de cómo funciona PLY, no de Python en general — en cualquier otra función de Python, ese docstring sería solo documentación.
- La regex dice: una letra A-G (mayúscula o minúscula), opcionalmente seguida de `#` o `b` (alteración), seguida de uno o más dígitos (la octava). Ejemplos que acepta: `C4`, `D#3`, `eb5`, `G0`.
- `t` es el objeto *token* que PLY le pasa a la función — tiene atributos como `t.value` (el texto reconocido), `t.type` (el nombre del token, aquí `"NOTE"` automáticamente por el nombre de la función `t_NOTE`), `t.lineno` (línea).
- `t.value = t.value.upper()` normaliza el texto a mayúsculas, para que `c4`, `C4` sean tratados exactamente igual por el resto del compilador (así ni el parser ni el semántico necesitan preocuparse por mayúsculas/minúsculas en las notas).
- `return t` — PLY requiere que la función devuelva el token para que se agregue a la salida. Si una función **no** devuelve nada (como vas a ver en `t_COMMENT`), ese lexema se descarta sin generar token.

**¿Por qué esta función está definida *antes* de `t_IDENTIFIER` en el archivo?** Porque la regex de identificador (`[a-zA-Z_][a-zA-Z0-9_]*`) *también* coincide con `"C4"` (una letra seguida de un dígito es un identificador válido). Como PLY da prioridad a la función definida primero, `t_NOTE` "gana" la carrera y `C4` se reconoce como nota, no como identificador. Si el orden estuviera invertido, todo el análisis de notas musicales se rompería.

### 4.7 La regla de números — `t_NUMBER`

```python
def t_NUMBER(t):
    r"[0-9]+"
    # Convierte el string a entero para que el parser y el generador MIDI
    # operen directamente con el valor numérico sin conversiones adicionales.
    t.value = int(t.value)
    return t
```

La regex `[0-9]+` acepta uno o más dígitos. Lo interesante es `t.value = int(t.value)`: por defecto, `t.value` llega como el texto crudo (`"120"`, un `str`), y aquí se convierte a entero (`120`, un `int`) — como harías con `Integer.parseInt(...)` en Java. Esto significa que, desde este punto en adelante, todo el pipeline recibe `t.value` ya como número, sin tener que volver a convertirlo en cada etapa siguiente.

### 4.8 La regla de identificadores y palabras reservadas — `t_IDENTIFIER`

```python
def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    # Consulta el diccionario RESERVED en minúsculas para ser case-insensitive:
    # "TEMPO", "Tempo" y "tempo" se tratan igual.
    # Si la palabra está en RESERVED → cambia el tipo al tipo correspondiente.
    # Si no está → queda como IDENTIFIER (nombre libre del usuario).
    token_type = RESERVED.get(t.value.lower(), "IDENTIFIER")
    t.type  = token_type
    t.value = t.value.lower() if token_type != "IDENTIFIER" else t.value
    return t
```

Este es, probablemente, el método más importante para entender *el diseño* del lexer. La regex acepta cualquier palabra que empiece con letra o `_`, seguida de letras, dígitos o `_` — el patrón típico de un identificador en casi cualquier lenguaje.

Lo que hace después de capturar el texto es la parte clave:

1. `RESERVED.get(t.value.lower(), "IDENTIFIER")` — es como un `map.getOrDefault(clave, valorPorDefecto)` en Java: busca la palabra (en minúsculas, para no distinguir mayúsculas/minúsculas) dentro del diccionario `RESERVED`. Si la encuentra (ej. `"tempo"` → `"TEMPO_KW"`), usa ese tipo. Si no la encuentra (ej. `"melody"`, un nombre inventado por el usuario), usa `"IDENTIFIER"` como valor por defecto.
2. `t.type = token_type` — cambia el tipo del token. Esto es lo que permite que una **sola** regla reconozca tanto palabras clave (`tempo`), nombres de instrumento (`piano`) como nombres libres (`melody`) — no hay una regla separada por cada palabra reservada.
3. La última línea decide cómo guardar el valor: si es una palabra reservada, se guarda en minúsculas (para uniformidad); si es un identificador libre del usuario, se conserva **tal cual lo escribió** (para no cambiarle el nombre a su variable).

### 4.9 Comentarios — `t_COMMENT`

```python
def t_COMMENT(t):
    r"\#[^\n]*"
    # Los comentarios no generan token: la función no retorna nada,
    # por lo que PLY descarta el lexema silenciosamente.
    pass
```

La regex `\#[^\n]*` reconoce un `#` seguido de cualquier cantidad de caracteres que **no** sean salto de línea (es decir, todo hasta el final de la línea). Como la función **no tiene `return`** (el `pass` es solo "no hacer nada", equivalente a un bloque vacío `{}` en Java), PLY entiende que este lexema no debe convertirse en ningún token — simplemente se descarta.

### 4.10 Saltos de línea — `t_newline`

```python
def t_newline(t):
    r"\n+"
    # Incrementa el contador de líneas en tantas unidades como saltos haya.
    # No retorna token → el salto de línea se descarta pero lineno queda actualizado
    # para que los mensajes de error indiquen la línea correcta.
    t.lexer.lineno += len(t.value)
```

Igual que los comentarios, los saltos de línea no generan token (tampoco hay `return`), pero antes de descartarlos, esta función actualiza `t.lexer.lineno` (el contador de línea actual del lexer) sumando cuántos saltos de línea hubo de una vez (`t.value` puede ser `"\n"` o `"\n\n\n"` si hay líneas vacías seguidas). Sin esto, **todos** los mensajes de error reportarían siempre "línea 1", porque nada estaría llevando la cuenta.

### 4.11 Caracteres ignorados — `t_ignore`

```python
t_ignore = " \t\r"
```

Esta variable especial le dice a PLY: "estos caracteres (espacio, tabulador, retorno de carro) sáltalos sin generar token **ni** llamar a `t_error`". Es distinto de los comentarios o los saltos de línea: aquí ni siquiera se ejecuta una función, PLY los descarta directamente a nivel del motor de reconocimiento.

### 4.12 Manejo de errores léxicos — `t_error`

```python
def t_error(t):
    col  = _find_column(t.lexer.lexdata, t)
    char = t.value[0]
    msg  = _build_error_msg(char, t.lineno, col)
    if hasattr(t.lexer, "error_list"):
        t.lexer.error_list.append({"line": t.lineno, "col": col, "char": char, "msg": msg})
    else:
        print(msg)
    t.lexer.skip(1)  # Salta el carácter inválido y continúa el escaneo
```

PLY llama **automáticamente** a esta función (su nombre es especial/reservado, como `t_error`) cuando ningún patrón de ninguna regla coincide con el carácter actual — por ejemplo, si el usuario escribe `@`, `;`, o `(`, que no forman parte de ninguna regla válida de BeatScript.

Paso a paso:
1. `_find_column(...)` calcula en qué columna de su línea está el carácter problemático (ver sección 4.14).
2. `char = t.value[0]` toma el primer carácter del lexema inválido (en Python, indexar un string con `[0]` da el primer carácter, como `str.charAt(0)` en Java).
3. `_build_error_msg(...)` construye el mensaje de error completo con una sugerencia específica (ver sección 4.13).
4. `hasattr(t.lexer, "error_list")` — comprueba **en tiempo de ejecución** si el objeto `lexer` tiene un atributo llamado `error_list` (esto es *duck typing*: Python no necesita que la clase declare ese atributo de antemano, solo revisa si existe en este objeto en particular). Si existe (porque `tokenize()` lo agregó, ver sección 4.16), el error se **acumula** en esa lista en vez de imprimirse — esto es lo que permite seguir escaneando y reportar todos los errores juntos al final. Si no existe (por ejemplo, corriendo el lexer "a mano" sin pasar por `tokenize()`), simplemente lo imprime en consola.
5. `t.lexer.skip(1)` — avanza el lexer un carácter (salta el carácter inválido) para que el escaneo **continúe** en vez de detenerse. Sin esto, PLY se quedaría atascado intentando reconocer el mismo carácter inválido para siempre.

### 4.13 Mensajes de ayuda por carácter — `_ERROR_HINTS` y `_build_error_msg`

```python
_ERROR_HINTS: dict[str, str] = {
    "@":  "El símbolo '@' no pertenece al alfabeto de BeatScript.",
    "!":  "El operador '!' no existe en BeatScript.",
    "*":  "Para repetir bloques usa: repeat N { ... }",
    "(":  "Paréntesis no válido — los bloques se delimitan con { }",
    ")":  "Paréntesis no válido — los bloques se delimitan con { }",
    ";":  "El ';' no es necesario — cada instrucción va en su propia línea.",
    ",":  "Separa notas con espacios, no con comas: C4 E4 G4 blanca",
    # ... (hay más entradas, cubre los símbolos típicos que alguien
    #      que viene de otro lenguaje intentaría usar por costumbre)
}


def _build_error_msg(char: str, line: int, col: int) -> str:
    hint = _ERROR_HINTS.get(char, f"'{char}' no pertenece al alfabeto de BeatScript.")
    return f"[ERROR LÉXICO] Línea {line}, Col {col}: carácter '{char}' no reconocido — {hint}"
```

`_ERROR_HINTS` es otro `HashMap<String,String>`, pero esta vez pensado específicamente en errores comunes de alguien que viene de otro lenguaje de programación: por ejemplo, alguien acostumbrado a C/Java podría intentar escribir `;` al final de una línea (aquí no existe) o paréntesis `( )` en vez de llaves `{ }`. En vez de un mensaje genérico, cada símbolo tiene una sugerencia concreta de qué hacer en su lugar.

`_build_error_msg` arma el texto final: busca el símbolo en `_ERROR_HINTS` (con `.get(char, valor_por_defecto)`, igual patrón que antes); si no está ahí, usa un mensaje genérico ("no pertenece al alfabeto"). El `f"..."` es un **f-string** de Python — el equivalente a `String.format(...)` o a la concatenación con `+` en Java, pero con las variables insertadas directamente dentro de `{ }` dentro del propio string.

### 4.14 Calcular la columna de un token — `_find_column`

```python
def _find_column(source: str, token) -> int:
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

`token.lexpos` es la posición **absoluta** del token dentro de todo el texto fuente (contando desde el carácter 0 del archivo completo, sin reiniciar por línea). Para convertir eso en "columna dentro de su línea":

1. `source.rfind("\n", 0, token.lexpos)` busca el **último** salto de línea que aparece *antes* de la posición del token (buscando hacia atrás, de ahí el nombre `rfind`, "reverse find" — como `String.lastIndexOf` en Java, pero limitado a buscar solo en la porción `[0, token.lexpos)`). Si no hay ningún salto de línea antes (el token está en la primera línea), `rfind` devuelve `-1`.
2. `+ 1` ajusta esa posición para que apunte al **primer carácter de la línea actual** (justo después del `\n`, o `0` si no había ninguno antes).
3. `token.lexpos - line_start + 1` es la distancia entre el inicio de la línea y la posición del token, +1 porque las columnas se cuentan desde 1 (no desde 0) para que coincida con lo que vería un humano contando caracteres en un editor de texto.

### 4.15 Construir el lexer — `build_lexer`

```python
def build_lexer() -> lex.Lexer:
    return lex.lex()
```

`lex.lex()` es la función de PLY que hace la magia: inspecciona **todo el módulo actual** buscando variables y funciones que sigan el patrón `t_NOMBRE`, compila cada regla en una expresión regular, y construye un único autómata combinado (AFD) a partir de todas ellas. El resultado es un objeto `Lexer` listo para recibir texto.

### 4.16 El punto de entrada público — `tokenize`

```python
def tokenize(source_code: str, *, debug: bool = False, collect_errors: bool = False):
    errors = []
    lx = build_lexer()
    lx.error_list = errors   # t_error acumula aquí en vez de imprimir
    lx.input(source_code)

    result = list(lx)        # Materializa el generador — escanea todo el código

    if debug:
        _print_token_table(result, source_code)

    if collect_errors:
        return result, errors
    return result
```

Esta es la función que llaman el parser y el resto del proyecto. Paso a paso:

1. `errors = []` — una lista vacía donde se van a acumular los errores léxicos.
2. `lx = build_lexer()` — construye un lexer nuevo.
3. `lx.error_list = errors` — **esto es la pieza clave**: Python permite agregar un atributo nuevo a un objeto en cualquier momento (a diferencia de Java, donde los campos de una clase están fijos desde su definición). Al asignar `lx.error_list = errors`, el objeto `lx` ahora **tiene** ese atributo, y por eso el `hasattr(t.lexer, "error_list")` de `t_error()` (sección 4.12) lo encuentra y acumula ahí en vez de imprimir.
4. `lx.input(source_code)` — le pasa el texto fuente completo al lexer.
5. `result = list(lx)` — PLY entrega los tokens como un **generador** (produce uno a la vez, de forma perezosa, como un `Iterator` en Java); `list(lx)` fuerza a consumirlos todos de inmediato y los junta en una lista normal. Es en este momento exacto donde ocurre todo el escaneo real.
6. `*, debug: bool = False, collect_errors: bool = False` en la firma de la función — el `*` fuerza a que `debug` y `collect_errors` solo puedan pasarse **por nombre** (`tokenize(codigo, debug=True)`), nunca por posición. Esto es una característica propia de Python (*keyword-only arguments*); en Java no existe un equivalente directo, sería como forzar a usar parámetros nombrados tipo builder.
7. Según `collect_errors`, la función devuelve solo la lista de tokens, o una tupla `(tokens, errores)`.

---

## 5. Etapa 2 — Análisis Sintáctico (`beatscript/parser.py`)

### 5.1 Qué hace un parser y la gramática de BeatScript

El **parser** recibe la lista de tokens y comprueba que estén en un orden válido según la gramática del lenguaje, construyendo al mismo tiempo el **AST** (árbol de sintaxis abstracta): una estructura jerárquica que representa el programa, lista para que las siguientes etapas la recorran sin tener que volver a mirar el texto original.

Gramática completa, en notación EBNF (tal como aparece al inicio de [parser.py](beatscript/parser.py)):

```
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
```

Leer esto: el `*` significa "cero o más repeticiones" (como `*` en una regex), el `|` significa "o" (una alternativa entre varias opciones), y las comillas simples marcan texto literal (tokens concretos). Por ejemplo, la regla `track ::= 'track' identificador '{' (evento)* '}'` dice: la palabra `track`, seguida de un identificador, seguida de `{`, seguida de cero o más eventos, seguida de `}`.

### 5.2 Parser recursivo descendente — la idea general

BeatScript usa un parser **recursivo descendente**, escrito **a mano** (sin generador como ANTLR/Yacc para esta parte — PLY sí se usó, pero solo para el lexer). La idea: **por cada regla de la gramática hay un método**, y esos métodos se llaman entre sí siguiendo exactamente la estructura de la gramática. Por ejemplo, para la regla `track`, existe un método `_parse_track()` que, en orden, consume la palabra `track`, consume un identificador, consume `{`, llama repetidamente a `_parse_event()` hasta encontrar `}`, y consume el `}`.

Si estuvieras escribiendo este mismo parser a mano en Java, se vería prácticamente igual: una clase con un método por regla gramatical, cada uno llamando a los demás.

### 5.3 Sugerencias de palabras parecidas — `_get_suggestions_for_word`

```python
def _get_suggestions_for_word(word, keywords_dict=None, cutoff=0.6, max_suggestions=3):
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
```

Esta función usa `difflib` (parte de la librería estándar de Python, no hay que instalarla aparte) para encontrar palabras **parecidas** a una palabra escrita por el usuario, comparándola contra todas las claves de `RESERVED` (importado desde el lexer: `from beatscript.lexer import RESERVED`). `cutoff` es el umbral de similitud mínima (0.0 a 1.0; 0.6 significa "al menos 60% parecida"). Se usa, por ejemplo, cuando el usuario escribe `temp 120` en vez de `tempo 120`: `_get_suggestions_for_word("temp")` encontraría `"tempo"` como sugerencia.

### 5.4 Las clases del AST — una por una, con su código

Todas heredan de una clase base común:

```python
class ASTNode:
    """Clase base para todos los nodos del árbol sintáctico."""
    line = col = None
    arg_line = arg_col = None
    def __repr__(self):
        return f"<{self.__class__.__name__}>"
```

`line = col = None` es una forma compacta de Python de escribir "estas dos variables empiezan en `None`" (equivalente a declarar `line` y `col` como campos de la clase con valor inicial `null`). `arg_line`/`arg_col` son la posición del **argumento** del nodo (ej. el número de un `tempo`), separada de `line`/`col` que es la posición de la palabra clave — esto permite que los mensajes de error del análisis semántico señalen exactamente el número que está mal, no la palabra `tempo`.

`__repr__` es un método especial de Python (empieza y termina con `__`, se llama *dunder method*, de "double underscore") que define cómo se ve el objeto cuando lo imprimes o lo inspeccionas — es el equivalente a sobreescribir `toString()` en Java.

```python
class Program(ASTNode):
    """Nodo raíz del programa."""
    def __init__(self):
        self.statements = []  # Lista de sentencias globales
```

El nodo raíz de todo el árbol. `__init__` es el constructor (equivalente al constructor de una clase en Java, pero siempre se llama exactamente `__init__`, nunca como la clase). `self.statements = []` crea una lista vacía como atributo de instancia — como `List<ASTNode> statements = new ArrayList<>();` en Java.

```python
class Tempo(ASTNode):
    """Sentencia: tempo <número>"""
    def __init__(self, bpm):
        self.bpm = bpm

    def __repr__(self):
        return f"Tempo({self.bpm})"
```

```python
class Volume(ASTNode):
    """Sentencia: volume <número>"""
    def __init__(self, level):
        self.level = level

    def __repr__(self):
        return f"Volume({self.level})"
```

```python
class Instrument(ASTNode):
    """Sentencia: instrument <nombre>"""
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Instrument({self.name})"
```

Estos tres son casi idénticos en estructura: guardan un único dato relevante (`bpm`, `level`, `name`) y definen cómo se representan como texto.

```python
class Track(ASTNode):
    """Sentencia: track <nombre> { eventos }"""
    def __init__(self, name, events):
        self.name = name
        self.events = events  # Lista de Note, Rest, Chord, Repeat

    def __repr__(self):
        return f"Track({self.name})"
```

`Track` guarda su nombre y una **lista** de eventos — aquí es donde el árbol empieza a tener profundidad real: un `Track` no es una hoja, tiene hijos.

```python
class Note(ASTNode):
    """Evento: <nota> <duración>"""
    def __init__(self, pitch, duration):
        self.pitch = pitch      # "C4", "D#3", "Eb5", etc.
        self.duration = duration  # "negra", "blanca", etc.

    def __repr__(self):
        return f"Note({self.pitch} {self.duration})"
```

```python
class Rest(ASTNode):
    """Evento: rest <duración>"""
    def __init__(self, duration):
        self.duration = duration

    def __repr__(self):
        return f"Rest({self.duration})"
```

```python
class Chord(ASTNode):
    """
    Sentencia/Evento: chord { NOTE+ DURATION }
    Representa un acorde: varias notas tocadas simultáneamente
    con una duración compartida al final del bloque.
    """
    def __init__(self, notes, duration):
        self.notes = notes        # Lista de strings de pitch ["C4", "E4", "G4"]
        self.duration = duration  # Duración compartida: "blanca", "negra", etc.

    def __repr__(self):
        return f"Chord({'+'.join(self.notes)} {self.duration})"
```

`'+'.join(self.notes)` es el equivalente a `String.join("+", notes)` en Java: convierte la lista `["C4", "E4", "G4"]` en el texto `"C4+E4+G4"`.

```python
class Repeat(ASTNode):
    """Evento/Sentencia: repeat <número> { eventos }"""
    def __init__(self, count, events):
        self.count = count
        self.events = events  # Lista de eventos o sentencias a repetir

    def __repr__(self):
        return f"Repeat({self.count})"
```

### 5.5 La clase principal del parser — `BeatScriptParser.__init__`

```python
class BeatScriptParser:
    """Parser que convierte tokens en un árbol sintáctico (AST)."""

    def __init__(self, tokens, source_code=""):
        self.tokens = tokens
        self.source_code = source_code  # Necesario para calcular columnas
        self.pos = 0        # Posición actual en la lista de tokens
        self.errors = []    # Errores de sintaxis encontrados
```

`self.pos = 0` es el **cursor**: un índice que indica en qué posición de la lista `self.tokens` está actualmente el parser. A diferencia del lexer (que avanza carácter por carácter sobre el texto), el parser avanza token por token sobre la lista ya tokenizada, y **nunca retrocede** — solo avanza hacia adelante.

### 5.6 Calcular columnas — `_get_column` y `_at`

```python
def _get_column(self, token):
    """
    Calcula la columna (1-indexada) del token dentro de su línea.
    Retorna '?' si no hay código fuente disponible.
    """
    if not self.source_code or not hasattr(token, "lexpos"):
        return "?"
    line_start = self.source_code.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

Es exactamente la misma lógica que `_find_column` del lexer (sección 4.14), repetida aquí porque el parser necesita calcular columnas de forma independiente (no tiene acceso directo al lexer original, solo a la lista de tokens y al texto fuente).

```python
def _at(self, node, token, arg_token=None):
    """Guarda en el nodo la posición (línea/columna) de sus tokens."""
    if token is not None:
        node.line, node.col = token.lineno, self._get_column(token)
    if arg_token is not None:
        node.arg_line, node.arg_col = arg_token.lineno, self._get_column(arg_token)
    return node
```

Este método pequeño se usa **constantemente** en los métodos `_parse_X()`: después de construir un nodo nuevo, le "estampa" su posición en el código fuente. `node.line, node.col = token.lineno, self._get_column(token)` es una asignación múltiple de Python (asigna dos valores a la vez, como una desestructuración) — el equivalente más cercano en Java sería asignar dos campos en dos líneas separadas.

### 5.7 Métodos de navegación por los tokens

```python
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
```

Estos cinco métodos son los "sentidos" del parser:
- `_current_token()` — mira el token en la posición actual, **sin moverse** (como `peek()` en muchas implementaciones de pila/cola).
- `_peek_token(offset)` — mira *más adelante* sin moverse, útil cuando hace falta decidir algo mirando dos tokens a la vez.
- `_advance()` — mueve el cursor una posición hacia adelante (y solo si no se ha llegado al final).
- `_is_at_end()` — pregunta si ya no quedan tokens.
- `_check(tipo)` — pregunta "¿el token actual es de este tipo?" sin consumirlo (no avanza el cursor). Se usa todo el tiempo para decidir qué regla de la gramática aplicar, antes de comprometerse a consumir nada.

### 5.8 Consumir un token — `_consume`

```python
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
        self._add_error(f"Fin de archivo inesperado — {error_msg}")

    return None
```

Este es, con diferencia, **el método más usado de todo el parser**. La idea: "espero que el token actual sea de tipo `token_type`". Si lo es, lo consume (avanza el cursor) y lo devuelve. Si no lo es, registra un error de sintaxis (con un mensaje personalizado si se pasó uno, o uno genérico si no) y devuelve `None`.

`message or f"..."` usa el operador `or` de Python como "valor por defecto": si `message` es `None` (o cualquier valor "falso"), se usa el string de la derecha. Es el mismo patrón que `message != null ? message : "..."` en Java, pero más compacto.

Casi todos los métodos `_parse_X()` del resto del archivo son, en esencia, una secuencia de llamadas a `_consume()` en el orden exacto que dicta la gramática.

### 5.9 Registro de errores sintácticos

```python
def _add_error_with_suggestions(self, token, base_message):
    col = self._get_column(token)
    error_line = f"[ERROR SINTÁCTICO] Línea {token.lineno}, Col {col}: {base_message}"

    # Buscar palabras reservadas parecidas si el token es un IDENTIFIER
    if token.type == "IDENTIFIER":
        suggestions = _get_suggestions_for_word(
            token.value, cutoff=0.6, max_suggestions=2
        )
        if suggestions:
            sugerencia = " | ".join(f"'{s}'" for s in suggestions)
            error_line += f"\n   💡 Sugerencia: ¿Quisiste decir {sugerencia}?"

    self.errors.append(error_line)
```

Además de construir el mensaje con línea/columna, si el token problemático es un `IDENTIFIER` (es decir, una palabra que el usuario escribió libremente, no una palabra clave reconocida), busca sugerencias parecidas con la función de la sección 5.3 y las agrega al mensaje. `" | ".join(f"'{s}'" for s in suggestions)` es una **comprensión de generador** dentro de un `join`: para cada sugerencia `s`, la envuelve en comillas simples, y junta todas con `" | "` entre medio — el resultado sería algo como `'tempo' | 'track'`.

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

Una versión más simple, sin sugerencias, para los casos donde ya se sabe el mensaje exacto a mostrar (o no hay token, como cuando el archivo termina de forma inesperada).

### 5.10 Recuperación de errores — "Modo Pánico" (`_synchronize`)

```python
def _synchronize(self, sync_tokens):
    """
    Recuperación de errores en Modo Pánico (Panic Mode).
    Descarta tokens uno a uno hasta encontrar uno cuyo tipo esté dentro
    de sync_tokens (token de sincronización seguro) o hasta llegar al
    final del archivo.
    """
    sync_set = set(sync_tokens)
    while not self._is_at_end():
        if self._current_token().type in sync_set:
            return
        self._advance()
```

El "**modo pánico**" es una técnica estándar de recuperación de errores en parsers: cuando algo no coincide con la gramática, en vez de detener todo el análisis, el parser **descarta tokens uno por uno** hasta encontrar un punto "seguro" para reanudar — típicamente el inicio de la siguiente sentencia (`track`, `tempo`, etc.) o el cierre de un bloque (`}`). `sync_tokens` es la lista de tipos de token que cuentan como "puntos seguros" en ese contexto específico (varía según en qué parte de la gramática se produjo el error). `set(sync_tokens)` convierte la lista en un **conjunto** (`HashSet` en Java) porque comprobar "¿está este elemento adentro?" es más rápido en un set que en una lista.

### 5.11 El punto de entrada — `parse()`

```python
def parse(self):
    """
    Parsea el programa completo y retorna el AST.
    """
    program = Program()

    while not self._is_at_end():
        stmt = self._parse_statement()
        if stmt:
            program.statements.append(stmt)

    return program
```

El método que se llama desde fuera de la clase (como un `main()` de este módulo). Crea el nodo raíz `Program()` vacío, y mientras queden tokens, pide una sentencia tras otra con `_parse_statement()`, agregándola a la lista si se obtuvo una (si hubo error, `_parse_statement()` puede devolver `None`, y entonces no se agrega nada, pero el bucle sigue intentando con el resto del archivo).

### 5.12 Sentencias de nivel superior — `_parse_statement`

```python
def _parse_statement(self):
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
        if current.type == "IDENTIFIER":
            suggestions = _get_suggestions_for_word(current.value, cutoff=0.5)
            if suggestions:
                sugerencia = " | ".join(f"'{s}'" for s in suggestions)
                self._add_error(
                    f"'{current.value}' no es una palabra reservada válida.\n"
                    f"   💡 Sugerencia: ¿Quisiste decir {sugerencia}?",
                    token=current,
                )
            else:
                self._add_error(
                    f"'{current.value}' no es una palabra reservada válida.",
                    token=current,
                )
        else:
            self._add_error(
                f"Token inesperado: '{current.type}' con valor '{current.value}'",
                token=current,
            )
        self._synchronize({
            "TEMPO_KW", "VOLUME_KW", "INSTRUMENT_KW",
            "TRACK_KW", "REPEAT_KW",
        })
        return None
```

Este método es el "despachador" de nivel superior: mira el token actual con `_check()` y decide a cuál método especializado delegar, según cuál palabra clave sea. Si el token no coincide con **ninguna** de las sentencias válidas, cae en el `else`: construye un mensaje de error (con sugerencias si es un `IDENTIFIER` parecido a una palabra reservada), y llama a `_synchronize(...)` pasándole el conjunto de palabras clave que son puntos seguros para reanudar el análisis desde el inicio de la siguiente sentencia.

### 5.13 Las sentencias más simples — `tempo`, `volume`, `instrument`

```python
def _parse_tempo(self):
    """Parsea: tempo <número>"""
    kw = self._consume("TEMPO_KW")
    num_token = self._consume("NUMBER", "Se esperaba un número después de 'tempo'")

    if num_token:
        return self._at(Tempo(num_token.value), kw, num_token)
    return None
```

```python
def _parse_volume(self):
    """Parsea: volume <número>"""
    kw = self._consume("VOLUME_KW")
    num_token = self._consume("NUMBER", "Se esperaba un número después de 'volume'")

    if num_token:
        return self._at(Volume(num_token.value), kw, num_token)
    return None
```

```python
def _parse_instrument(self):
    """Parsea: instrument <nombre_instrumento>"""
    kw = self._consume("INSTRUMENT_KW")
    instr_token = self._consume("INSTR_NAME", "Se esperaba un nombre de instrumento")

    if instr_token:
        return self._at(Instrument(instr_token.value), kw, instr_token)
    return None
```

Los tres siguen el mismo patrón exacto, que vas a ver repetirse en casi todo el archivo: 1) consumir la palabra clave, 2) consumir el argumento esperado (reportando un mensaje de error específico si falta), 3) si el argumento se obtuvo, construir el nodo del AST correspondiente y estampar sus posiciones con `_at()` (pasando tanto el token de la palabra clave como el del argumento, para que `node.line/col` y `node.arg_line/arg_col` queden ambos guardados).

### 5.14 `track` — `_parse_track`

```python
def _parse_track(self):
    """Parsea: track <identificador> { <eventos> }"""
    kw = self._consume("TRACK_KW")
    name_token = self._consume("IDENTIFIER", "Se esperaba un nombre de track")
    self._consume("LBRACE", "Se esperaba '{'")

    events = []
    while not self._check("RBRACE") and not self._is_at_end():
        event = self._parse_event()
        if event:
            events.append(event)

    self._consume("RBRACE", "Se esperaba '}'")

    if name_token:
        return self._at(Track(name_token.value, events), kw, name_token)
    return None
```

Aquí ya aparece la recursión real de "recursivo descendente": después de consumir `track`, el nombre y `{`, el método entra en un bucle que llama a `_parse_event()` repetidamente — y cada evento puede, a su vez, ser un `chord` o un `repeat` que internamente vuelve a llamar a otros métodos `_parse_X()`. El bucle se detiene cuando encuentra `}` o se queda sin tokens (por si el archivo termina sin cerrar el bloque).

### 5.15 `chord` — `_parse_chord` (el más elaborado)

```python
def _parse_chord(self):
    kw_token = self._current_token()
    self._consume("CHORD_KW")
    self._consume("LBRACE", "Se esperaba '{' después de 'chord'")

    notas, note_pos = [], []      # pitches y (línea, col) de cada nota
    durations = []                # [(valor, línea, col)]
    invalid_notes = []            # [(texto, línea, col)] tokens con forma de nota pero inválidos (S8)
    misplaced_pos = None          # primera nota que aparece DESPUÉS de una duración

    while not self._check("RBRACE") and not self._is_at_end():
        tok = self._current_token()
        pos = (tok.lineno, self._get_column(tok))
        es_nota_mal_formada = (
            tok.type == "IDENTIFIER" and re.match(r"^[A-Za-z][#b]*\d+$", tok.value)
        )
        if tok.type == "NOTE" or es_nota_mal_formada:
            if durations and misplaced_pos is None:
                misplaced_pos = pos
            if tok.type == "NOTE":
                notas.append(tok.value)
                note_pos.append(pos)
            else:
                invalid_notes.append((tok.value, *pos))
            self._advance()
        elif tok.type == "DURATION":
            durations.append((tok.value, *pos))
            self._advance()
        else:
            self._add_error_with_suggestions(
                tok, f"'{tok.value}' no es válido dentro de un acorde"
            )
            self._advance()

    self._consume("RBRACE", "Se esperaba '}'")

    node = Chord(notas, durations[0][0] if durations else None)
    node.note_pos = note_pos
    node.durations = durations
    node.invalid_notes = invalid_notes
    node.misplaced_pos = misplaced_pos
    return self._at(node, kw_token)
```

Este método es deliberadamente **permisivo** en cuanto a la gramática: en vez de rechazar de inmediato cualquier cosa rara dentro de `chord { }`, recolecta por separado notas válidas (`notas`/`note_pos`), posibles duraciones (`durations`), y "cosas con forma de nota pero inválidas" (`invalid_notes` — por ejemplo `H4`, que parece una nota pero `H` no existe en la escala musical). También detecta y guarda `misplaced_pos`: la posición de la primera nota que aparece *después* de ya haber visto una duración (lo cual sería un error de orden, pero el parser solo lo **registra**, no lo rechaza).

¿Por qué esta permisividad? Porque **el parser solo valida la estructura** (que haya llaves, que los tokens tengan forma de nota/duración). Decidir si el acorde tiene la cantidad correcta de notas, si la duración está en la posición correcta, o si una nota con forma rara es realmente inválida, son preguntas de **significado** — y esas las responde el análisis semántico (regla S6 y S8, explicadas en [`ANALISIS_SEMANTICO.md`](ANALISIS_SEMANTICO.md)), no el parser. Por eso el nodo `Chord` termina cargando estos campos extra (`note_pos`, `durations`, `invalid_notes`, `misplaced_pos`) — son "evidencia" que el parser recolectó para que la siguiente etapa pueda emitir mensajes de error precisos sin tener que volver a escanear el bloque.

`re.match(r"^[A-Za-z][#b]*\d+$", tok.value)` usa el módulo `re` (expresiones regulares) de Python para comprobar, a mano, si un `IDENTIFIER` *tiene forma* de nota (letra + alteraciones + dígitos) aunque no haya sido reconocido como `NOTE` por el lexer — esto pasa, por ejemplo, con `H4`: como `H` no es una letra válida en la regex del lexer (`[A-Ga-g]`), el lexer lo deja pasar como `IDENTIFIER` en vez de `NOTE`, y aquí el parser lo "recupera" para poder reportarlo como una nota inválida en vez de un error de sintaxis genérico.

### 5.16 `repeat` a nivel de sentencia — `_parse_repeat_statement`

```python
def _parse_repeat_statement(self):
    """Parsea repeat a nivel de sentencia: repeat <número> { <sentencias> }"""
    kw = self._consume("REPEAT_KW")
    count_token = self._consume("NUMBER", "Se esperaba un número después de 'repeat'")
    self._consume("LBRACE", "Se esperaba '{'")

    statements = []
    while not self._check("RBRACE") and not self._is_at_end():
        # El cuerpo acepta sentencias globales Y eventos (nota / rest),
        # p. ej.: repeat 2 { C4 negra rest negra }
        if self._check("NOTE") or self._check("REST"):
            stmt = self._parse_event()
        else:
            stmt = self._parse_statement()
        if stmt:
            statements.append(stmt)

    self._consume("RBRACE", "Se esperaba '}'")

    if count_token:
        return self._at(Repeat(count_token.value, statements), kw, count_token)
    return None
```

Nota la decisión dentro del bucle: `repeat` puede usarse tanto a nivel del programa completo (repitiendo otras sentencias como `track`) como a nivel de evento dentro de un track (repitiendo notas directamente). Por eso este método comprueba si el siguiente token es `NOTE`/`REST` (y en ese caso llama a `_parse_event()`) o si es otra cosa (y entonces asume que es una sentencia completa, llamando a `_parse_statement()`).

### 5.17 Eventos dentro de un track — `_parse_event`

```python
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
        # (mismo patrón que _parse_statement, adaptado al contexto de "evento")
        ...
        self._synchronize({
            "NOTE", "REST", "REPEAT_KW", "RBRACE",
        })
        return None
```

El mismo patrón "despachador" de `_parse_statement()`, pero para las cosas que pueden aparecer *dentro* de un track: una nota, un silencio, un acorde anidado, o un `repeat` anidado.

### 5.18 Notas y silencios — `_parse_note`, `_parse_rest`

```python
def _parse_note(self):
    """Parsea: <nota> <duración>"""
    note_token = self._consume("NOTE")
    duration_token = self._consume(
        "DURATION", "Se esperaba una duración después de la nota"
    )

    if note_token and duration_token:
        return self._at(Note(note_token.value, duration_token.value), note_token, note_token)
    return None
```

```python
def _parse_rest(self):
    """Parsea: rest <duración>"""
    kw = self._consume("REST")
    duration_token = self._consume(
        "DURATION", "Se esperaba una duración después de 'rest'"
    )

    if duration_token:
        return self._at(Rest(duration_token.value), kw, duration_token)
    return None
```

Simples y directos: cada nota y cada silencio es solo una palabra seguida de su duración.

### 5.19 `repeat` a nivel de evento — `_parse_repeat_event`

```python
def _parse_repeat_event(self):
    """Parsea repeat a nivel de evento: repeat <número> { <eventos> }"""
    kw = self._consume("REPEAT_KW")
    count_token = self._consume("NUMBER", "Se esperaba un número después de 'repeat'")
    self._consume("LBRACE", "Se esperaba '{'")

    events = []
    while not self._check("RBRACE") and not self._is_at_end():
        event = self._parse_event()
        if event:
            events.append(event)

    self._consume("RBRACE", "Se esperaba '}'")

    if count_token:
        return self._at(Repeat(count_token.value, events), kw, count_token)
    return None
```

Casi idéntico a `_parse_track()`, pero construyendo un nodo `Repeat` en vez de `Track`, y llamando a `_parse_event()` en el bucle en vez de aceptar sentencias completas.

### 5.20 Ejemplo completo: de tokens a AST

Para el código:
```
tempo 120
track t {
    C4 negra
}
```

El lexer produce (simplificado): `TEMPO_KW, NUMBER(120), TRACK_KW, IDENTIFIER(t), LBRACE, NOTE(C4), DURATION(negra), RBRACE`.

El parser, siguiendo la gramática, construye:

```
Program
├── Tempo(bpm=120)
└── Track(name="t")
    └── Note(pitch="C4", duration="negra")
```

En código Python real, esto es un objeto `Program` cuyo atributo `statements` es `[Tempo(...), Track(...)]`, y el `Track` tiene `events = [Note(...)]`.

### 5.21 Funciones de visualización — no son parte de la lógica de compilación

Al final de `parser.py` hay tres funciones que **no participan en la compilación en sí**: solo convierten un AST ya construido en distintas representaciones visuales, para que el IDE pueda mostrárselo al usuario.

```python
def ast_to_table_rows(node, parent_id=""):
    """Convierte un nodo AST a una lista de tuplas para insertar en un Treeview."""
    rows = []
    if isinstance(node, Program):
        for stmt in node.statements:
            rows.extend(ast_to_table_rows(stmt, parent_id))
    elif isinstance(node, Tempo):
        rows.append((parent_id, f"Tempo {node.bpm}", ("Tempo", "Comando", f"{node.bpm} BPM"), "leaf"))
    # ... un caso "elif" por cada tipo de nodo (Volume, Instrument, Track, Note, Rest, Chord, Repeat)
    return rows
```

Recorre el árbol con el mismo patrón `isinstance()` que ya vas a reconocer de `semantic.py` (patrón Visitor), pero en vez de validar nada, simplemente construye filas de texto (`tuple`) que la interfaz Tkinter usa para llenar una tabla visual (`Treeview`).

```python
def ast_to_tree_string(node, indent="", is_last=True):
    """
    Convierte un nodo AST a una representación visual estilo árbol de directorios.
    Usa caracteres Unicode: ├── rama intermedia, └── última rama, │ continuación.
    """
    ...
```

Genera un texto con la misma apariencia que el comando `tree` de una terminal, útil para pegar en un documento o mostrar en consola sin necesitar una interfaz gráfica.

```python
def generate_visual_tree(ast_root, output_filename="parse_tree"):
    """
    Genera un Árbol de Derivación visual usando Graphviz y lo guarda como PNG.
    """
    import graphviz  # pip install graphviz (requiere también el binario de Graphviz)
    ...
```

Esta es la más elaborada: usa la librería `graphviz` para generar una **imagen PNG** real del árbol de derivación (mostrando tanto los nodos internos como los tokens terminales), ideal para incluir directamente en una presentación o documento para el profesor. Internamente recorre el árbol con el mismo patrón visitor, pero en vez de construir texto, va llamando a `dot.node(...)` y `dot.edge(...)` para construir el grafo que Graphviz luego dibuja.

---

## 6. Etapa 3 — Análisis Semántico (`beatscript/semantic.py`)

Resumen: el parser solo valida la **forma** del programa (que las palabras estén en el orden correcto); `semantic.py` valida el **significado** — por ejemplo que `tempo` esté entre 20 y 400 BPM, que no haya dos tracks con el mismo nombre, o que una nota no se salga del rango MIDI permitido (0-127). Recorre el AST ya construido (no los tokens) con el patrón Visitor, y construye una **tabla de símbolos** con los tracks declarados.

**El detalle completo de esta etapa — cada clase, cada método, cada una de las 8 reglas con ejemplos y la fórmula de conversión nota→MIDI explicada paso a paso — está en el documento [`ANALISIS_SEMANTICO.md`](ANALISIS_SEMANTICO.md)**, porque es suficientemente extenso como para merecer su propio documento completo sin diluir esta visión general.

---

## 7. Etapa 4 (atajo actual) — Generación de MIDI (`beatscript/midi_gen.py`)

Como se explicó en la sección 2, esta etapa **no sigue la ruta de un compilador clásico**: toma la lista de tokens cruda (no el AST, no la tabla de símbolos) y la recorre con un índice manual.

### 7.1 Tablas de conversión

```python
NOTE_SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

DURATION_BEATS = {
    'redonda':     4.0,
    'blanca':      2.0,
    'negra':       1.0,
    'corchea':     0.5,
    'semicorchea': 0.25,
    'fusa':        0.125,
    'semifusa':    0.0625,
}

INSTRUMENT_PROGRAM = {
    'piano':       0,
    'violin':     40,
    # ... (28 instrumentos en total, cada uno con su número de programa MIDI General)
}
```

Tres diccionarios de conversión: letra de nota → semitonos desde Do, nombre de duración → cuántos beats dura (la negra es la unidad base = 1 beat), y nombre de instrumento BeatScript → número de programa del estándar **MIDI General** (un catálogo fijo de 128 instrumentos que cualquier reproductor MIDI entiende igual).

### 7.2 Convertir nota a número MIDI — `note_to_midi`

```python
def note_to_midi(note_str: str) -> int:
    s = note_str.upper()
    letter = s[0]
    rest   = s[1:]
    # Detecta si hay alteración: el segundo carácter es # o B con dígito después
    if rest and rest[0] in ('#', 'B') and len(rest) > 1:
        alt, octave = rest[0], int(rest[1:])
    else:
        alt, octave = '', int(rest)
    pitch = NOTE_SEMITONES[letter] + (octave + 1) * 12
    if alt == '#': pitch += 1   # Sostenido: sube un semitono
    if alt == 'B': pitch -= 1   # Bemol: baja un semitono
    return pitch
```

Esta es prácticamente la misma fórmula que `pitch_to_midi()` de `semantic.py` (explicada en detalle en `ANALISIS_SEMANTICO.md`) — **duplicada** en este archivo, porque como se explicó, `midi_gen.py` no importa nada de `semantic.py`. `s[0]` toma el primer carácter (la letra), `s[1:]` toma "desde el índice 1 hasta el final" (el *slicing* de Python — equivalente a `substring(1)` en Java). Luego distingue si lo que sigue es una alteración (`#`/`B`) seguida de la octava, o directamente la octava sola.

### 7.3 Extraer un bloque `{ }` — `_collect_block`

```python
def _collect_block(tokens: list, start: int):
    depth, end = 1, start
    while end < len(tokens) and depth > 0:
        if   tokens[end].type == 'LBRACE': depth += 1
        elif tokens[end].type == 'RBRACE': depth -= 1
        end += 1
    return tokens[start:end - 1], end
```

Como `midi_gen.py` trabaja sobre tokens **crudos** (no sobre un árbol que ya tiene los bloques delimitados como listas), necesita su propia forma de encontrar dónde termina un bloque `{ ... }`. Usa un contador de profundidad (`depth`): empieza en 1 (ya se asume que `start` es el token justo después del `{` de apertura), sube con cada `{` que encuentra (un bloque anidado) y baja con cada `}`; cuando `depth` llega a 0, significa que encontró el `}` que cierra el bloque original. `tokens[start:end - 1]` es un *slice* de la lista (como `List.subList(...)` en Java) que toma el bloque sin incluir la llave de cierre.

### 7.4 El generador principal — `tokens_to_midi`

```python
def tokens_to_midi(tokens: list, output_path: str = "output.mid") -> str:
    midi     = MIDIFile(1)   # 1 pista MIDI
    track    = 0
    channel  = 0
    tempo    = 120           # BPM por defecto si el código no define 'tempo'
    program  = 0             # Programa MIDI por defecto (piano acústico = 0)
    velocity = 80            # Volumen por defecto (0-127)
    midi.addTempo(track, 0, tempo)
    midi.addProgramChange(track, channel, 0, program)

    def process(tok_list: list, t: float) -> float:
        nonlocal tempo, program, velocity
        j = 0
        while j < len(tok_list):
            tok = tok_list[j]
            # ... un bloque if/elif por cada tipo de token (ver 7.5)
            j += 1
        return t

    process(tokens, 0.0)   # Procesa el programa completo desde t=0

    with open(output_path, 'wb') as f:
        midi.writeFile(f)

    return output_path
```

`MIDIFile(1)` crea un archivo MIDI con 1 pista (de la librería externa `midiutil`). Las variables `tempo`, `program`, `velocity` guardan el **estado musical actual** mientras se recorre el programa — empiezan con valores por defecto razonables (120 BPM, piano, volumen medio) para el caso de que el código BeatScript nunca los defina explícitamente.

Lo más particular de Python aquí es `process()`: es una **función anidada** (definida dentro de otra función), algo que Java no permite directamente (tendrías que usar una clase interna o una lambda con limitaciones). `nonlocal tempo, program, velocity` le dice a Python "estas variables NO son locales a `process()`, son las del ámbito exterior (`tokens_to_midi`) — modifícalas ahí, no crees copias nuevas". Sin `nonlocal`, cualquier asignación a `tempo` dentro de `process()` crearía una variable local nueva que desaparecería al salir de la función, y el cambio nunca se reflejaría afuera.

`process()` se llama **recursivamente a sí misma** cada vez que encuentra un bloque anidado (`track { }`, `repeat N { }`) — así es como maneja la jerarquía sin necesitar un árbol: en vez de "bajar un nivel en el árbol", literalmente vuelve a llamarse con el sub-tramo de tokens de ese bloque.

### 7.5 El recorrido token por token dentro de `process`

```python
# volume N → actualiza velocity (clampeado a rango MIDI 0-127)
if tok.type == 'VOLUME_KW':
    if j + 1 < len(tok_list) and tok_list[j + 1].type == 'NUMBER':
        velocity = max(0, min(127, tok_list[j + 1].value))
        j += 2; continue
```
Mira el token siguiente (`tok_list[j + 1]`) sin un método `_peek` dedicado (a diferencia del parser, aquí se indexa la lista directamente). `max(0, min(127, valor))` es la forma típica de "clampear" (recortar) un número a un rango — primero evita que supere 127, luego evita que sea menor que 0.

```python
# tempo N → actualiza BPM en el archivo MIDI en el tiempo actual
elif tok.type == 'TEMPO_KW':
    if j + 1 < len(tok_list) and tok_list[j + 1].type == 'NUMBER':
        tempo = tok_list[j + 1].value
        midi.addTempo(track, t, tempo)
        j += 2; continue
```
`midi.addTempo(track, t, tempo)` es una llamada a la librería `midiutil`: registra un cambio de tempo en el archivo MIDI, en el instante `t` (el tiempo acumulado hasta ahora, no el inicio del archivo) — esto permite que un programa BeatScript cambie de tempo a mitad de la pieza, como en el ejemplo del README.

```python
# instrument NAME → cambia el programa MIDI del canal en tiempo t
elif tok.type == 'INSTRUMENT_KW':
    if j + 1 < len(tok_list) and tok_list[j + 1].type == 'INSTR_NAME':
        program = INSTRUMENT_PROGRAM.get(tok_list[j + 1].value, 0)
        midi.addProgramChange(track, channel, t, program)
        j += 2; continue
```

```python
# track NAME { ... } → extrae el bloque y lo procesa recursivamente
elif tok.type == 'TRACK_KW':
    k = j + 1
    while k < len(tok_list) and tok_list[k].type != 'LBRACE':
        k += 1
    if k < len(tok_list):
        block, end = _collect_block(tok_list, k + 1)
        t = process(block, t)
        j = end; continue
```
Busca hacia adelante el `{` de apertura del track, extrae su contenido con `_collect_block`, y llama a `process(block, t)` **recursivamente** — el resultado (el tiempo acumulado después de procesar todo el bloque) se guarda de vuelta en `t`, para que el siguiente evento después del track continúe desde ahí.

```python
# repeat N { ... } → extrae el bloque y lo procesa N veces seguidas
elif tok.type == 'REPEAT_KW':
    n, k = 1, j + 1
    if k < len(tok_list) and tok_list[k].type == 'NUMBER':
        n = tok_list[k].value; k += 1
    while k < len(tok_list) and tok_list[k].type != 'LBRACE':
        k += 1
    if k < len(tok_list):
        block, end = _collect_block(tok_list, k + 1)
        for _ in range(n):
            t = process(block, t)   # Cada iteración parte desde t actualizado
        j = end; continue
```
Aquí está la implementación *real* de la repetición: un `for _ in range(n)` que llama a `process(block, t)` exactamente `n` veces, y cada vez usa el `t` actualizado de la vuelta anterior — por eso las notas de la segunda repetición empiezan justo después de donde terminó la primera, no se superponen.

```python
# chord { NOTE... DURATION } → agrega todas las notas en el mismo t
elif tok.type == 'CHORD_KW':
    k = j + 1
    while k < len(tok_list) and tok_list[k].type != 'LBRACE':
        k += 1
    if k < len(tok_list):
        block, end = _collect_block(tok_list, k + 1)
        chord_notes = [b.value for b in block if b.type == 'NOTE']
        dur_tok = next((b for b in reversed(block) if b.type == 'DURATION'), None)
        dur = DURATION_BEATS.get(dur_tok.value, 1.0) if dur_tok else 1.0
        for note in chord_notes:
            midi.addNote(track, channel, note_to_midi(note), t, dur, velocity)
        t += dur   # Avanza t una sola vez (todas las notas son simultáneas)
        j = end; continue
```
`chord_notes = [b.value for b in block if b.type == 'NOTE']` es una **lista por comprensión** (*list comprehension*) — el equivalente a un `.stream().filter(...).map(...).collect(...)` de Java, pero en una sola línea: recorre `block`, se queda solo con los tokens de tipo `NOTE`, y toma su `.value`. `next((b for b in reversed(block) if b.type == 'DURATION'), None)` busca la **última** duración del bloque (recorriendo `block` al revés con `reversed()` y tomando la primera que encuentra, que en el orden original es la última), con `None` como valor por defecto si no hay ninguna. Todas las notas del acorde se agregan en el **mismo** instante `t` (por eso suenan simultáneas), y `t` solo avanza **una vez** al final, no por cada nota.

```python
# NOTE [DURATION] → agrega la nota y avanza t por su duración
elif tok.type == 'NOTE':
    dur = 1.0
    if j + 1 < len(tok_list) and tok_list[j + 1].type == 'DURATION':
        dur = DURATION_BEATS.get(tok_list[j + 1].value, 1.0)
        j += 1
    try:
        midi.addNote(track, channel, note_to_midi(tok.value), t, dur, 80)
    except Exception:
        pass   # Ignora notas con valores MIDI fuera de rango
    t += dur
```
`try/except` es el equivalente de `try/catch` en Java. Aquí se usa como una **red de seguridad**: si `note_to_midi(...)` produjera un valor fuera del rango MIDI válido (0-127) y la librería `midiutil` lanzara una excepción al intentar agregarla, el `except Exception: pass` simplemente la ignora en silencio, en vez de detener la generación de todo el archivo por una sola nota problemática. (En la práctica esto rara vez ocurre porque el análisis semántico ya debería haber detectado notas fuera de rango antes de llegar aquí — pero como esta función ni siquiera recibe el resultado del análisis semántico, no tiene ninguna garantía real de que eso haya pasado.)

```python
# rest [DURATION] → silencio: solo avanza t, no agrega nota
elif tok.type == 'REST':
    dur = 1.0
    if j + 1 < len(tok_list) and tok_list[j + 1].type == 'DURATION':
        dur = DURATION_BEATS.get(tok_list[j + 1].value, 1.0)
        j += 1
    t += dur   # El tiempo avanza igual que con una nota, pero sin sonido
```
Un silencio es, literalmente, "avanza el tiempo pero no llames a `midi.addNote(...)`" — por eso el código es casi idéntico al de `NOTE`, solo sin la línea que agrega la nota.

---

## 8. Cómo correr el proyecto

```bash
# Instalar dependencias
pip install -r requirements.txt

# Abrir el IDE visual
python main_gui.py

# Probar solo el lexer desde consola (con su demo incluido al final del archivo)
python -X utf8 beatscript/lexer.py

# Correr las pruebas de cada etapa
python -m pytest beatscript/tests/ -v
```
