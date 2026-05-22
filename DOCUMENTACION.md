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
   - 3.4 Teoría formal: Alfabeto y Lenguajes Regulares
   - 3.5 Autómatas Finitos: AFN y AFD
   - 3.6 AFDs de los tokens de BeatScript
   - 3.7 Construcción de Thompson: regex → AFN
   - 3.8 Construcción de subconjuntos: AFN → AFD
   - 3.9 Cómo PLY construye el lexer internamente
   - 3.10 Prioridad de reglas en PLY
   - 3.11 Manejo de errores léxicos
   - 3.12 API pública del lexer
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

**¿Por qué es un compilador?** Porque sigue las mismas etapas de un compilador clásico. Actualmente el proyecto implementa la **Etapa 1 (Análisis Léxico)** completa, y la **Generación de código MIDI** directamente desde tokens:

```
Código fuente (texto)
        ↓
  [Análisis Léxico]      ← Etapa 1 — IMPLEMENTADA
        ↓
  [Generación MIDI]      ← Implementada directo desde tokens
        ↓
  archivo output.mid
```

---

## 2. Arquitectura general del compilador

```
c:\Compiladores\
├── main_gui.py              ← IDE visual (la ventana que ve el usuario)
└── beatscript\
    ├── lexer.py             ← Analizador léxico (Etapa 1) — núcleo del compilador
    ├── midi_gen.py          ← Generador de archivos MIDI
    └── tests\
        └── test_lexer.py    ← 74 pruebas automáticas del lexer
```

El flujo de datos es:

```
Usuario escribe código
        ↓
main_gui.py llama a lexer.tokenize()
        ↓
lexer.py devuelve lista de tokens + lista de errores
        ↓
main_gui.py valida semánticamente los pares de tokens
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

Un **analizador léxico** (lexer, scanner o tokenizador) es el primer componente de cualquier compilador. Su trabajo es recibir el código fuente como una cadena de caracteres y dividirlo en **tokens**: la unidad mínima con significado en el lenguaje.

Analogía con el español: así como al leer "El gato duerme" separamos las palabras "El", "gato", "duerme" antes de analizar la gramática, el lexer separa `tempo 120` en los tokens `TEMPO_KW` y `NUMBER(120)`.

| Entrada (texto) | Token generado | Tipo |
| --- | --- | --- |
| `tempo` | `tempo` | `TEMPO_KW` |
| `120` | `120` | `NUMBER` |
| `C4` | `C4` | `NOTE` |
| `negra` | `negra` | `DURATION` |
| `{` | `{` | `LBRACE` |
| `# comentario` | (descartado) | — |

El lexer **no entiende la estructura** del programa. Si el código dice `negra tempo 120`, produce tres tokens válidos sin protestar — eso lo detecta la etapa siguiente.

### 3.2 Tokens reconocidos

BeatScript define **14 tipos de tokens** en la tupla `tokens` de `lexer.py`:

```python
tokens = (
    "TEMPO_KW",       # keyword 'tempo'
    "VOLUME_KW",      # keyword 'volume'
    "INSTRUMENT_KW",  # keyword 'instrument'
    "TRACK_KW",       # keyword 'track'
    "REPEAT_KW",      # keyword 'repeat'
    "CHORD_KW",       # keyword 'chord'
    "REST",           # keyword 'rest'
    "NOTE",           # nota: [A-G][#b]?[0-9]   ej: C4, D#3, Eb5
    "DURATION",       # redonda|blanca|negra|corchea|semicorchea|fusa|semifusa
    "INSTR_NAME",     # piano|guitar|violin|...  (30 instrumentos)
    "NUMBER",         # entero: [0-9]+
    "IDENTIFIER",     # nombre libre: [a-zA-Z_][a-zA-Z0-9_]*
    "LBRACE",         # {
    "RBRACE",         # }
)
```

PLY **requiere** esta tupla exacta. Si se agrega un tipo de token en las reglas sin declararlo aquí, PLY lanza un error al construir el lexer.

| Token | Descripción | Ejemplo |
| --- | --- | --- |
| `TEMPO_KW` | Palabra clave para tempo | `tempo` |
| `VOLUME_KW` | Control de volumen | `volume` |
| `INSTRUMENT_KW` | Palabra clave para instrumento | `instrument` |
| `TRACK_KW` | Palabra clave para pistas | `track` |
| `REPEAT_KW` | Palabra clave para repetición | `repeat` |
| `CHORD_KW` | Palabra clave para acordes | `chord` |
| `REST` | Silencio musical | `rest` |
| `NOTE` | Nota musical con octava | `C4`, `D#3`, `Eb5` |
| `DURATION` | Duración de nota | `negra`, `blanca`, `corchea` |
| `INSTR_NAME` | Nombre de instrumento MIDI | `piano`, `violin`, `guitar` |
| `NUMBER` | Número entero positivo | `120`, `88`, `2` |
| `IDENTIFIER` | Nombre libre definido por usuario | `melodia`, `coro`, `mi_track` |
| `LBRACE` | Llave de apertura | `{` |
| `RBRACE` | Llave de cierre | `}` |

### 3.3 Palabras reservadas (RESERVED)

El lexer usa un diccionario Python `RESERVED` que mapea cada palabra clave a su tipo de token:

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
    "redonda"     : "DURATION",   # 4 tiempos
    "blanca"      : "DURATION",   # 2 tiempos
    "negra"       : "DURATION",   # 1 tiempo
    "corchea"     : "DURATION",   # 0.5 tiempos
    "semicorchea" : "DURATION",   # 0.25 tiempos
    "fusa"        : "DURATION",   # 0.125 tiempos
    "semifusa"    : "DURATION",   # 0.0625 tiempos

    # 30 instrumentos MIDI (piano, violin, flute, trumpet, guitar...)
    "piano"       : "INSTR_NAME",
    "violin"      : "INSTR_NAME",
    "viola"       : "INSTR_NAME",
    "cello"       : "INSTR_NAME",
    "contrabass"  : "INSTR_NAME",
    "harp"        : "INSTR_NAME",
    "flute"       : "INSTR_NAME",
    "piccolo"     : "INSTR_NAME",
    "recorder"    : "INSTR_NAME",
    "oboe"        : "INSTR_NAME",
    "clarinet"    : "INSTR_NAME",
    "bassoon"     : "INSTR_NAME",
    "saxophone"   : "INSTR_NAME",
    "trumpet"     : "INSTR_NAME",
    "trombone"    : "INSTR_NAME",
    "frenchhorn"  : "INSTR_NAME",
    "tuba"        : "INSTR_NAME",
    "marimba"     : "INSTR_NAME",
    "vibraphone"  : "INSTR_NAME",
    "xylophone"   : "INSTR_NAME",
    "celesta"     : "INSTR_NAME",
    "drums"       : "INSTR_NAME",
    "guitar"      : "INSTR_NAME",
    "bass"        : "INSTR_NAME",
    "banjo"       : "INSTR_NAME",
    "sitar"       : "INSTR_NAME",
    "harpsichord" : "INSTR_NAME",
    "organ"       : "INSTR_NAME",
    "accordion"   : "INSTR_NAME",
    "harmonica"   : "INSTR_NAME",
}
```

**¿Para qué sirve esto?** El lexer captura primero cualquier secuencia de letras como `IDENTIFIER` con la regex `[a-zA-Z_][a-zA-Z0-9_]*`. Luego consulta `RESERVED` para ver si esa palabra tiene un significado especial. Si sí, cambia el tipo del token:

```text
Texto: "tempo"
  → El regex de IDENTIFIER captura "tempo"
  → RESERVED.get("tempo") → "TEMPO_KW"
  → El token queda con tipo TEMPO_KW, no IDENTIFIER
```

Esta técnica evita tener una regex diferente para cada palabra clave. Es más eficiente y equivale a una **tabla de símbolos** simplificada.

---

### 3.4 Teoría Formal: Alfabeto y Lenguajes Regulares

Para entender cómo funciona el lexer desde la base teórica, hay que partir de las definiciones formales de la teoría de lenguajes.

#### Alfabeto

Un **alfabeto** Σ es un conjunto finito y no vacío de símbolos. El alfabeto de BeatScript incluye:

```
Σ_BeatScript = {
    letras:              a-z, A-Z
    dígitos:             0-9
    símbolos válidos:    #  {  }  _  (espacio)  (tabulación)  (salto de línea)
    símbolos inválidos:  @  *  (  )  [  ]  ;  ,  .  /  ...
}
```

Los símbolos "inválidos" siguen siendo parte del universo de caracteres posibles — el lexer los rechaza con un error específico (ver sección 3.11).

#### Cadena y Lenguaje

- Una **cadena** (o palabra) es una secuencia finita de símbolos del alfabeto. Ejemplo: `"C4"`, `"tempo"`, `"negra"`.
- La **cadena vacía** se denota `ε`.
- Un **lenguaje** L sobre Σ es un conjunto (finito o infinito) de cadenas.

#### Lenguaje Regular

Un lenguaje es **regular** si puede ser descrito por una **expresión regular** (ER). Las ERs se construyen con tres operaciones básicas:

| Operación | Notación | Significado |
| --- | --- | --- |
| Unión | `r₁ \| r₂` | Pertenece a r₁ **o** a r₂ |
| Concatenación | `r₁ r₂` | r₁ seguido de r₂ |
| Cerradura de Kleene | `r*` | Cero o más repeticiones de r |

De estas tres se derivan las demás:

- `r+` = `r r*` (uno o más)
- `r?` = `r | ε` (cero o uno)
- `[a-z]` = `a | b | c | ... | z` (clase de caracteres)

**Ejemplo:** el lenguaje de los tokens `NOTE` en BeatScript es regular y se describe como:

```text
L(NOTE) = { s ∈ Σ* | s ∈ {A,B,C,D,E,F,G,a,b,c,d,e,f,g} × {#,b,ε} × {0,...,9} }
```

Con la expresión regular: `[A-Ga-g][#b]?[0-9]`

Este lenguaje es **infinito** (hay infinitas cadenas posibles: `C0`, `C1`... `G9`, `D#0`... `Fb9`...) pero **regular**, ya que la expresión regular lo describe completamente.

#### Propiedades de los Lenguajes Regulares

Los lenguajes regulares son **cerrados** bajo:

- Unión: L₁ ∪ L₂ sigue siendo regular
- Concatenación: L₁L₂ sigue siendo regular
- Cerradura de Kleene: L* sigue siendo regular
- Complemento: Σ* − L sigue siendo regular
- Intersección: L₁ ∩ L₂ sigue siendo regular

Esto es importante porque **el lenguaje de todos los tokens de BeatScript** se obtiene uniendo los lenguajes individuales de cada token, y esa unión sigue siendo regular. PLY puede construir un solo autómata que reconoce todos los tokens simultáneamente.

---

### 3.5 Autómatas Finitos: AFN y AFD

Un **autómata finito** es un modelo matemático de una máquina que lee una cadena de entrada carácter por carácter y decide si la acepta o rechaza.

#### Autómata Finito Determinista (AFD)

Formalmente, un AFD es una tupla M = (Q, Σ, δ, q₀, F) donde:

- **Q** = conjunto finito de estados
- **Σ** = alfabeto de entrada
- **δ: Q × Σ → Q** = función de transición (determinista: para cada par estado-símbolo, hay exactamente un estado destino)
- **q₀ ∈ Q** = estado inicial
- **F ⊆ Q** = conjunto de estados de aceptación

La máquina funciona así:

1. Comienza en q₀.
2. Lee el primer carácter c de la entrada.
3. Aplica δ(estado_actual, c) para obtener el siguiente estado.
4. Repite hasta agotar la entrada.
5. Si el estado final ∈ F, **acepta**. Si no, **rechaza**.

#### Autómata Finito No Determinista (AFN)

Un AFN es una tupla M = (Q, Σ, δ, q₀, F) donde la función de transición es:

`δ: Q × (Σ ∪ {ε}) → P(Q)`

La diferencia clave:

- El resultado es un **subconjunto de Q**, no un único estado (puede haber 0, 1 o muchos estados destino).
- Puede haber **transiciones ε** (se cambia de estado sin consumir ningún carácter).

En un AFN, la máquina "prueba todos los caminos posibles simultáneamente" — si existe algún camino que lleve a un estado de aceptación, la cadena es aceptada.

#### Equivalencia AFN ≡ AFD ≡ Expresión Regular

Este es el teorema fundamental de los lenguajes regulares (**Teorema de Kleene**):

```
ER  ←→  AFN  ←→  AFD
```

Cualquiera de los tres formalismos puede describir exactamente el mismo conjunto de lenguajes: los lenguajes regulares. Las conversiones entre ellos son algoritmos bien definidos:

| Conversión | Algoritmo |
| --- | --- |
| ER → AFN | Construcción de Thompson |
| AFN → AFD | Construcción de subconjuntos |
| AFD → AFD mínimo | Algoritmo de particiones de Hopcroft |
| AFD → ER | Ecuaciones de Arden o eliminación de estados |

PLY aplica exactamente estas conversiones internamente, como se detalla en la sección 3.9.

---

### 3.6 AFDs de los tokens de BeatScript

Aquí se muestra, para cada token, su expresión regular exacta del código y el AFD que la reconoce.

---

#### Token NOTE — Nota musical

**Expresión regular en el código:** `[A-Ga-g][#b]?[0-9]`

Esta regex acepta letras A hasta G (mayúsculas o minúsculas), seguidas opcionalmente por `#` o `b` (sostenido/bemol), y obligatoriamente por un dígito 0–9.

**AFD (4 estados):**

```
               [A-G, a-g]           [#, b]            [0-9]
    → q0 ─────────────────→ q1 ──────────────→ q2 ──────────────→ q3*

                               [0-9] (sin alteración)
                            q1 ──────────────────────────────────→ q3*
```

- **q0**: Estado inicial. Solo acepta letras A-G (mayúscula o minúscula).
- **q1**: Leyó la letra de la nota. Puede seguir `#`, `b`, o un dígito directamente.
- **q2**: Leyó la alteración. Ahora **debe** venir un dígito.
- **q3\***: Estado de aceptación. Nota bien formada.

**Tabla de transiciones del AFD:**

| Estado | [A-Ga-g] | [#b] | [0-9] | Aceptación |
| --- | --- | --- | --- | --- |
| q0 | q1 | — | — | No |
| q1 | — | q2 | q3 | No |
| q2 | — | — | q3 | No |
| q3 | — | — | — | **Sí** |

**Código en `lexer.py` (línea 139):**

```python
def t_NOTE(t):
    r"[A-Ga-g][#b]?[0-9]"
    t.value = t.value.upper()   # normalizar: c4 → C4, eb3 → EB3
    return t
```

La función hace una acción extra después del reconocimiento: normaliza el valor a mayúsculas. Así `c4`, `C4` y `c4` producen el mismo token `NOTE("C4")`.

**Ejemplos de cadenas:**

| Entrada | q0→q1 | q1→? | Resultado |
| --- | --- | --- | --- |
| `C4` | C | 4 → q3 | ✓ ACEPTA |
| `D#3` | D | # → q2, 3 → q3 | ✓ ACEPTA |
| `Eb5` | E | b → q2, 5 → q3 | ✓ ACEPTA |
| `G` | G | (fin) | ✗ RECHAZA (falta octava) |
| `bass` | b | a → muerto | ✗ RECHAZA (no es nota) |

---

#### Token NUMBER — Número entero

**Expresión regular en el código:** `[0-9]+`

**AFD (2 estados):**

```text
            [0-9]          [0-9]
    → q0 ─────────→ q1* ──────────→ q1*  (bucle)
```

El `+` ("uno o más") se representa en el AFD como un estado de aceptación con bucle: al menos una transición es obligatoria, y luego puede haber tantas como quiera.

**Código en `lexer.py` (línea 150):**

```python
def t_NUMBER(t):
    r"[0-9]+"
    t.value = int(t.value)   # "120" → 120  (string a entero Python)
    return t
```

La acción convierte el lexema string a un entero Python. Cuando el generador MIDI lee `tok_list[j+1].value`, ya recibe un `int`, no un string.

---

#### Token IDENTIFIER — Identificador de usuario

**Expresión regular en el código:** `[a-zA-Z_][a-zA-Z0-9_]*`

**AFD (2 estados):**

```
        [a-zA-Z_]        [a-zA-Z0-9_]
→ q0 ──────────────→ q1* ──────────────→ q1*  (bucle)
```

El primer carácter debe ser letra o guión bajo (no dígito). Luego puede seguir cualquier combinación de letras, dígitos y guiones bajos.

**Código en `lexer.py` (línea 164):**

```python
def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    token_type = RESERVED.get(t.value.lower(), "IDENTIFIER")
    t.type  = token_type
    t.value = t.value.lower() if token_type != "IDENTIFIER" else t.value
    return t
```

Este es el autómata **más general**: captura cualquier palabra alfabética. Después del reconocimiento consulta `RESERVED`. Si la palabra está ahí, cambia el tipo; si no, queda como `IDENTIFIER`. También convierte el lexema a minúsculas para los tokens reservados (para aceptar `Tempo` o `TEMPO` igual que `tempo`), pero deja sin cambiar los identificadores de usuario (preserva `melodia`, `Melodia`, `Track1` como fueron escritos).

**Ejemplos de clasificación:**

| Lexema capturado | `RESERVED.get(...)` | Tipo final |
| --- | --- | --- |
| `melodia` | `None` → default `"IDENTIFIER"` | IDENTIFIER |
| `tempo` | `"TEMPO_KW"` | TEMPO_KW |
| `negra` | `"DURATION"` | DURATION |
| `piano` | `"INSTR_NAME"` | INSTR_NAME |
| `negraa` | `None` → `"IDENTIFIER"` | IDENTIFIER (typo, error semántico) |

---

#### Token COMMENT — Comentario

**Expresión regular en el código:** `\#[^\n]*`

"Un `#` seguido de cualquier carácter que no sea salto de línea, cero o más veces."

**AFD:**

```text
         [#]          [^\n]
→ q0 ─────────→ q1* ──────────→ q1*  (bucle hasta newline)
```

**Código en `lexer.py` (línea 173):**

```python
def t_COMMENT(t):
    r"\#[^\n]*"
    pass   # no retorna → el token es descartado
```

La función no retorna `t`. En PLY, cuando una función de regla no retorna nada, el token se descarta. Los comentarios nunca llegan a la lista de tokens ni al generador MIDI.

---

#### Tokens LBRACE y RBRACE — Llaves

**Expresiones regulares en el código:** `\{` y `\}` (como strings, no funciones)

```python
t_LBRACE = r"\{"
t_RBRACE = r"\}"
```

Se definen como **strings** en lugar de funciones porque no necesitan acción adicional: el token se crea automáticamente con el carácter como valor. Son autómatas de dos estados triviales:

```
→ q0 ─── { ───→ q1*   (LBRACE)
→ q0 ─── } ───→ q1*   (RBRACE)
```

---

#### Salto de línea — Tracking de líneas

**Expresión regular en el código:** `\n+`

No genera token, pero es necesario para que los mensajes de error reporten la línea correcta:

```python
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    # No retorna → token descartado
```

`t.lexer.lineno` es el contador interno de PLY. Cada vez que el lexer cruza uno o más saltos de línea, se incrementa en la cantidad correspondiente. Así cuando ocurre un error en la línea 15, el mensaje dice "Línea 15" y no siempre "Línea 1".

---

#### Caracteres ignorados

```python
t_ignore = " \t\r"
```

Espacios, tabulaciones y retornos de carro se descartan **sin siquiera invocar una función**. PLY los filtra antes de intentar aplicar cualquier regla. En términos de autómatas, esto equivale a que el autómata unificado simplemente ignora estos caracteres entre tokens.

---

### 3.7 Construcción de Thompson: regex → AFN

La **Construcción de Thompson** es el algoritmo estándar para convertir una expresión regular a un AFN equivalente. Fue publicado por Ken Thompson en 1968 y es la base de herramientas como `grep` y PLY.

La idea central es construir AFNs pequeños para las ERs básicas y combinarlos con reglas de composición.

#### Construcción base

**Un solo carácter `a`:**

```
→ q₀ ── a ──→ q₁*
```

**ε (cadena vacía):**

```
→ q₀ ── ε ──→ q₁*
```

#### Operaciones de composición

Sean r₁ y r₂ dos ERs con sus AFNs N(r₁) y N(r₂):

**Concatenación r₁r₂:**

```text
→ [N(r₁)] ──ε──→ [N(r₂)]
```

La aceptación de N(r₁) se conecta por ε al inicio de N(r₂).

**Unión r₁|r₂:**

```text
           ──ε──→ [N(r₁)] ──ε──→
→ q_new                           q_final*
           ──ε──→ [N(r₂)] ──ε──→
```

Un nuevo estado inicial tiene ε a ambos, sus estados de aceptación tienen ε al nuevo estado final.

**Cerradura de Kleene r*:**

```
           ──────────────────────ε (vuelta)────────────
          ↑                                            │
→ q_i ──ε──→ [N(r)] ──ε──→ q_f*
      │                                               ↑
      └──────────────────────ε (skip)────────────────
```

Un estado inicial con ε al cuerpo del AFN y ε directo al final (para cero ocurrencias). El final del cuerpo tiene ε de regreso al inicio (para repetir) y ε al final.

**Opcional r? = r|ε:**

```
→ q_i ──ε──→ [N(r)] ──ε──→ q_f*
      │                          ↑
      └──────────ε (skip)────────┘
```

#### Aplicación al token NOTE: `[A-Ga-g][#b]?[0-9]`

Desglosando la regex:

```text
r₁ = [A-Ga-g]         (clase = A | B | C | D | E | F | G | a | b | ... | g)
r₂ = [#b]?            (opcional = [#b] | ε)
r₃ = [0-9]            (clase = 0 | 1 | ... | 9)

NOTE = r₁ · r₂ · r₃  (concatenación de las tres partes)
```

AFN resultante (simplificado, usando ε para el opcional):

```
q0 ──[A-Ga-g]──→ q1 ──[#b]──→ q2 ──[0-9]──→ q4*
                  │                            ↑
                  └───────────ε───────────→ q3 ──[0-9]──→ q4*
```

Los estados q2 y q3 son equivalentes después de ε-cerradura — ambos esperan un dígito para llegar al estado de aceptación q4.

---

### 3.8 Construcción de subconjuntos: AFN → AFD

La **Construcción de subconjuntos** (también llamada determinización) convierte un AFN a un AFD equivalente. El AFD resultante puede tener exponencialmente más estados que el AFN, pero en la práctica esto rara vez ocurre.

#### El algoritmo

Cada **estado del AFD** corresponde a un **subconjunto de estados del AFN** que podrían estar activos simultáneamente.

Se definen dos operaciones:

- **ε-cerradura(T)**: el conjunto de estados alcanzables desde cualquier estado en T siguiendo solo transiciones ε.
- **mover(T, c)**: el conjunto de estados alcanzables desde cualquier estado en T siguiendo una transición con el carácter c.

El algoritmo:

1. Estado inicial del AFD = ε-cerradura({q₀_AFN})
2. Para cada estado S del AFD y cada símbolo c ∈ Σ: calcular ε-cerradura(mover(S, c))
3. Si el resultado es un conjunto nuevo, agregarlo como nuevo estado del AFD
4. Repetir hasta que no haya estados nuevos
5. Un estado del AFD es de aceptación si contiene algún estado de aceptación del AFN

#### Aplicación al token NOTE

El AFN tiene 5 estados: {q0, q1, q2, q3, q4} donde q4 es el estado de aceptación.

Transiciones del AFN:

```
q0 ──[A-Ga-g]──→ {q1}
q1 ──[#b]──────→ {q2}
q1 ──ε─────────→ {q3}   (camino sin alteración)
q2 ──[0-9]─────→ {q4}*
q3 ──[0-9]─────→ {q4}*
```

**Paso 1:** Estado inicial AFD = ε-cerradura({q0}) = **{q0}** (no hay ε desde q0)

**Paso 2:** Desde {q0} con [A-Ga-g]:

- mover({q0}, [A-Ga-g]) = {q1}
- ε-cerradura({q1}) = {q1, q3}   (q1 tiene ε a q3)
- Nuevo estado AFD: **A = {q1, q3}**

**Paso 3:** Desde A={q1,q3} con [#b]:

- mover({q1,q3}, [#b]) = {q2}   (solo q1 tiene transición [#b])
- ε-cerradura({q2}) = **{q2}**
- Nuevo estado AFD: **B = {q2}**

**Paso 4:** Desde A={q1,q3} con [0-9]:

- mover({q1,q3}, [0-9]) = {q4}   (q3 tiene transición [0-9])
- ε-cerradura({q4}) = **{q4}**
- Nuevo estado AFD: **C = {q4}** ← contiene q4 → **estado de aceptación**

**Paso 5:** Desde B={q2} con [0-9]:

- mover({q2}, [0-9]) = {q4}
- ε-cerradura({q4}) = **{q4}** = C ← ya existe

**AFD resultante:**

```
Estados: {q0}, A={q1,q3}, B={q2}, C={q4}*

        [A-Ga-g]        [#b]       [0-9]
→ {q0} ──────────→ A ──────────→ B ──────────→ C*
                    │                            ↑
                    └──────────[0-9]─────────────┘
```

Este es exactamente el AFD de 4 estados mostrado en la sección 3.6 — solo que ahora sabemos de dónde viene cada estado.

---

### 3.9 Cómo PLY construye el lexer internamente

PLY no construye un AFD separado por cada token — construye **un solo AFD** que reconoce todos los tokens del lenguaje simultáneamente. Esto es más eficiente porque un solo pasaje por la cadena de entrada reconoce cualquier token.

**El proceso interno de PLY:**

```text
1. Lee todas las reglas léxicas (funciones t_* y strings t_*)

2. Convierte cada regex a un AFN usando Thompson

3. Une todos los AFNs con un nuevo estado inicial y transiciones ε:
      q0 ──ε──→ AFN(t_NOTE)
      q0 ──ε──→ AFN(t_NUMBER)
      q0 ──ε──→ AFN(t_IDENTIFIER)
      q0 ──ε──→ AFN(t_COMMENT)
      q0 ──ε──→ AFN(t_LBRACE)
      q0 ──ε──→ AFN(t_RBRACE)
      ...etc

4. Aplica construcción de subconjuntos al AFN unificado → AFD

5. Minimiza el AFD (algoritmo de Hopcroft)

6. El AFD resultante reconoce cualquier token en O(n)
   donde n es la longitud de la entrada
```

**¿Cómo sabe PLY qué token reconoció?**

En el AFD unificado, cada estado de aceptación tiene una **etiqueta** con el nombre del token. Si múltiples tokens podrían aceptar (como `tempo` que coincide con IDENTIFIER y con la ruta hacia TEMPO_KW), PLY aplica sus reglas de prioridad (ver sección 3.10).

PLY también implementa la política de **"maximal munch"** (longest match): siempre captura el lexema más largo posible. Por eso `tempo` no se tokeniza como `t` + `empo`, sino como `tempo` completo.

---

### 3.10 Prioridad de reglas en PLY

PLY tiene reglas específicas de prioridad que son **críticas** para que el lexer funcione correctamente:

**Regla 1 — Funciones:** se ordenan por posición en el archivo (más arriba = mayor prioridad).

**Regla 2 — Strings:** se ordenan por longitud del regex (más larga = mayor prioridad).

**El orden en `beatscript/lexer.py`:**

```
Línea 127: t_LBRACE, t_RBRACE  → strings (prioridad por longitud, ambas len=2)
Línea 139: def t_NOTE(t)       → ALTA PRIORIDAD (primera función)
Línea 150: def t_NUMBER(t)     → MEDIA PRIORIDAD
Línea 164: def t_IDENTIFIER(t) → BAJA PRIORIDAD (última función)
```

**¿Por qué este orden importa?**

Caso 1 — `C4`:

- IDENTIFIER regex `[a-zA-Z_][a-zA-Z0-9_]*` aceptaría `C4` como un identificador.
- NOTE regex `[A-Ga-g][#b]?[0-9]` también lo acepta.
- Como `t_NOTE` está antes que `t_IDENTIFIER` en el archivo, **NOTE gana**.

Caso 2 — `bass`:

- NOTE regex necesita que la segunda posición sea `#`, `b` seguido de dígito, o directamente un dígito.
- `bass` = `b` + `a`... `a` no es `#`, `b` ni dígito, entonces el regex de NOTE **no avanza** — el AFD queda en estado muerto.
- IDENTIFIER acepta `bass`, luego RESERVED lo convierte a `INSTR_NAME`.

Caso 3 — `tempo`:

- IDENTIFIER captura `tempo`, RESERVED lo convierte a TEMPO_KW.
- El usuario nunca puede usar `tempo` como nombre de track — sería un error léxico imposible de producir (el lexer siempre lo clasifica como keyword).

---

### 3.11 Manejo de errores léxicos

Cuando el lexer encuentra un carácter que no encaja en ninguna regla, PLY llama automáticamente a la función `t_error`.

#### La función t_error

**Código en `lexer.py` (línea 191):**

```python
def t_error(t):
    col  = _find_column(t.lexer.lexdata, t)
    char = t.value[0]
    msg  = _build_error_msg(char, t.lineno, col)
    if hasattr(t.lexer, "error_list"):
        t.lexer.error_list.append({"line": t.lineno, "col": col, "char": char, "msg": msg})
    else:
        print(msg)
    t.lexer.skip(1)
```

Paso a paso:

1. `t.value[0]` — extrae el carácter inválido (el primero de la cadena restante).
2. `_find_column(...)` — calcula en qué columna de la línea está.
3. `_build_error_msg(...)` — construye el mensaje descriptivo.
4. Si el lexer tiene `error_list` → acumula el error (modo GUI). Si no → imprime directo (modo consola).
5. `t.lexer.skip(1)` — avanza un carácter y continúa. El lexer **no se detiene**, sigue buscando errores adicionales.

#### Diccionario _ERROR_HINTS

```python
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
```

Si el carácter no está en el diccionario, el mensaje genérico es: `'X' no pertenece al alfabeto de BeatScript.`

```python
def _build_error_msg(char: str, line: int, col: int) -> str:
    hint = _ERROR_HINTS.get(char, f"'{char}' no pertenece al alfabeto de BeatScript.")
    return f"[ERROR LÉXICO] Línea {line}, Col {col}: carácter '{char}' no reconocido — {hint}"
```

**Ejemplo de mensaje producido:**

```
[ERROR LÉXICO] Línea 3, Col 8: carácter ',' no reconocido — Separa notas con espacios, no con comas: C4 E4 G4 blanca
```

#### Cálculo de columna

**Código en `lexer.py` (línea 243):**

```python
def _find_column(source: str, token) -> int:
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return token.lexpos - line_start + 1
```

- `token.lexpos` es la posición **absoluta** del carácter en toda la cadena fuente (índice 0 al final).
- `source.rfind("\n", 0, token.lexpos)` busca hacia atrás el último `\n` antes de esa posición. Si no hay ninguno, retorna -1.
- `+ 1` da el inicio de la línea actual (el carácter justo después del `\n`).
- La resta `lexpos - line_start + 1` da la posición dentro de la línea (columna 1-indexada).

**Ejemplo:** si la cadena fuente es `"tempo 120\nC4,negra"` y el error es en la coma (posición 13):

```
"tempo 120\nC4,negra"
 0123456789^10^11^12^13

lexpos = 13
rfind("\n", 0, 13) = 9   (el \n está en posición 9)
line_start = 9 + 1 = 10
columna = 13 - 10 + 1 = 4   → Línea 2, Col 4
```

---

### 3.12 API pública del lexer

El módulo `lexer.py` expone tres funciones públicas que usa el resto del proyecto.

#### build_lexer()

```python
def build_lexer() -> lex.Lexer:
    """Construye y retorna el objeto lexer de PLY."""
    return lex.lex()
```

`lex.lex()` es la función de PLY que lee todas las reglas del módulo actual (las funciones `t_*` y strings `t_*`), aplica el pipeline Thompson → subconjuntos → Hopcroft, y retorna un objeto `Lexer` listo para usar.

Esta función se llama **cada vez** que se quiere tokenizar un nuevo programa, para garantizar que el lexer empiece en estado limpio (sin residuos del código anterior).

#### tokenize()

```python
def tokenize(source_code: str, *, debug: bool = False, collect_errors: bool = False):
```

Es la función principal que usa la GUI. Tiene dos modos de operación:

**Modo normal** (`collect_errors=False`):

```python
tokens = tokenize("tempo 120\nC4 negra")
# retorna: [LexToken(TEMPO_KW,'tempo',1,0), LexToken(NUMBER,120,1,6), ...]
```

**Modo recolección de errores** (`collect_errors=True`):

```python
tokens, errors = tokenize("tempo 120\n@C4 negra", collect_errors=True)
# tokens: tokens válidos encontrados antes y después del error
# errors: [{"line": 2, "col": 1, "char": "@", "msg": "[ERROR LÉXICO]..."}]
```

**Implementación interna:**

```python
def tokenize(source_code: str, *, debug: bool = False, collect_errors: bool = False):
    errors = []
    lx = build_lexer()
    lx.error_list = errors      # ← conecta t_error con esta lista
    lx.input(source_code)       # ← alimenta el código al lexer

    result = list(lx)           # ← itera el lexer hasta EOF, produce tokens

    if debug:
        _print_token_table(result, source_code)

    if collect_errors:
        return result, errors
    return result
```

La línea `lx.error_list = errors` es el mecanismo que conecta `t_error` con la lista local: cuando `t_error` verifica `hasattr(t.lexer, "error_list")`, encuentra el atributo y añade el error a la lista en vez de imprimirlo. Esto permite que la GUI acumule **todos** los errores del programa de una sola pasada.

`list(lx)` itera el objeto lexer hasta que retorna `None` (fin de entrada). Cada iteración lee el siguiente token del AFD unificado.

#### _print_token_table() — modo debug

```python
def _print_token_table(token_list: list, source: str = "") -> None:
```

Imprime una tabla formateada en consola. Útil para desarrollo y para el bloque `__main__` al ejecutar `python beatscript/lexer.py` directamente:

```text
====================================================================
              TABLA DE TOKENS — BeatScript Lexer
====================================================================
#     TIPO               VALOR                LÍNEA   COL
--------------------------------------------------------------------
1     TEMPO_KW           tempo                1       1
2     NUMBER             120                  1       7
3     INSTRUMENT_KW      instrument           3       1
4     INSTR_NAME         piano                3       12
...
====================================================================
  Total: 14 tokens
====================================================================
```

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

Nótese que D=2 (no 1) y E=4 (no 3) porque entre Do-Re y Re-Mi existe un semitono que no tiene nombre en el sistema de notas naturales — eso explica por qué no hay tecla negra entre E y F en un piano.

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

```text
MIDI = NOTE_SEMITONES[letra] + (octava + 1) × 12 + ajuste_alteración
```

El `+1` en la octava se debe a que MIDI define C-1 (octava -1) como nota 0. Por eso C0 = 12, C1 = 24, C4 = 60.

**Implementación:**

```python
def note_to_midi(note_str: str) -> int:
    s      = note_str.upper()
    letter = s[0]
    rest   = s[1:]
    if rest and rest[0] in ('#', 'B') and len(rest) > 1:
        alt, octave = rest[0], int(rest[1])
    else:
        alt, octave = '', int(rest[0])

    pitch = NOTE_SEMITONES[letter] + (octave + 1) * 12
    if alt == '#': pitch += 1   # sostenido
    if alt == 'B': pitch -= 1   # bemol
    return pitch
```

**Ejemplos:**

| Nota | Cálculo | MIDI |
| --- | --- | --- |
| `C4` | 0 + (4+1)×12 = 60 | 60 |
| `D#3` | 2 + (3+1)×12 + 1 = 51 | 51 |
| `EB5` | 4 + (5+1)×12 − 1 = 75 | 75 |
| `G0` | 7 + (0+1)×12 = 19 | 19 |

### 4.3 Máquina de estados para procesar tokens

**Función:** `tokens_to_midi(tokens, output_path)`

El generador implementa una **máquina de estados** que recorre la lista de tokens en orden, manteniendo estado global del contexto actual.

```text
Estado global:
  tempo    = 120 BPM
  program  = 0 (piano)
  velocity = 80 (volumen)
  t        = 0.0 (tiempo actual en el MIDI, en beats)
```

La función interna `process(tok_list, t)` es **recursiva**: cuando encuentra un bloque `track {}`, `repeat {}` o `chord {}`, extrae los tokens del interior y se llama a sí misma con esos tokens.

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
    VOLUME_KW  ──→ lee NUMBER → velocity = min(127, val)   │
         │                                                  │
    TEMPO_KW   ──→ lee NUMBER → tempo = val                │
                   → addTempo() en el MIDI                  │
         │                                                  │
    INSTRUMENT_KW → lee INSTR_NAME → program = GM_num      │
                   → addProgramChange() en el MIDI          │
         │                                                  │
    TRACK_KW   ──→ busca LBRACE → extrae bloque             │
                   → process(bloque, t) recursivamente      │
         │                                                  │
    REPEAT_KW  ──→ lee N → extrae bloque                   │
                   → process(bloque, t) × N veces           │
         │                                                  │
    CHORD_KW   ──→ extrae bloque → busca todas las NOTEs   │
                   → busca última DURATION                  │
                   → addNote() por cada nota simultánea     │
                   → t += duración                          │
         │                                                  │
    NOTE ─────────→ lee DURATION opcional                  │
                   → addNote() en el MIDI                   │
                   → t += duración                          │
         │                                                  │
    REST ─────────→ lee DURATION opcional                  │
                   → solo avanza t (silencio)               │
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

```text
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

Este algoritmo es un reconocedor de **lenguaje de paréntesis balanceados** — el ejemplo clásico de lenguaje que es libre de contexto pero no regular. Requiere "memoria" (la variable `depth` actúa como pila) para contar el anidamiento.

---

## 5. Interfaz Gráfica (IDE)

**Archivo:** `main_gui.py`

### 5.1 Estructura de la ventana

La GUI usa **customtkinter** (versión mejorada de tkinter con tema oscuro) y **tkinter.ttk** para tablas.

```
┌────────────────────────────────────────────────────────────────────┐
│  BeatScript IDE   [▶ Compilar y Reproducir]  [⏹ Detener]          │
│                   [Ver Detalles Extra]                              │  ← Barra superior
├───────────────────────────────────┬────────────────────────────────┤
│                                   │                                │
│       Editor de código            │   Árbol Sintáctico             │
│       (CTkTextbox)                │   (placeholder Etapa 2)        │
│       Fuente: Consolas 13pt       │   (ttk.Treeview)               │
│       Sin ajuste de línea         │   Columnas: Nodo / Tipo / Valor│
│                                   │                                │
├───────────────────────────────────┴────────────────────────────────┤
│  Consola                                                           │
│  (mensajes de compilación, errores, estado de reproducción)        │
└────────────────────────────────────────────────────────────────────┘
```

**Componentes clave:**

| Atributo | Tipo | Descripción |
| --- | --- | --- |
| `self.editor` | `CTkTextbox` | Área de edición del código fuente |
| `self.tabla_ast` | `ttk.Treeview` | Tabla del árbol sintáctico (Etapa 2, por ahora vacía) |
| `self.consola` | `CTkTextbox` | Salida de mensajes del compilador |

### 5.2 Flujo de compilación

Cuando el usuario presiona **▶ Compilar y Reproducir**, se ejecuta `_compilar()`:

```python
def _compilar(self):
    # 1. Limpiar consola
    self._log("", clear=True)

    # 2. Obtener código del editor
    source = self.editor.get("1.0", "end-1c").strip()
    if not source:
        self._log("⚠  El editor está vacío.")
        return

    self._log("▶  Iniciando análisis léxico...")

    # 3. Ejecutar el lexer
    tokens, errors = tokenize(source, collect_errors=True)

    # 4. Si hay errores léxicos → mostrar y PARAR
    if errors:
        for err in errors:
            self._log(f"✗  {err['msg']}")
        self._log(f"\n✗  Compilación detenida — {len(errors)} error(es) léxico(s).")
        return

    # 5. Validación semántica adicional → PARAR si hay problemas
    avisos = self._validar_tokens_extra(tokens, source)
    if avisos:
        for av in avisos:
            self._log(f"✗  {av}")
        self._log(f"\n✗  Compilación detenida — {len(avisos)} error(es) de validación.")
        return

    # 6. Éxito — reportar y continuar
    self._log(f"✔  Análisis léxico completado — {len(tokens)} tokens encontrados.")

    # 7. Generar MIDI y reproducir
    midi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.mid")
    tokens_to_midi(tokens, midi_path)
    pygame.mixer.music.load(midi_path)
    pygame.mixer.music.play()
    self._log("♪  Reproduciendo output.mid ...")
```

**Comportamiento ante errores:**

- Si el lexer encuentra un carácter inválido → se detiene, muestra el error, no genera MIDI.
- Si la validación semántica encuentra un problema → se detiene, muestra el error, no genera MIDI.
- Solo llega a generar MIDI si ambas validaciones pasan limpiamente.

### 5.3 Validación semántica adicional

El lexer solo verifica que los caracteres formen tokens reconocibles. Hay errores que el lexer acepta porque los caracteres son válidos, pero que no tienen sentido musical. El método `_validar_tokens_extra()` los detecta revisando **pares de tokens consecutivos**:

**Regla 1 — Instrumento desconocido:**

```text
instrument xyz  →  ERROR: 'xyz' no es un instrumento reconocido
```

`INSTRUMENT_KW` seguido de `IDENTIFIER` (no `INSTR_NAME`) → el nombre no está en la tabla MIDI.

**Regla 2 — Tempo sin número:**

```text
tempo allegro  →  ERROR: se esperaba un número después de 'tempo'
```

`TEMPO_KW` seguido de cualquier token que no sea `NUMBER`.

**Regla 3 — Volumen fuera de rango:**

```
volume 200  →  ERROR: volumen 200 fuera de rango (0-127)
```

`VOLUME_KW` + `NUMBER` con valor fuera de [0, 127].

**Regla 4 — Duración inválida:**

```
C4 rapidito  →  ERROR: 'rapidito' no es una duración válida
```

`NOTE` o `REST` seguido de `IDENTIFIER` (no `DURATION`). Captura typos como `negraa`, `blancaa`.

**Regla 5 — Nota mal formada:**

```
C4x  →  AVISO: 'C4x' parece una nota inválida
```

`IDENTIFIER` que coincide con el patrón `^[A-Ga-g].+\d$` — empieza como nota pero tiene caracteres de más.

---

## 6. Suite de pruebas

**Archivo:** `beatscript/tests/test_lexer.py`

El proyecto incluye **74 pruebas automáticas** usando `pytest`. Cubren:

| Grupo de pruebas | Cantidad | Qué verifica |
| --- | --- | --- |
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

El lexer llama a `tokenize(source, collect_errors=True)`. Internamente `lex.lex()` construye el AFD unificado y `list(lx)` lo recorre carácter a carácter. El resultado es:

| # | Tipo | Valor | Línea | Col |
| --- | --- | --- | --- | --- |
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

Saltos de línea y espacios son descartados por `t_ignore`. Los comentarios tampoco aparecen porque `t_COMMENT` no retorna.

### Paso 2: Validación semántica

La GUI revisa los pares de tokens con `_validar_tokens_extra()`. En este código:

- `TEMPO_KW → NUMBER` ✓
- `INSTRUMENT_KW → INSTR_NAME` ✓ (`piano` existe en la tabla MIDI)
- No hay NOTE seguida de IDENTIFIER ✓

Sin errores — continúa al paso 3.

### Paso 3: Generación MIDI

`tokens_to_midi` procesa los tokens con su máquina de estados:

1. `TEMPO_KW + NUMBER(120)` → `midi.addTempo(track, 0, 120)`
2. `INSTRUMENT_KW + INSTR_NAME(piano)` → `midi.addProgramChange(track, channel, 0, program=0)`
3. `TRACK_KW + IDENTIFIER(melodia) + LBRACE` → `_collect_block()` busca el `}` correspondiente, extrae el bloque interno
4. Dentro del bloque (t=0.0):
   - `NOTE(C4) + DURATION(negra)`:
     - `note_to_midi("C4")` = 0 + (4+1)×12 = **60**
     - `DURATION_BEATS["negra"]` = **1.0**
     - `midi.addNote(0, 0, 60, t=0.0, dur=1.0, vel=80)`
     - t = 1.0
   - `NOTE(E4) + DURATION(negra)`:
     - `note_to_midi("E4")` = 4 + (4+1)×12 = **64**
     - `midi.addNote(0, 0, 64, t=1.0, dur=1.0, vel=80)`
     - t = 2.0
   - `NOTE(G4) + DURATION(blanca)`:
     - `note_to_midi("G4")` = 7 + (4+1)×12 = **67**
     - `DURATION_BEATS["blanca"]` = **2.0**
     - `midi.addNote(0, 0, 67, t=2.0, dur=2.0, vel=80)`
     - t = 4.0

### Paso 4: Escritura del archivo

```python
with open("output.mid", "wb") as f:
    midi.writeFile(f)
```

`MIDIFile` serializa los eventos en el formato binario estándar MIDI (estructura de chunk `MThd` + `MTrk` con eventos time-stamped).

### Paso 5: Reproducción

```python
pygame.mixer.music.load("output.mid")
pygame.mixer.music.play()
```

pygame usa el sintetizador del sistema operativo para reproducir el archivo MIDI.

---

## 8. Dependencias y tecnologías

| Librería | Versión mínima | Para qué se usa |
| --- | --- | --- |
| `ply` | ≥ 3.11 | Framework para construir lexers. Implementa internamente Thompson + subconjuntos para convertir las reglas regex a un AFD eficiente. |
| `midiutil` | ≥ 1.2.1 | Serialización de eventos musicales al formato binario MIDI. |
| `customtkinter` | ≥ 5.2.0 | Widget toolkit para la GUI con tema oscuro moderno. |
| `pygame-ce` | ≥ 2.5.0 | Módulo `mixer` para reproducir archivos MIDI. |

**Relación de PLY con la materia:**

PLY (Python Lex-Yacc) es un port en Python de las herramientas clásicas de Unix `lex` y `yacc`. La parte `ply.lex` implementa exactamente el pipeline teórico estudiado en Lenguajes y Autómatas:

```text
Reglas regex del programador
        ↓ Thompson
    AFN por token
        ↓ Unión con ε-transiciones
    AFN unificado
        ↓ Construcción de subconjuntos
    AFD equivalente
        ↓ Minimización (Hopcroft)
    AFD mínimo
        ↓ Tabla de transiciones
    Lexer ejecutable en O(n)
```

Este pipeline es lo que ocurre cuando se llama a `lex.lex()` en `build_lexer()`. El resultado es el objeto `Lexer` que `tokenize()` usa para procesar cualquier programa BeatScript.

---

*Documentación técnica del proyecto BeatScript — Lenguajes y Autómatas I, 6to semestre.*
