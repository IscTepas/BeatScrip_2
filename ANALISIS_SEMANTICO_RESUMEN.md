# Análisis Semántico en BeatScript — guía de estudio

Este documento explica `semantic.py`: qué es el análisis semántico, qué son las acciones semánticas, la tabla de símbolos, cada una de las 8 reglas (S1–S8) con ejemplos válidos e inválidos, y el funcionamiento de cada método del archivo.

> Convenciones usadas en este documento: cuando digo "como en Java" me refiero a un concepto equivalente que probablemente ya conoces. `self` en Python es lo mismo que `this` en Java. Un `dict` es un `HashMap`. Una clase con `@dataclass` es básicamente un *record*/POJO: Python genera el constructor por ti a partir de los atributos declarados.

---

## 1. ¿Qué es el análisis semántico?

En cualquier compilador hay (al menos) tres preguntas distintas que se le hacen al código fuente, en este orden:

| Etapa | Pregunta que responde | Ejemplo de fallo que detecta |
|-------|------------------------|-------------------------------|
| Léxico | ¿Estos caracteres forman palabras válidas del lenguaje? | `tempo @120` → `@` no es un carácter válido |
| Sintáctico | ¿Las palabras están en un orden gramaticalmente válido? | `tempo` (sin número) → falta un argumento |
| **Semántico** | ¿Lo que se escribió **tiene sentido**? | `tempo 5000` → la gramática lo permite (es un número), pero 5000 BPM no es un tempo musical válido |

El parser (etapa sintáctica) solo sabe reconocer *forma*: sabe que después de `tempo` debe venir un `NUMBER`, pero no sabe ni le importa si ese número es razonable. El análisis semántico es la etapa que entiende el **significado** de lo que ya se comprobó que está bien escrito: rangos válidos, nombres únicos, coherencia entre partes del programa que están lejos una de otra (ej. un `track` usado dos veces, aunque esté en otra parte del archivo).

Por eso el análisis semántico **no trabaja sobre los tokens ni sobre el texto** — trabaja sobre el **AST** (el árbol que construyó el parser), porque ya necesita ver la estructura completa, no solo una secuencia plana de palabras.

---

## 2. ¿Qué son las "acciones semánticas"?

En la teoría de compiladores, una **acción semántica** es un fragmento de código que se ejecuta cuando se reconoce una construcción del lenguaje, y que **calcula o verifica algo sobre su significado** (en vez de solo verificar su forma). En muchos compiladores "de libro", estas acciones se escriben directamente embebidas en las reglas de la gramática (eso se llama **traducción dirigida por la sintaxis**, *syntax-directed translation*): cada regla gramatical lleva pegado un trozo de código que se ejecuta en el momento en que esa regla se reconoce durante el parseo.

**En BeatScript estas acciones existen, pero están separadas en una segunda pasada** en vez de ir pegadas al parser: primero se construye el AST completo (etapa sintáctica, sin ninguna validación de significado), y *después* `SemanticAnalyzer` recorre ese árbol ya construido aplicando una acción semántica por cada tipo de nodo. Esto se llama más precisamente **traducción dirigida por el árbol de sintaxis** (una variante igual de válida y muy común en compiladores reales, porque simplifica tener un solo recorrido claro en vez de mezclar gramática y semántica).

Las acciones semánticas de este proyecto son, concretamente, los métodos privados de `SemanticAnalyzer` — cada uno es la "acción" asociada a un tipo de nodo del AST:

| Nodo del AST | Acción semántica (método) | Qué hace la acción |
|---------------|----------------------------|----------------------|
| `Tempo` | `_tempo()` | valida el rango del BPM (S1) |
| `Volume` | `_volume()` | valida el rango del volumen (S2) |
| `Instrument` | (inline en `_visit`) | guarda el instrumento activo (no valida nada, solo actualiza estado) |
| `Track` | `_track()` | registra el track en la tabla de símbolos y valida duplicados (S5), dispara S7 |
| `Repeat` | `_repeat()` | valida que el contador sea ≥ 1 (S4) |
| `Chord` | `_chord()` | valida notas, cantidad y posición de la duración (S3, S6, S8) |
| `Note` | `_note()` | convierte la nota a MIDI y valida su rango (S3) |

Cada acción puede hacer dos cosas (igual que en un compilador real): **verificar una condición** (y reportar error/warning si falla) y/o **actualizar el estado acumulado** que necesitan las validaciones siguientes (como la tabla de símbolos, o qué instrumento está activo en este punto del recorrido).

---

## 3. La Tabla de Símbolos

Una **tabla de símbolos** es una estructura central en cualquier compilador: un registro de todo lo que el programa *declara* (variables, funciones, clases... en BeatScript, **tracks**), para poder comprobar más adelante cosas como "¿ya existe algo con este nombre?" sin tener que volver a recorrer todo el árbol desde cero cada vez.

```python
class SymbolTable:
    def __init__(self):
        self._symbols: dict[str, Symbol] = {}   # equivalente a HashMap<String, Symbol>
```

Cada entrada es un `Symbol` ([semantic.py](beatscript/semantic.py)), que guarda:

| Campo | Significado |
|-------|-------------|
| `name` | nombre del track |
| `kind` | tipo de símbolo (siempre `"track"` en este proyecto; se deja el campo por si en el futuro hay otros tipos) |
| `line`, `col` | dónde se declaró, para señalar duplicados |
| `instrument` | qué instrumento estaba activo cuando se declaró (con `"*"` si fue el valor por defecto, no uno explícito) |
| `events` | cuántos eventos tiene directamente ese track |

El método clave es `define()`:

```python
def define(self, symbol: Symbol):
    previo = self._symbols.get(symbol.name)
    if previo is not None:
        return previo          # ya existía → devuelve el anterior (para reportar el duplicado)
    self._symbols[symbol.name] = symbol
    return None                 # no existía → quedó registrado
```

Esto es el mismo patrón que usarías para detectar "variable ya declarada" en un compilador de un lenguaje de propósito general — aquí, en vez de variables, son nombres de `track`.

---

## 4. Las reglas semánticas — catálogo completo (S1 a S8)

Cada regla tiene un código `S1`...`S8` (están descritas en el diccionario `SEMANTIC_ERRORS`, al inicio de [semantic.py](beatscript/semantic.py)). Son **8 reglas en total: 7 errores + 1 warning**.

### S1 — `tempo` debe estar en [20, 400]

- **Qué valida:** el BPM del `tempo` debe ser un entero razonable para música (20 a 400 beats por minuto).
- **Método:** `_tempo()`.
- ❌ Inválido: `tempo 0` / `tempo 5000`
- ✅ Válido: `tempo 20` / `tempo 120` / `tempo 400`
- **Mensaje real:** `BPM 5000 demasiado alto: debe estar entre 20 y 400`

### S2 — `volume` debe estar en [0, 127]

- **Qué valida:** el volumen (velocity MIDI) debe estar en el rango que el estándar MIDI permite.
- **Método:** `_volume()`.
- ❌ Inválido: `volume 150`
- ✅ Válido: `volume 0` / `volume 90` / `volume 127`
- *Nota:* `volume -5` ni siquiera llega hasta aquí — el **lexer** ya rechaza el `-` como carácter inválido (BeatScript no tiene números negativos).

### S3 — Toda nota debe caer en el rango MIDI [0, 127]

- **Qué valida:** después de convertir la nota a su número MIDI (con `pitch_to_midi`), el resultado debe estar entre 0 y 127 — el límite real del protocolo MIDI.
- **Método:** `_note()`. Se llama tanto para una `Note` suelta como para cada nota dentro de un `Chord`.
- ❌ Inválido: `C10` (= MIDI 132, se sale)
- ✅ Válido: `G9` (= MIDI 127, el límite exacto permitido)
- ❌ Inválido: `G#9` (= MIDI 128, un semitono más que el límite)
- **Cálculo:** `pitch_to_midi("C10")` = semitono de C (0) + (10+1)×12 = 132.

### S4 — `repeat N` exige N ≥ 1

- **Qué valida:** repetir un bloque 0 veces no tiene sentido (nunca se ejecutaría).
- **Método:** `_repeat()`.
- ❌ Inválido: `repeat 0 { C4 negra }`
- ✅ Válido: `repeat 1 { C4 negra }` / `repeat 2 { ... }`
- Aplica igual si el `repeat` está anidado dentro de un `track`.

### S5 — Nombres de `track` únicos

- **Qué valida:** no puede haber dos tracks con el mismo nombre — se detecta usando la tabla de símbolos.
- **Método:** `_track()`.
- ❌ Inválido:
  ```
  track melodia { C4 negra }
  track melodia { D4 negra }
  ```
  Mensaje: `track 'melodia' ya está definido (primera definición: línea 2, col 1)` — apunta a la primera declaración, no solo a la repetida.
- ✅ Válido: usar nombres distintos (`melodia`, `acompanamiento`, etc.)

### S6 — `chord` con ≥ 1 nota y exactamente 1 duración, al final

Esta regla en realidad agrupa **tres validaciones relacionadas** sobre la forma de un acorde:

1. El acorde debe tener al menos una nota.
2. Debe tener exactamente una duración (ni cero, ni dos).
3. Esa duración debe ir **al final** del bloque, después de todas las notas.

- **Método:** `_chord()`.
- ❌ Inválido: `chord { }` → sin notas
- ❌ Inválido: `chord { C4 E4 }` → sin duración
- ❌ Inválido: `chord { C4 E4 negra blanca }` → dos duraciones
- ❌ Inválido: `chord { C4 negra E4 }` → la duración apareció antes de terminar las notas
- ✅ Válido: `chord { C4 E4 G4 blanca }`

### S7 — Advertencia: usar notas sin haber definido `instrument` (warning, no error)

- **Qué valida:** si se escriben notas antes de cualquier `instrument`, BeatScript seguirá funcionando (usa `piano`, programa MIDI 0, por defecto), pero avisa por si fue un olvido.
- **Método:** `_warn_sin_instrumento()`, llamado desde `_track()` y `_chord()`.
- ⚠️ Genera warning: `track t { C4 negra }` (sin `instrument` antes)
- ✅ No genera nada: `instrument piano` antes del `track`
- **Es la única regla que es `Warning` y no `Error`** — por eso `result.errors` queda vacío pero `result.warnings` tiene 1 elemento. Un warning **no detiene la compilación**.

### S8 — Las notas dentro de un `chord` deben ser válidas musicalmente

- **Qué valida:** el parser, al leer un `chord`, acepta cualquier cosa con *forma* de nota (letra + número) aunque la letra no exista en la escala o la alteración sea rara, y la guarda como "nota inválida" (`invalid_notes`) en vez de rechazarla de inmediato. Esta regla es la que finalmente la rechaza con un mensaje claro.
- **Método:** `_chord()` (la parte que recorre `n.invalid_notes`).
- ❌ Inválido: `chord { H4 E4 blanca }` → `H` no es una letra musical válida (solo existen A-G)
- ✅ Válido: `chord { C4 E4 G4 blanca }`
- *Por qué existe aparte de S3:* S3 valida el **rango numérico** de una nota ya válida; S8 valida que la nota **exista** como tal antes de poder convertirla a número. Son chequeos distintos y complementarios.

### Resumen rápido

| Código | Severidad | En una frase |
|--------|-----------|---------------|
| S1 | Error | `tempo` fuera de 20–400 |
| S2 | Error | `volume` fuera de 0–127 |
| S3 | Error | nota fuera del rango MIDI 0–127 |
| S4 | Error | `repeat` con N < 1 |
| S5 | Error | nombre de `track` repetido |
| S6 | Error | `chord` mal formado (notas/duración) |
| S7 | **Warning** | falta `instrument` antes de usar notas |
| S8 | Error | nota con letra/alteración inválida dentro de un `chord` |

---

## 5. Clases del archivo, explicadas una por una

### `SemanticDiagnostic`
Representa **un** error o warning ya detectado: código de regla, severidad, línea, columna y mensaje. Su `__str__` arma el texto final que se muestra al usuario, con el formato `[ERROR SEMÁNTICO] Línea X, Col Y: mensaje (Sn)`.

### `Symbol` y `SymbolTable`
Ya explicados en la sección 3 — el registro de tracks declarados.

### `SemanticAnalyzer`
La clase principal. Guarda tres cosas mientras recorre el árbol:

- `self.diagnostics` — lista de todos los errores/warnings encontrados hasta ahora.
- `self.symbols` — la tabla de símbolos (los tracks vistos hasta ahora).
- `self._instrument` — qué instrumento está "activo" en este punto del recorrido (se actualiza cada vez que se pasa por un nodo `Instrument`; empieza en `None`).

---

## 6. Método por método — cómo funciona cada cosa

### `errors` y `warnings` (propiedades)
Son dos *filtros* sobre `self.diagnostics`: `errors` devuelve solo los de severidad `"Error"`, `warnings` solo los `"Warning"`. Son propiedades (`@property`) en vez de métodos normales para poder escribir `resultado.errors` sin paréntesis, como si fuera un atributo — es solo azúcar sintáctica de Python, no cambia la lógica.

### `_report(code, line, col, message)`
El único lugar del archivo donde se **crea** un `SemanticDiagnostic` y se agrega a la lista. Busca la severidad correcta en `SEMANTIC_ERRORS[code]` automáticamente, así los demás métodos solo necesitan pasar el código de regla (`"S1"`, `"S2"`...) sin tener que acordarse si es error o warning.

### `analyze(program)` — el punto de entrada
```python
def analyze(self, program):
    for stmt in program.statements:
        self._visit(stmt)
    self.diagnostics.sort(key=lambda d: (d.line or 0, d.col or 0))
    return self
```
Recorre cada sentencia de nivel superior del programa (`program.statements`, que viene del AST) y llama a `_visit()` por cada una. Al final, **ordena** los diagnósticos por línea y columna — esto es necesario porque, por ejemplo, un `chord` puede reportar varios errores internos en un orden distinto al de lectura; ordenarlos al final asegura que el usuario los vea en el mismo orden en que aparecen en su código, sin importar el orden en que el analizador los fue descubriendo.

### `_visit(node, top_level=True)` — el patrón Visitor
```python
def _visit(self, node, top_level=True):
    if isinstance(node, Tempo):        self._tempo(node)
    elif isinstance(node, Volume):     self._volume(node)
    elif isinstance(node, Instrument): self._instrument = node.name
    elif isinstance(node, Track):      self._track(node)
    ...
```
Este es el **patrón Visitor**: en vez de que cada clase de nodo (`Tempo`, `Track`, `Note`...) sepa cómo validarse a sí misma, hay **una** función externa que decide, según el tipo de nodo (`isinstance`), a qué método especializado delegar. Es el mismo patrón que usarías en Java con un `switch` sobre el tipo, o con una jerarquía de clases `Visitor`/`Visitable` si quisieras hacerlo más "orientado a objetos".

El parámetro `top_level` viaja junto con cada llamada para que algunas reglas (como S7) sepan si están mirando un nodo que cuelga directamente del programa o uno que está anidado dentro de un `track`/`repeat` — esto importa porque, por ejemplo, el warning de "falta instrument" solo tiene sentido reportarlo una vez por bloque de nivel superior, no por cada nota individual dentro de él.

### `_tempo(n)` / `_volume(n)` — las reglas más simples
Cada una es una sola comparación de rango (S1, S2). Si falla, construye un mensaje indicando si el valor fue "demasiado bajo" o "demasiado alto" y lo reporta con `_report()`. Usan `n.arg_line`/`n.arg_col` (no `n.line`/`n.col`) porque quieren señalar la posición del *número* (el argumento), no de la palabra clave `tempo`/`volume`.

### `_note(pitch, line, col)` — S3
Convierte el pitch (ej. `"C4"`) a número MIDI llamando a `pitch_to_midi()`, y verifica el rango 0-127. Está separado como una función que recibe `pitch/line/col` sueltos (en vez de un nodo `Note` completo) precisamente para poder **reutilizarla** tanto desde el visitor normal (nodo `Note`) como desde `_chord()` (una nota dentro de un acorde no es un nodo `Note`, es solo texto dentro de `n.notes`).

### `pitch_to_midi(pitch)` — la fórmula de conversión
```python
def pitch_to_midi(pitch: str) -> int:
    letra, alt, octava = _NOTE_RE.match(pitch.upper()).groups()
    return _SEMITONES[letra] + (int(octava) + 1) * 12 + (1 if alt == "#" else -1 if alt == "B" else 0)
```
Esta es la fórmula estándar de conversión nota→MIDI:
1. `_SEMITONES[letra]` da los semitonos de esa nota dentro de una octava (C=0, D=2, E=4, F=5, G=7, A=9, B=11 — son los semitonos de la escala, no hay D y D# intermedios como notas con letra propia).
2. `(octava + 1) * 12` ubica esa octava en la escala MIDI completa (el +1 es porque el estándar MIDI considera que la octava "0" empieza en C(-1), por eso C4 cae en 60 y no en 48).
3. Se suma +1 si hay sostenido (`#`) o se resta 1 si hay bemol (`B`, porque el lexer ya normalizó `b` a mayúscula).

Ejemplo paso a paso con `"D#3"`: letra=`D` (2) + (3+1)×12 (48) + 1 (sostenido) = **51**.

### `_repeat(n, top_level)` — S4
Primero valida que `n.count >= REPEAT_MIN` (1). Luego, **sin importar si la validación falló o no**, recorre cada evento dentro del cuerpo del repeat llamando a `_visit()` recursivamente — porque aunque el conteo sea inválido, igual hay que revisar que las notas de adentro sean válidas. Ojo: esto **no ejecuta el cuerpo N veces**; solo lo revisa una vez (la repetición real de eventos la hará la futura etapa de código intermedio o la actual `midi_gen.py`, no el análisis semántico).

### `_track(n)` — S5 + dispara S7
1. Calcula qué instrumento se va a registrar (`self._instrument` si hay uno activo, o `"piano*"` con asterisco si es el valor por defecto — el asterisco es solo una marca visual para la tabla de símbolos del IDE).
2. Llama a `self.symbols.define(...)` para registrar el track. Si ya existía uno con ese nombre, `define()` devuelve el símbolo anterior (no `None`), y entonces se reporta S5 señalando la línea de la *primera* definición.
3. Llama a `_warn_sin_instrumento()` (S7).
4. Recorre cada evento interno del track con `top_level=False` (porque ya no están "sueltos" en el programa, están dentro de un track).

### `_chord(n, top_level)` — S3 + S6 + S8
Es el método más largo porque un acorde tiene más piezas que validar que cualquier otra construcción:
1. Por cada nota válida del acorde, llama a `_note()` (reutilizando S3).
2. Por cada "nota" con forma inválida que el **parser** ya detectó y guardó aparte (`n.invalid_notes` — el parser no rechaza esto, solo lo etiqueta), determina el motivo exacto (¿la letra no existe, o es la alteración la que está mal?) y reporta S8.
3. Cuenta cuántas duraciones hay (`n.durations`) y aplica las tres sub-reglas de S6: sin notas, sin duración, duración repetida o mal ubicada (`n.misplaced_pos`, que el parser calculó durante el parseo: la posición de la primera nota que aparece *después* de una duración).
4. Si el acorde está en el nivel superior del programa, también dispara el warning S7 (igual que un track).

### `_warn_sin_instrumento(line, col, donde)` — S7
La más simple de todas: si `self._instrument` sigue siendo `None` (nunca se vio un `instrument` antes de este punto del recorrido), reporta el warning. `donde` es solo el texto que identifica el bloque en el mensaje (`"track 't'"` o `"chord"`).

### `analyze(program)` (función del módulo, al final del archivo)
No confundir con el método `analyze()` de la clase: esta es la función pública que usa el resto del proyecto (`from beatscript.semantic import analyze`). Solo crea un `SemanticAnalyzer()` nuevo y le pide que analice el programa — es el **punto de entrada oficial** del módulo, para no obligar a quien lo use a saber que existe la clase por dentro.

---

## 7. Cómo se usa esto en la práctica

```python
from beatscript.lexer import tokenize
from beatscript.parser import BeatScriptParser
from beatscript.semantic import analyze

codigo = "tempo 500\ntrack t { C4 negra }\n"

tokens = tokenize(codigo)
ast = BeatScriptParser(tokens, codigo).parse()
resultado = analyze(ast)

for error in resultado.errors:
    print(error)          # usa SemanticDiagnostic.__str__

print(resultado.symbols.rows())   # [Symbol(name='t', ...)]
```

Salida esperada:
```
[ERROR SEMÁNTICO] Línea 1, Col 7: BPM 500 demasiado alto: debe estar entre 20 y 400  (S1)
```

---

## 8. Más ejemplos para estudiar (más allá de los que ya están en los tests)

| Código | Resultado esperado | Por qué |
|--------|---------------------|---------|
| `tempo 400` | sin errores | 400 es el límite superior incluido |
| `tempo 401` | S1 | justo un BPM arriba del límite |
| `volume 128` | S2 | 127 es el máximo MIDI válido |
| `instrument piano\ntrack a {C4 negra}\ntrack b {D4 negra}` | sin errores | nombres distintos |
| `chord { C4 }` | S6 | tiene nota pero no duración |
| `chord { blanca C4 }` | S6 (duración antes de la nota) | la duración debe ir al final |
| `track t { Z5 negra }` | — (no aplica S8) | S8 solo aplica *dentro de un chord*; fuera de un chord, una nota inválida la rechaza el **parser**, no el semántico (otra capa distinta) |
| `repeat 3 { repeat 0 { C4 negra } }` | S4 | el `repeat 0` interno es inválido sin importar que el externo sea válido |

### Ejercicio sugerido para la presentación

Una forma clara de demostrarle al profesor que el analizador funciona es mostrar un mismo bloque de código con **un error introducido a propósito por regla**, y la salida de `analyze()` para cada uno — los 8 casos de la tabla de la sección 4 ya sirven directamente para esto. Los archivos [beatscript/tests/test_semantic.py](beatscript/tests/test_semantic.py) tienen exactamente un caso inválido y uno válido por cada regla S1–S8, listos para ejecutar como demo en vivo:

```bash
python -m pytest beatscript/tests/test_semantic.py -v
```

---

## 9. Glosario rápido (términos de la materia usados aquí)

- **AST (Abstract Syntax Tree):** árbol que representa la estructura del programa, construido por el parser, sin detalles superfluos de sintaxis (como las llaves `{ }`, que ya cumplieron su función de delimitar y no se guardan como nodos).
- **Acción semántica:** código que se ejecuta al reconocer una construcción del lenguaje, para calcular o verificar su significado (sección 2).
- **Tabla de símbolos:** registro de todo lo declarado en el programa, usado para detectar duplicados y (en lenguajes más complejos) resolver referencias.
- **Patrón Visitor:** forma de recorrer una estructura heterogénea (el AST, con 9 tipos de nodo distintos) despachando a un método distinto según el tipo de cada nodo, sin que los nodos necesiten saber cómo validarse a sí mismos.
- **Diagnóstico:** término genérico para "error o warning reportado por el compilador".
- **Severidad:** si un diagnóstico es `Error` (detiene la compilación) o `Warning` (solo informa).
