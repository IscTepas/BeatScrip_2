# MusicLang — Compilador de lenguaje musical → MIDI

Proyecto universitario de **Compiladores**.  
Lenguaje DSL para composición musical que genera archivos MIDI.

## Estructura del proyecto

```
Compiladores/
├── requirements.txt       # Dependencias Python
├── README.md
├── .gitignore
└── musiclang/
    ├── __init__.py
    ├── lexer.py           # Etapa 1: Analizador Léxico
    └── tests/
        └── test_lexer.py  # 74 casos de prueba
```

## Instalación (una sola vez)

Necesitas **Python 3.10+**. Verificar con:

```
python --version
```

Instalar dependencias:

```
pip install -r requirements.txt
```

## Cómo correr el demo del lexer

Desde la carpeta `C:\Compiladores\`:

```
python -X utf8 musiclang/lexer.py
```

Verás la tabla de tokens para el programa de ejemplo.

## Cómo correr los tests

```
python -X utf8 musiclang/tests/test_lexer.py
```

Resultado esperado: **74/74 tests pasados**.

## Ejemplo de código MusicLang

```
# Mi primera cancion
tempo 120

instrument piano

track melody {
    C4 negra
    D4 negra
    E4 blanca
    rest corchea
}

repeat 2 {
    G4 negra
    A4 corchea
}

chord {
    C4 E4 G4 blanca
}
```

## Tokens del lenguaje

| Token | Descripcion | Ejemplo |
|-------|-------------|---------|
| `TEMPO_KW` | Velocidad en BPM | `tempo 120` |
| `INSTRUMENT_KW` | Seleccion de instrumento | `instrument piano` |
| `TRACK_KW` | Inicio de pista | `track melody {` |
| `REPEAT_KW` | Repeticion de bloque | `repeat 2 {` |
| `CHORD_KW` | Acorde | `chord {` |
| `REST` | Silencio | `rest negra` |
| `NOTE` | Nota musical [A-G][#b][octava] | `C4`, `D#3`, `Eb5` |
| `DURATION` | Duracion de nota | `negra`, `blanca` |
| `INSTR_NAME` | Nombre de instrumento | `piano`, `violin` |
| `NUMBER` | Numero entero | `120`, `2` |
| `IDENTIFIER` | Nombre de track | `melody`, `coro` |

## Etapas del compilador (roadmap)

- [x] Etapa 1: Analizador Lexico (Lexer)
- [ ] Etapa 2: Analizador Sintactico (Parser) + AST
- [ ] Etapa 3: Analisis Semantico
- [ ] Etapa 4: Generacion de codigo MIDI
- [ ] Etapa 5: Interfaz visual

## Equipo
<!-- Agrega los nombres del equipo aqui -->
