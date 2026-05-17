# BeatScript — Compilador de lenguaje musical → MIDI

Proyecto universitario de **Compiladores**.  
Lenguaje DSL para composición musical que genera archivos MIDI.

## Estructura del proyecto

```
Compiladores/
├── main_gui.py            # IDE visual (BeatScript IDE)
├── requirements.txt       # Dependencias Python
├── README.md
├── .gitignore
└── beatscript/
    ├── __init__.py
    ├── lexer.py           # Etapa 1: Analizador Léxico
    ├── midi_gen.py        # Generador MIDI directo desde tokens
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

## Cómo correr el IDE

Desde la carpeta `C:\Compiladores\`:

```
python main_gui.py
```

## Cómo correr el demo del lexer (consola)

```
python -X utf8 beatscript/lexer.py
```

## Cómo correr los tests

```
python -X utf8 beatscript/tests/test_lexer.py
```

Resultado esperado: **74/74 tests pasados**.

## Ejemplo de código BeatScript

```
# Oda a la Alegría — BeatScript
tempo 110
volume 80

instrument violin

track melodia {
    E4 negra
    E4 negra
    F4 negra
    G4 negra
    G4 negra
    F4 negra
    E4 negra
    D4 negra
    C4 negra
    C4 negra
    D4 negra
    E4 negra
    E4 blanca
    D4 blanca
}

volume 70
instrument cello

track acompanamiento {
    C3 blanca
    G3 blanca
    C3 blanca
    G3 blanca
}

tempo 120
volume 90
instrument frenchhorn

repeat 2 {
    C4 negra
    E4 negra
    G4 negra
    rest negra
}

volume 100
instrument piano

chord {
    C4 E4 G4 C5 redonda
}
```

## Tokens del lenguaje

| Token | Descripcion | Ejemplo |
|-------|-------------|---------|
| `TEMPO_KW` | Velocidad en BPM | `tempo 120` |
| `VOLUME_KW` | Volumen MIDI (0–127) | `volume 90` |
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

## Instrumentos disponibles

| Categoria | Instrumentos |
| --------- | ------------ |
| Cuerdas | `piano`, `violin`, `viola`, `cello`, `contrabass`, `harp` |
| Vientos madera | `flute`, `piccolo`, `recorder`, `oboe`, `clarinet`, `bassoon`, `saxophone` |
| Vientos metal | `trumpet`, `trombone`, `frenchhorn`, `tuba` |
| Percusion melodica | `marimba`, `vibraphone`, `xylophone`, `celesta`, `drums` |
| Cuerdas pulsadas | `guitar`, `bass`, `banjo`, `sitar`, `harpsichord` |
| Teclados y otros | `organ`, `accordion`, `harmonica` |

## Duraciones disponibles

| Token | Beats |
| ----- | ----- |
| `redonda` | 4.0 |
| `blanca` | 2.0 |
| `negra` | 1.0 |
| `corchea` | 0.5 |
| `semicorchea` | 0.25 |
| `fusa` | 0.125 |
| `semifusa` | 0.0625 |

## Etapas del compilador (roadmap)

- [x] Etapa 1: Analizador Lexico (Lexer)
- [ ] Etapa 2: Analizador Sintactico (Parser) + AST
- [ ] Etapa 3: Analisis Semantico
- [ ] Etapa 4: Generacion de codigo MIDI
- [ ] Etapa 5: Interfaz visual

## Equipo

| Nombre                          |
| ------------------------------- |
| Rojas González Moisés Emmanuel  |
| Canales Navarro Christian Yael  |
| Nuñez Carvajal Jose Tadeo       |
| Rodriguez Flores Iker Gustavo   |
