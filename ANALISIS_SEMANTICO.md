# Análisis Semántico en BeatScript — guía de estudio completa y detallada

Este documento explica **todo** `beatscript/semantic.py`, línea por línea donde haga falta: qué es el análisis semántico, qué son las acciones semánticas, la tabla de símbolos, cada una de las 8 reglas (S1–S8) con ejemplos reales y su código exacto, y el funcionamiento de cada clase y método del archivo con el código siempre al lado de la explicación.

> **Convenciones:** cuando digo "como en Java" me refiero a un concepto equivalente que probablemente ya conoces. `self` en Python es lo mismo que `this` en Java. Un `dict` es un `HashMap`. Una clase con `@dataclass` es básicamente un *record*/POJO: Python genera el constructor por ti a partir de los atributos declarados, en vez de tener que escribirlo a mano.

---

## 1. ¿Qué es el análisis semántico?

En cualquier compilador hay (al menos) tres preguntas distintas que se le hacen al código fuente, en este orden:

| Etapa | Pregunta que responde | Ejemplo de fallo que detecta |
|-------|------------------------|-------------------------------|
| Léxico | ¿Estos caracteres forman palabras válidas del lenguaje? | `tempo @120` → `@` no es un carácter válido |
| Sintáctico | ¿Las palabras están en un orden gramaticalmente válido? | `tempo` (sin número) → falta un argumento |
| **Semántico** | ¿Lo que se escribió **tiene sentido**? | `tempo 5000` → la gramática lo permite (es un número), pero 5000 BPM no es un tempo musical válido |

El parser (etapa sintáctica) solo sabe reconocer *forma*: sabe que después de `tempo` debe venir un `NUMBER`, pero no sabe ni le importa si ese número es razonable. El análisis semántico es la etapa que entiende el **significado** de lo que ya se comprobó que está bien escrito: rangos válidos, nombres únicos, coherencia entre partes del programa que están lejos una de otra (ej. un `track` usado dos veces, aunque esté en otra parte del archivo).

Por eso el análisis semántico **no trabaja sobre los tokens ni sobre el texto crudo** — trabaja sobre el **AST** (el árbol que construyó el parser, explicado en detalle en [`COMO_FUNCIONA_EL_PROYECTO.md`](COMO_FUNCIONA_EL_PROYECTO.md)), porque ya necesita ver la estructura completa del programa, no solo una secuencia plana de palabras.

### El archivo completo, de un vistazo

```python
import re
from dataclasses import dataclass

from beatscript.parser import (
    Program, Tempo, Volume, Instrument, Track, Note, Rest, Chord, Repeat,
)
```

La primera línea importante: `semantic.py` **importa las clases de nodo del AST** directamente desde `parser.py`. Esto es lo que le permite, más adelante, usar `isinstance(node, Tempo)` para reconocer de qué tipo es cada nodo del árbol que recorre. `from dataclasses import dataclass` trae el *decorador* `@dataclass` (lo verás en la sección 5) que Python usa para generar automáticamente el constructor de clases que solo guardan datos.

---

## 2. ¿Qué son las "acciones semánticas"?

En la teoría de compiladores, una **acción semántica** es un fragmento de código que se ejecuta cuando se reconoce una construcción del lenguaje, y que **calcula o verifica algo sobre su significado** (en vez de solo verificar su forma). En muchos compiladores "de libro", estas acciones se escriben directamente embebidas en las reglas de la gramática (eso se llama **traducción dirigida por la sintaxis**, *syntax-directed translation*): cada regla gramatical lleva pegado un trozo de código que se ejecuta en el momento exacto en que esa regla se reconoce durante el parseo.

**En BeatScript estas acciones existen, pero están separadas en una segunda pasada** en vez de ir pegadas al parser: primero se construye el AST completo (etapa sintáctica, sin ninguna validación de significado), y *después* `SemanticAnalyzer` recorre ese árbol ya construido aplicando una acción semántica por cada tipo de nodo. Esto se llama más precisamente **traducción dirigida por el árbol de sintaxis** — una variante igual de válida y muy común en compiladores reales, porque simplifica tener un solo recorrido claro en vez de mezclar gramática y semántica en el mismo paso.

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

Cada acción puede hacer dos cosas (igual que en un compilador real): **verificar una condición** (y reportar error/warning si falla) y/o **actualizar el estado acumulado** que necesitan las validaciones siguientes (como la tabla de símbolos, o qué instrumento está activo en este punto del recorrido). Vas a ver exactamente cómo funciona cada una en la sección 7.

---

## 3. El catálogo de reglas — `SEMANTIC_ERRORS`

```python
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
```

Este es un `dict` cuyas **claves** son los códigos de regla (`"S1"` a `"S8"`) y cuyos **valores** son, a su vez, otro `dict` con cuatro campos de texto: `severity` (si detiene la compilación o solo avisa), `rule` (la regla en una frase), `example` (código que la viola), `cause` (por qué está mal) y `fix` (cómo corregirlo). Es, literalmente, la "ficha técnica" de cada regla — y es la fuente de verdad que consulta `_report()` (sección 7.3) para saber automáticamente si algo es `Error` o `Warning` sin que cada método tenga que decidirlo por su cuenta.

**Son 8 reglas en total: 7 errores + 1 warning (S7).**

---

## 4. Los límites numéricos — constantes al inicio del archivo

```python
TEMPO_MIN, TEMPO_MAX = 20, 400
VOLUME_MIN, VOLUME_MAX = 0, 127
MIDI_MIN, MIDI_MAX = 0, 127
REPEAT_MIN = 1
DEFAULT_INSTRUMENT = "piano"   # programa MIDI 0
```

`TEMPO_MIN, TEMPO_MAX = 20, 400` es una asignación múltiple de Python: en una sola línea asigna `20` a `TEMPO_MIN` y `400` a `TEMPO_MAX` (equivalente a escribir dos líneas `int TEMPO_MIN = 20; int TEMPO_MAX = 400;` en Java). Tener estos números como constantes con nombre, en vez de escribir `20` y `400` sueltos dentro de cada método, es lo que permite que las reglas S1, S2 y S3 (que comparten el mismo rango 0-127 para MIDI) sean fáciles de ajustar desde un solo lugar si el proyecto cambiara de requisitos.

---

## 5. Las clases de datos — `SemanticDiagnostic`, `Symbol`, `SymbolTable`

### 5.1 `SemanticDiagnostic` — un error o warning ya detectado

```python
# Un error o warning semántico ya detectado (código, posición y mensaje).
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
```

El decorador `@dataclass` encima de la clase le dice a Python: "genera automáticamente el constructor (`__init__`) a partir de estos cinco atributos declarados". Sin `@dataclass`, tendrías que escribir a mano:

```python
# Esto es lo que @dataclass genera por ti automáticamente:
def __init__(self, code, severity, line, col, message):
    self.code = code
    self.severity = severity
    self.line = line
    self.col = col
    self.message = message
```

Es exactamente el mismo ahorro que te da un **record** de Java moderno, o Lombok con `@Data` — una clase que solo guarda datos, sin tener que escribir el constructor repetitivo.

`__str__` es un método especial (*dunder method*) que define qué texto se muestra cuando haces `str(objeto)` o `print(objeto)` — el equivalente directo a sobreescribir `toString()` en Java. Aquí arma el mensaje final con el formato estándar: `[ERROR SEMÁNTICO] Línea 1, Col 7: BPM 5000 demasiado alto...  (S1)`. La expresión `"ERROR SEMÁNTICO" if self.severity == "Error" else "WARNING SEMÁNTICO"` es el **operador ternario** de Python (`valor_si_true if condicion else valor_si_false`) — equivalente a `condicion ? valorA : valorB` en Java.

### 5.2 `Symbol` — una entrada de la tabla de símbolos

```python
# Una entrada de la tabla de símbolos: un track ya declarado y sus datos.
@dataclass
class Symbol:
    name: str
    kind: str          # "track"
    line: int
    col: int
    instrument: str    # instrumento activo al definirse ("piano*" = por defecto)
    events: int        # cantidad de eventos directos del track
```

Otro POJO/record: guarda el nombre del track, su "tipo de símbolo" (`kind`, siempre `"track"` en este proyecto — el campo se deja genérico por si en el futuro hubiera otros tipos de símbolo), dónde se declaró, qué instrumento estaba activo en ese momento, y cuántos eventos tiene directamente.

### 5.3 `SymbolTable` — el registro de tracks declarados

```python
# Tabla de símbolos: guarda los tracks declarados para detectar duplicados (regla S5).
# Por dentro es solo un diccionario nombre → Symbol (equivalente a un
# HashMap<String, Symbol> en Java).
class SymbolTable:

    def __init__(self):
        self._symbols: dict[str, Symbol] = {}

    # Registra el símbolo. Si ya existía devuelve el anterior (duplicado), si no None.
    def define(self, symbol: Symbol):
        previo = self._symbols.get(symbol.name)
        if previo is not None:
            return previo
        self._symbols[symbol.name] = symbol
        return None

    # Busca un símbolo por nombre. Devuelve None si no está definido.
    def lookup(self, name):
        return self._symbols.get(name)

    # Devuelve todos los símbolos como lista (para mostrarlos en el IDE).
    def rows(self):
        return list(self._symbols.values())

    # Cantidad de símbolos registrados — permite usar len(tabla).
    def __len__(self):
        return len(self._symbols)
```

Una **tabla de símbolos** es una estructura central en cualquier compilador: un registro de todo lo que el programa *declara* (variables, funciones, clases... en BeatScript, **tracks**), para poder comprobar más adelante cosas como "¿ya existe algo con este nombre?" sin tener que volver a recorrer todo el árbol desde cero cada vez que se necesite esa respuesta.

El prefijo `_` en `self._symbols` es una convención de Python (no una regla forzada por el lenguaje, a diferencia de `private` en Java) que significa "esto es interno a la clase, no lo toques desde afuera" — solo por convención, cualquiera *podría* acceder a `tabla._symbols` directamente, pero no se supone que lo haga.

El método clave es `define()`:
```python
def define(self, symbol: Symbol):
    previo = self._symbols.get(symbol.name)
    if previo is not None:
        return previo          # ya existía → devuelve el anterior (para reportar el duplicado)
    self._symbols[symbol.name] = symbol
    return None                 # no existía → quedó registrado
```
`self._symbols.get(symbol.name)` busca si ya hay algo con ese nombre (como `map.get(clave)` en Java, que devuelve `null`/`None` si no existe). Si **ya existía** algo (`previo is not None`), la función **no sobreescribe** — simplemente devuelve el símbolo anterior, para que quien llamó a `define()` pueda comparar y generar el mensaje de error de duplicado (esto se usa en `_track()`, sección 7.7). Si no existía, lo guarda y devuelve `None` para indicar "todo bien, no había duplicado". Este es el mismo patrón que usarías para detectar "variable ya declarada" en un compilador de un lenguaje de propósito general — aquí, en vez de variables, son nombres de `track`.

`__len__` es otro método especial: define qué devuelve `len(tabla)` — el equivalente a implementar una interfaz `Sized`/`Collection` en Java para que `.size()` funcione, pero en Python se logra con esta convención de nombre especial en vez de una interfaz.

---

## 6. La conversión nota → número MIDI — `pitch_to_midi`

```python
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_RE = re.compile(r"^([A-G])([#B]?)(\d+)$")


# 'C4' → 60, 'D#3' → 51, 'C10' → 132 (el lexer ya normaliza a mayúsculas).
def pitch_to_midi(pitch: str) -> int:
    letra, alt, octava = _NOTE_RE.match(pitch.upper()).groups()
    return _SEMITONES[letra] + (int(octava) + 1) * 12 + (1 if alt == "#" else -1 if alt == "B" else 0)
```

`_SEMITONES` da los semitonos de cada nota **dentro de una octava** (C=0, D=2, E=4, F=5, G=7, A=9, B=11 — nota que van de 2 en 2 generalmente, salvo E→F y B→C que van de 1 en 1; así es la escala musical occidental, con sus semitonos intermedios reservados para los sostenidos/bemoles).

`_NOTE_RE = re.compile(r"^([A-G])([#B]?)(\d+)$")` compila una expresión regular **una sola vez** al cargar el módulo (en vez de recompilarla cada vez que se llama a la función, lo cual sería más lento) — tiene tres **grupos de captura** entre paréntesis: la letra (`[A-G]`), la alteración opcional (`[#B]?`), y la octava (uno o más dígitos, `\d+`).

Paso a paso de `pitch_to_midi`:
1. `pitch.upper()` — por si acaso, vuelve a normalizar a mayúsculas (aunque el lexer ya lo hace, ver sección 4.6 de `COMO_FUNCIONA_EL_PROYECTO.md`).
2. `_NOTE_RE.match(...)` — intenta encajar la regex contra el texto completo.
3. `.groups()` — devuelve una tupla con lo que capturó cada grupo, ej. para `"D#3"` sería `("D", "#", "3")`.
4. `letra, alt, octava = (...)` — asignación múltiple que reparte esa tupla en tres variables (como desestructurar un array en una sola línea).
5. La fórmula final: `_SEMITONES[letra]` da los semitonos de la letra (consulta el diccionario, como `map.get(letra)`), `(int(octava) + 1) * 12` ubica esa octava en la escala MIDI completa — nota que `int(octava)` convierte el texto `"3"` a número `3` (la regex siempre captura texto, nunca números directamente) — y el operador ternario anidado `1 if alt == "#" else -1 if alt == "B" else 0` suma 1 si hay sostenido, resta 1 si hay bemol, o no suma nada si no hay alteración.

**¿Por qué `(octava + 1) * 12` y no solo `octava * 12`?** Porque el estándar MIDI define que la nota `C4` (Do central del piano) corresponde al número MIDI **60**, y la convención de nombres de octava hace que la "octava 4" en notación científica no empiece exactamente en el múltiplo de 12 que uno esperaría a simple vista — el `+1` es el ajuste necesario para que la fórmula cuadre con ese estándar. Puedes comprobarlo: `C4` → semitono de C (0) + (4+1)×12 (60) + 0 = **60**. ✓.

Ejemplo completo paso a paso con `"D#3"`:
1. `letra="D"`, `alt="#"`, `octava="3"`.
2. `_SEMITONES["D"]` = 2.
3. `(int("3") + 1) * 12` = `4 * 12` = 48.
4. Como `alt == "#"`, se suma 1.
5. Total: `2 + 48 + 1` = **51**.

---

## 7. `SemanticAnalyzer` — la clase principal, método por método

```python
# Recorre el AST una sola vez y acumula errores/warnings.
class SemanticAnalyzer:

    def __init__(self):
        self.diagnostics: list[SemanticDiagnostic] = []
        self.symbols = SymbolTable()
        self._instrument = None    # instrumento vigente mientras se recorre
```

El constructor inicializa tres cosas que se van a ir llenando/actualizando durante el recorrido:
- `self.diagnostics` — la lista acumulada de **todos** los errores y warnings encontrados hasta ahora (empieza vacía).
- `self.symbols` — una `SymbolTable` nueva y vacía.
- `self._instrument` — qué instrumento está "activo" en este punto del recorrido; empieza en `None` porque al inicio del programa aún no se ha visto ningún `instrument`.

### 7.1 `errors` y `warnings` — las dos propiedades de resultado

```python
# -- resultados ---------------------------------------------------------

# Solo los diagnósticos de severidad 'Error' (los que detienen la compilación).
@property
def errors(self):
    return [d for d in self.diagnostics if d.severity == "Error"]

# Solo los diagnósticos de severidad 'Warning' (no detienen la compilación).
@property
def warnings(self):
    return [d for d in self.diagnostics if d.severity == "Warning"]
```

`[d for d in self.diagnostics if d.severity == "Error"]` es una **lista por comprensión**: recorre `self.diagnostics`, y se queda solo con los elementos `d` cuyo `d.severity` sea `"Error"` — es el equivalente compacto de un `.stream().filter(d -> d.getSeverity().equals("Error")).collect(toList())` de Java, pero en una sola expresión.

`@property` es un decorador que convierte un método en algo que se **accede como si fuera un atributo**, sin paréntesis: en vez de escribir `analizador.errors()`, se escribe `analizador.errors`. Esto no cambia la lógica en absoluto, solo la forma de llamarlo — es puramente estético/ergonómico, parecido a un *getter* automático en Java pero sin necesidad de escribir `getErrors()`.

### 7.2 `_report` — crear y acumular un diagnóstico

```python
# Crea un SemanticDiagnostic a partir del código de regla (S1...S8) y lo acumula.
# La severidad (Error/Warning) no se pasa a mano: se busca en SEMANTIC_ERRORS
# según el código, para no tener que repetirla en cada llamada.
def _report(self, code, line, col, message):
    sev = SEMANTIC_ERRORS[code]["severity"]
    self.diagnostics.append(SemanticDiagnostic(code, sev, line, col, message))
```

Este es el **único** lugar del archivo donde se crea un `SemanticDiagnostic`. Todas las reglas (S1 a S8) terminan llamando a este método en vez de construir el diagnóstico ellas mismas — eso significa que ninguna regla necesita saber si es `Error` o `Warning`, solo necesita pasar su código (`"S1"`, `"S7"`, etc.) y `_report()` busca la severidad correcta automáticamente consultando el catálogo `SEMANTIC_ERRORS` de la sección 3. Esto evita que, si algún día cambiara la severidad de una regla, haya que modificar el método que la aplica — solo habría que cambiar el catálogo.

### 7.3 `analyze` (método) — el punto de entrada de la clase

```python
# -- punto de entrada ---------------------------------------------------

# Punto de entrada: visita cada sentencia del programa y devuelve self con los resultados.
# Al final ordena los diagnósticos por línea/columna para que se
# muestren en el mismo orden en que aparecen en el código fuente,
# sin importar en qué orden se hayan detectado internamente.
def analyze(self, program: Program):
    for stmt in program.statements:
        self._visit(stmt)
    self.diagnostics.sort(key=lambda d: (d.line or 0, d.col or 0))
    return self
```

`for stmt in program.statements:` recorre cada sentencia de nivel superior del AST (el `Program` que construyó el parser, ver [`COMO_FUNCIONA_EL_PROYECTO.md`](COMO_FUNCIONA_EL_PROYECTO.md) sección 5.4) y llama a `_visit()` por cada una.

`self.diagnostics.sort(key=lambda d: (d.line or 0, d.col or 0))` — `sort()` ordena la lista **en el propio lugar** (modifica `self.diagnostics` directamente, no crea una lista nueva). El parámetro `key` le dice cómo comparar dos elementos: `lambda d: (d.line or 0, d.col or 0)` es una **función anónima** (lambda, equivalente a una expresión lambda de Java) que, para cada diagnóstico `d`, devuelve una tupla `(línea, columna)` — Python ordena tuplas comparando primero el primer valor, y solo si son iguales compara el segundo (orden lexicográfico), que es exactamente el criterio "primero por línea, luego por columna" que se necesita aquí. El `or 0` es por seguridad: si `d.line` fuera `None` (no debería pasar normalmente, pero por si acaso), usa `0` en su lugar para que la comparación no falle.

Por qué este ordenamiento es necesario: durante el recorrido del árbol, un `Chord` puede reportar varios errores internos (S3, S6, S8) en el orden en que el código los fue comprobando, que no necesariamente es el mismo orden en que esas cosas aparecen escritas en el archivo fuente. Ordenar al final garantiza que el usuario vea los errores en el mismo orden en que leería su propio código, de arriba hacia abajo.

Finalmente, `return self` — el método devuelve la instancia misma del analizador (con todo ya calculado adentro), lo cual permite encadenar: `SemanticAnalyzer().analyze(program)` en una sola línea, como verás en la función pública al final del archivo (sección 7.10).

### 7.4 `_visit` — el patrón Visitor, el corazón del recorrido

```python
# -- despacho -----------------------------------------------------------

# Patrón visitor: según la clase del nodo AST, llama al método que sabe revisarlo.
# top_level indica si el nodo está directamente bajo el programa (True)
# o dentro de un track/repeat (False) — algunas reglas (como el warning
# de instrumento no definido, S7) solo aplican a nivel superior.
def _visit(self, node, top_level=True):
    if isinstance(node, Tempo):        self._tempo(node)
    elif isinstance(node, Volume):     self._volume(node)
    elif isinstance(node, Instrument): self._instrument = node.name
    elif isinstance(node, Track):      self._track(node)
    elif isinstance(node, Repeat):     self._repeat(node, top_level)
    elif isinstance(node, Chord):      self._chord(node, top_level)
    elif isinstance(node, Note):       self._note(node.pitch, node.arg_line, node.arg_col)
```

Este es el **patrón Visitor**: en vez de que cada clase de nodo (`Tempo`, `Track`, `Note`...) sepa cómo validarse a sí misma (lo cual mezclaría la definición del AST, en `parser.py`, con la lógica de validación semántica), hay **una sola función externa** que decide, mirando el tipo real del objeto con `isinstance()`, a qué método especializado delegar. Es el mismo patrón que implementarías en Java con un `switch` sobre el tipo (o con `instanceof` encadenados como aquí), o de forma más "orientada a objetos" con una jerarquía `Visitor`/`Visitable` (donde cada nodo tendría un método `accept(visitor)`).

`isinstance(node, Tempo)` comprueba si `node` es una instancia de la clase `Tempo` (o de una subclase) — el equivalente directo a `node instanceof Tempo` en Java.

Nota que el caso de `Instrument` **no llama a ningún método de validación** — simplemente actualiza `self._instrument = node.name` directamente dentro del `_visit`. Esto es porque `Instrument` no tiene ninguna regla que lo valide a sí mismo (cualquier nombre de instrumento que llegó hasta aquí ya fue validado por el lexer, que solo reconoce instrumentos de la lista fija `INSTR_NAME`); su única función semántica es actualizar el "instrumento activo" para que las reglas de `Track` y `Chord` sepan qué instrumento estaba vigente.

El parámetro `top_level` viaja junto con cada llamada recursiva para que algunas reglas (como S7) sepan si están mirando un nodo que cuelga directamente del programa, o uno que está anidado dentro de un `track`/`repeat` — esto importa porque, por ejemplo, el warning de "falta instrument" solo tiene sentido reportarlo una vez por bloque de nivel superior (un `track` o un `chord` sueltos), no evaluarlo de nuevo por cada nota individual dentro de ellos.

### 7.5 `_tempo` — Regla S1

```python
# -- reglas -------------------------------------------------------------

# Regla S1: el BPM de 'tempo N' debe caer en [TEMPO_MIN, TEMPO_MAX].
def _tempo(self, n):                                                    # S1
    if not (TEMPO_MIN <= n.bpm <= TEMPO_MAX):
        lado = "bajo" if n.bpm < TEMPO_MIN else "alto"
        self._report("S1", n.arg_line, n.arg_col,
                     f"BPM {n.bpm} demasiado {lado}: debe estar entre {TEMPO_MIN} y {TEMPO_MAX}")
```

`TEMPO_MIN <= n.bpm <= TEMPO_MAX` es una comparación **encadenada**, una característica propia de Python que no existe en Java: en Java tendrías que escribir `TEMPO_MIN <= n.bpm && n.bpm <= TEMPO_MAX`; en Python se puede escribir como una sola cadena de comparaciones, que se lee casi igual que la notación matemática "20 ≤ bpm ≤ 400". El `not (...)` invierte la condición completa: si el BPM **no** está en rango, entra al `if`.

`"bajo" if n.bpm < TEMPO_MIN else "alto"` — el operador ternario de Python, usado aquí para decidir qué palabra poner en el mensaje de error según de qué lado se salió del rango.

- ❌ Inválido: `tempo 0` → `n.bpm = 0`, `0 < 20` → mensaje "demasiado bajo".
- ❌ Inválido: `tempo 5000` → `5000 > 400` → mensaje "demasiado alto".
- ✅ Válido: `tempo 20`, `tempo 120`, `tempo 400` (los límites están incluidos, por el `<=`).

`n.arg_line, n.arg_col` (no `n.line, n.col`) — se usa la posición del **argumento** (el número), no de la palabra clave `tempo`, para que el mensaje de error señale exactamente el número que está mal (ver `_at()` en `parser.py`, sección 5.6 de `COMO_FUNCIONA_EL_PROYECTO.md`).

### 7.6 `_volume` — Regla S2

```python
# Regla S2: el nivel de 'volume N' debe caer en [VOLUME_MIN, VOLUME_MAX].
def _volume(self, n):                                                   # S2
    if not (VOLUME_MIN <= n.level <= VOLUME_MAX):
        self._report("S2", n.arg_line, n.arg_col,
                     f"volumen {n.level} fuera de rango {VOLUME_MIN}-{VOLUME_MAX}")
```

Estructuralmente idéntico a `_tempo()`, pero validando el rango MIDI de volumen (0-127) en vez del rango de tempo.
- ❌ Inválido: `volume 150` (128-127 es el máximo real de MIDI, 150 se pasa).
- ✅ Válido: `volume 0`, `volume 90`, `volume 127`.
- *Nota:* `volume -5` nunca llega a esta regla — el **lexer** ya rechaza el carácter `-` como inválido (BeatScript no tiene números negativos en absoluto, ver `_ERROR_HINTS` en `lexer.py`).

### 7.7 `_note` — Regla S3

```python
# Regla S3: convierte la nota a número MIDI y verifica que esté en [0, 127].
# Se llama tanto para notas sueltas (Note) como para cada nota dentro de
# un chord — por eso recibe pitch/line/col sueltos en vez de un nodo completo.
def _note(self, pitch, line, col):                                      # S3
    midi = pitch_to_midi(pitch)
    if not (MIDI_MIN <= midi <= MIDI_MAX):
        self._report("S3", line, col,
                     f"{pitch} = MIDI {midi}, fuera del rango MIDI {MIDI_MIN}-{MIDI_MAX}")
```

Usa `pitch_to_midi()` (sección 6) para convertir el texto de la nota a su número real, y valida que ese número esté en el rango físico que el protocolo MIDI permite (0-127; son 128 valores posibles, el máximo que cabe en un solo byte).

- ❌ Inválido: `C10` → `pitch_to_midi("C10")` = `0 + (10+1)*12 + 0` = **132**, se sale del rango.
- ✅ Válido: `G9` → `pitch_to_midi("G9")` = `7 + (9+1)*12 + 0` = **127**, justo el límite permitido.
- ❌ Inválido: `G#9` → `127 + 1` = **128**, un semitono más que el límite, ya se sale.

Esta función recibe `pitch, line, col` **sueltos** (no un nodo `Note` completo) a propósito, para poder **reutilizarla** desde dos lugares distintos: tanto desde `_visit()` cuando el nodo es un `Note` normal (`self._note(node.pitch, node.arg_line, node.arg_col)`), como desde `_chord()` (sección 7.9) para cada nota individual dentro de un acorde, que no son nodos `Note` — son solo texto dentro de la lista `n.notes` del nodo `Chord`.

### 7.8 `_repeat` — Regla S4

```python
# Regla S4: 'repeat N' exige N >= 1; luego visita cada evento del cuerpo.
# No desenrolla el bucle (no ejecuta el cuerpo N veces aquí): solo valida
# el conteo y revisa el cuerpo UNA vez, igual para todas las repeticiones.
def _repeat(self, n, top_level):                                        # S4
    if n.count < REPEAT_MIN:
        self._report("S4", n.arg_line, n.arg_col,
                     f"repeat {n.count}: repeat debe ser mayor o igual a {REPEAT_MIN}")
    for hijo in n.events:
        self._visit(hijo, top_level)
```

Primero valida que `n.count >= REPEAT_MIN` (1) — un bloque repetido 0 veces nunca se ejecutaría, así que no tiene sentido permitirlo. Luego, **sin importar si la validación falló o no** (no hay `else`, el `for` siempre se ejecuta), recorre cada evento dentro del cuerpo del repeat llamando a `_visit()` recursivamente — porque aunque el conteo sea inválido, igual conviene revisar que las notas de adentro sean válidas, para reportar el máximo de problemas reales de una sola corrida.

**Importante para entender el alcance de esta etapa:** este método **no ejecuta el cuerpo N veces** — solo lo revisa **una vez**, pase lo que pase con `n.count`. La repetición real de los eventos (ejecutar el bloque efectivamente 2, 3, 5 veces) la hace hoy `midi_gen.py` (con su propio `for _ in range(n): process(...)`, ver `COMO_FUNCIONA_EL_PROYECTO.md` sección 7.5) — y sería también responsabilidad de la futura etapa de código intermedio, no de esta.

- ❌ Inválido: `repeat 0 { C4 negra }`.
- ✅ Válido: `repeat 1 { ... }`, `repeat 2 { ... }`.
- También aplica anidado: `repeat 3 { repeat 0 { C4 negra } }` reporta S4 por el `repeat 0` interno, sin importar que el externo sea válido — porque `_visit()` recorre recursivamente y cada `Repeat` que encuentra se valida de forma independiente.

### 7.9 `_track` — Regla S5 (+ dispara S7)

```python
# Regla S5 (nombre de track único) + dispara S7 si no hay instrumento definido.
# Registra el track en la tabla de símbolos (self.symbols.define); si ya
# existía uno con el mismo nombre, reporta el duplicado. Luego visita
# cada evento interno marcando top_level=False.
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
```

Paso a paso:
1. `usado = self._instrument or f"{DEFAULT_INSTRUMENT}*"` — si hay un instrumento activo (`self._instrument` no es `None` ni cadena vacía), lo usa; si no, usa `"piano*"` (el asterisco es solo una marca visual para distinguir en la tabla de símbolos del IDE que ese instrumento fue el valor por defecto, no uno que el usuario escribió explícitamente).
2. `self.symbols.define(Symbol(...))` — construye un `Symbol` nuevo con todos sus datos y lo intenta registrar en la tabla. Si ya existía uno con el mismo nombre, `define()` (sección 5.3) devuelve ese símbolo anterior en vez de `None`.
3. Si `previo is not None` (hubo duplicado), reporta S5 señalando la línea de la **primera** definición (`previo.line`, `previo.col`) dentro del mensaje — así el usuario sabe exactamente dónde está el otro track con el mismo nombre, no solo que "hay un duplicado" en abstracto.
4. `self._warn_sin_instrumento(...)` — ver sección 7.11 (S7).
5. `for ev in n.events: self._visit(ev, top_level=False)` — recorre cada evento (nota, rest, chord, repeat) dentro del track, marcando `top_level=False` porque ya no están "sueltos" a nivel de programa, están anidados dentro de este track.

- ❌ Inválido:
  ```
  track melodia { C4 negra }
  track melodia { D4 negra }
  ```
  Mensaje: `track 'melodia' ya está definido (primera definición: línea 2, col 1)`.
- ✅ Válido: usar nombres distintos (`melodia`, `acompanamiento`, etc.)

### 7.10 `_chord` — Reglas S3 + S6 + S8 (el método más elaborado)

```python
# Valida un chord completo: reutiliza S3 por cada nota, y aplica S6/S8.
# S8: cada "nota" con forma inválida (ej. letra fuera de A-G, o alteración
# rara) que el parser ya detectó y guardó en n.invalid_notes se reporta
# aquí con el motivo exacto.
# S6: el chord debe tener al menos una nota y exactamente una duración,
# ubicada al final del bloque (no antes de las notas).
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
```

Este método recorre **cuatro frentes distintos**, uno por cada sub-validación necesaria de un `chord`. Recuerda que el nodo `Chord` llega aquí con información extra que el **parser** ya recolectó por adelantado (`note_pos`, `durations`, `invalid_notes`, `misplaced_pos` — ver `COMO_FUNCIONA_EL_PROYECTO.md` sección 5.15):

**Parte 1 — S3 reutilizada para cada nota del acorde:**
```python
for pitch, (l, c) in zip(n.notes, n.note_pos):
    self._note(pitch, l, c)
```
`zip(n.notes, n.note_pos)` combina dos listas en paralelo, elemento por elemento: si `n.notes = ["C4", "E4"]` y `n.note_pos = [(2,8), (2,11)]`, `zip` produce los pares `("C4", (2,8))` y `("E4", (2,11))`. `for pitch, (l, c) in zip(...)` desestructura cada par directamente en el bucle (la tupla `(l, c)` dentro de la posición se "desempaqueta" en dos variables separadas). Por cada nota, llama a `_note()` (ya explicado en 7.7) para validar su rango MIDI.

**Parte 2 — S8, notas con forma inválida:**
```python
for texto, l, c in n.invalid_notes:
    if texto[0].upper() not in _SEMITONES:
        motivo = f"la letra '{texto[0]}' no existe (solo A-G)"
    else:
        motivo = "alteración inválida (solo '#' o 'b')"
    self._report("S8", l, c, f"'{texto}' no es una nota válida: {motivo}")
```
`n.invalid_notes` son tokens que el parser detectó con *forma* de nota (letra seguida de dígitos) pero que el lexer no reconoció como `NOTE` real, porque la letra no es una de las válidas (A-G) o la alteración es rara. Por cada una, decide el **motivo exacto**: si la primera letra ni siquiera está en `_SEMITONES` (el diccionario de la sección 6, que solo tiene A-G), el problema es la letra; si la letra sí es válida pero aun así se marcó como inválida, el problema debe ser la alteración.
- ❌ Inválido: `chord { H4 E4 blanca }` → `H` no está en `_SEMITONES` → "la letra 'H' no existe (solo A-G)".

**Parte 3 — S6, forma del acorde (cantidad y posición de la duración):**
```python
n_dur = len(n.durations)
if not n.notes and not n.invalid_notes:
    self._report("S6", n.line, n.col, "el acorde no tiene notas")
if n_dur == 0 and (n.notes or n.invalid_notes):
    self._report("S6", n.line, n.col, "el acorde no tiene duración")
elif n_dur > 1:
    _, l, c = n.durations[1]
    self._report("S6", l, c, "la duración compartida va una sola vez al final")
elif n.misplaced_pos:
    self._report("S6", *n.misplaced_pos, "la duración compartida va una sola vez al final")
```
Cuatro casos, en orden de prioridad:
1. `not n.notes and not n.invalid_notes` — no hay absolutamente ninguna nota (ni válida ni inválida): `chord { }`.
2. `n_dur == 0 and (n.notes or n.invalid_notes)` — hay notas pero ninguna duración: `chord { C4 E4 }`.
3. `n_dur > 1` — hay más de una duración (`chord { C4 E4 negra blanca }`); el mensaje señala específicamente la **segunda** duración encontrada (`n.durations[1]`, índice 1 porque las listas en Python empiezan en 0) como la que está de más.
4. `n.misplaced_pos` — aunque haya exactamente una duración, si el parser detectó que una nota apareció *después* de ella (`chord { C4 negra E4 }`), se reporta en esa posición exacta. `self._report("S6", *n.misplaced_pos, "...")` usa `*` para **desempaquetar** la tupla `n.misplaced_pos` (que es `(línea, columna)`) directamente como los dos argumentos posicionales `line, col` que espera `_report()` — equivalente a pasar `n.misplaced_pos[0], n.misplaced_pos[1]` por separado, pero más compacto.

- ✅ Válido: `chord { C4 E4 G4 blanca }` (al menos una nota, exactamente una duración, al final).

**Parte 4 — dispara el warning S7 si corresponde:**
```python
if top_level:
    self._warn_sin_instrumento(n.line, n.col, "chord")
```
Solo si el `chord` está a nivel superior del programa (no anidado dentro de otra cosa) se evalúa el warning de instrumento no definido — igual que ocurre para `_track()`.

### 7.11 `_warn_sin_instrumento` — Regla S7 (el único warning)

```python
# Regla S7 (warning): avisa si se usan notas sin haber definido 'instrument' antes.
# No es error porque BeatScript cae a piano por defecto si falta; solo se
# reporta una vez por track/chord gracias a que _instrument ya habría
# quedado asignado si hubo un 'instrument' previo.
def _warn_sin_instrumento(self, line, col, donde):                      # S7
    if self._instrument is None:
        self._report("S7", line, col,
                     f"{donde}: no se definió instrumento; se usará {DEFAULT_INSTRUMENT} (programa 0)")
```

La más simple de todas las reglas: si `self._instrument` sigue siendo `None` (nunca se vio un `instrument` antes de este punto del recorrido), reporta el warning. `donde` es solo el texto que identifica el bloque en el mensaje (recibe `"track 't'"` desde `_track()`, o `"chord"` desde `_chord()`).

- ⚠️ Genera warning: `track t { C4 negra }` (sin `instrument` antes en todo el programa hasta ese punto).
- ✅ No genera nada: `instrument piano` antes del `track`.

**Es la única regla de severidad `Warning`** (todas las demás son `Error`) — por eso, para un programa que solo viola S7, `resultado.errors` queda vacío (la compilación "no se detiene") pero `resultado.warnings` tiene 1 elemento (sí se informa al usuario).

### 7.12 La función pública `analyze()` (al final del archivo)

```python
# ---------------------------------------------------------------------------
# 7. FUNCIÓN PÚBLICA
# ---------------------------------------------------------------------------

# Ejecuta el análisis semántico completo sobre un AST y devuelve el analizador con resultados.
def analyze(program: Program) -> SemanticAnalyzer:
    return SemanticAnalyzer().analyze(program)
```

**No confundir con el método `analyze()` de la clase** (sección 7.3) — esta es una **función del módulo** (vive suelta en el archivo, no dentro de ninguna clase), y es el **punto de entrada oficial** que usa el resto del proyecto: `from beatscript.semantic import analyze`. Internamente solo crea un `SemanticAnalyzer()` nuevo (llamando a su constructor, sección 7 inicial) y de inmediato le pide `.analyze(program)` — todo en una sola línea, encadenando la llamada porque, como vimos en 7.3, el método de la clase devuelve `self`. Esto existe para que quien use el módulo no necesite saber que la clase `SemanticAnalyzer` existe por dentro — solo necesita llamar a una función y usar el resultado.

---

## 8. Cómo se usa esto en la práctica — ejemplo de extremo a extremo

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

print(resultado.symbols.rows())   # [Symbol(name='t', kind='track', ...)]
```

Salida esperada:
```
[ERROR SEMÁNTICO] Línea 1, Col 7: BPM 500 demasiado alto: debe estar entre 20 y 400  (S1)
```

Y `resultado.symbols.rows()` devolvería una lista con un solo `Symbol`, correspondiente al track `"t"` — aunque el `tempo` tuviera un error, el `track` sigue siendo válido y se registra igual, porque cada regla se evalúa de forma independiente durante el mismo recorrido.

---

## 9. Catálogo completo de reglas con ejemplos, lado a lado

| Código | Severidad | Método | En una frase | Ejemplo inválido | Ejemplo válido |
|--------|-----------|--------|---------------|-------------------|------------------|
| S1 | Error | `_tempo` | `tempo` fuera de 20–400 | `tempo 0` / `tempo 5000` | `tempo 120` |
| S2 | Error | `_volume` | `volume` fuera de 0–127 | `volume 150` | `volume 90` |
| S3 | Error | `_note` | nota fuera del rango MIDI 0–127 | `C10 negra` (MIDI 132) | `G9 negra` (MIDI 127) |
| S4 | Error | `_repeat` | `repeat` con N < 1 | `repeat 0 { C4 negra }` | `repeat 2 { C4 negra }` |
| S5 | Error | `_track` | nombre de `track` repetido | `track a {..} track a {..}` | `track a {..} track b {..}` |
| S6 | Error | `_chord` | `chord` mal formado (notas/duración) | `chord { C4 E4 negra blanca }` | `chord { C4 E4 blanca }` |
| S7 | **Warning** | `_warn_sin_instrumento` | falta `instrument` antes de usar notas | `track t { C4 negra }` (sin instrument) | `instrument piano`<br>`track t { C4 negra }` |
| S8 | Error | `_chord` | nota con letra/alteración inválida dentro de un `chord` | `chord { H4 E4 blanca }` | `chord { C4 E4 blanca }` |

---

## 10. Más ejemplos para estudiar (más allá de los que ya están en los tests)

| Código BeatScript | Resultado esperado | Por qué |
|--------------------|---------------------|---------|
| `tempo 400` | sin errores | 400 es el límite superior incluido |
| `tempo 401` | S1 | justo un BPM arriba del límite |
| `volume 128` | S2 | 127 es el máximo MIDI válido |
| `instrument piano`<br>`track a {C4 negra}`<br>`track b {D4 negra}` | sin errores | nombres distintos |
| `chord { C4 }` | S6 | tiene nota pero no duración |
| `chord { blanca C4 }` | S6 (duración antes de la nota) | la duración debe ir al final |
| `track t { Z5 negra }` | — (no aplica S8) | S8 solo aplica *dentro de un chord*; fuera de un chord, una nota con letra inválida la rechaza el **parser** (otra capa, no esta) |
| `repeat 3 { repeat 0 { C4 negra } }` | S4 | el `repeat 0` interno es inválido sin importar que el externo sea válido |

### Ejercicio sugerido para la presentación al profesor

Una forma clara de demostrar que el analizador funciona es mostrar un mismo bloque de código con **un error introducido a propósito por regla**, y la salida de `analyze()` para cada uno — los 8 casos de la tabla de la sección 9 ya sirven directamente para esto. El archivo [`beatscript/tests/test_semantic.py`](beatscript/tests/test_semantic.py) tiene exactamente un caso inválido y uno válido por cada regla S1–S8, listos para ejecutar como demo en vivo:

```bash
python -m pytest beatscript/tests/test_semantic.py -v
```

---

## 11. Glosario rápido (términos de la materia usados en este documento)

- **AST (Abstract Syntax Tree):** árbol que representa la estructura del programa, construido por el parser, sin detalles superfluos de sintaxis (como las llaves `{ }`, que ya cumplieron su función de delimitar y no se guardan como nodos independientes).
- **Acción semántica:** código que se ejecuta al reconocer una construcción del lenguaje, para calcular o verificar su significado (sección 2).
- **Traducción dirigida por la sintaxis / por el árbol:** dos formas de organizar cuándo se ejecutan las acciones semánticas — pegadas al parser en el momento del reconocimiento, o en una pasada separada después de tener el árbol completo (lo que hace este proyecto).
- **Tabla de símbolos:** registro de todo lo declarado en el programa, usado para detectar duplicados y (en lenguajes más complejos) resolver referencias entre partes del código.
- **Patrón Visitor:** forma de recorrer una estructura heterogénea (el AST, con 9 tipos de nodo distintos) despachando a un método distinto según el tipo de cada nodo, sin que los nodos necesiten saber cómo validarse a sí mismos.
- **Diagnóstico:** término genérico para "error o warning reportado por el compilador".
- **Severidad:** si un diagnóstico es `Error` (detiene la compilación) o `Warning` (solo informa, el programa sigue siendo válido).
- **`@dataclass`:** decorador de Python que genera automáticamente el constructor de una clase a partir de sus atributos declarados — equivalente a un *record* de Java o a `@Data` de Lombok.
- **Lista por comprensión:** sintaxis de Python `[expr for x in iterable if condicion]` para construir una lista nueva filtrando/transformando otra en una sola línea — equivalente a un `stream().filter().map().collect()` de Java.
