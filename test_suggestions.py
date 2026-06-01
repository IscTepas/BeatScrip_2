#!/usr/bin/env python3
"""
Test script para verificar que el sistema de sugerencias de palabras reservadas funciona
"""

from beatscript.lexer import tokenize
from beatscript.parser import BeatScriptParser

# Test cases con errores tipográficos comunes
test_cases = [
    # Error 1: "tempo" mal escrito como "tempp"
    {
        "name": "Typo en 'tempo'",
        "code": "tempp 120\n",
    },
    # Error 2: "instrument" mal escrito como "instrumento"
    {
        "name": "Typo en 'instrument'",
        "code": "instrumento piano\n",
    },
    # Error 3: "track" mal escrito como "traack"
    {
        "name": "Typo en 'track'",
        "code": "traack melody { C4 negra }\n",
    },
    # Error 4: "repeat" mal escrito como "repet"
    {
        "name": "Typo en 'repeat'",
        "code": "tempo 120\ntrack test { repet 2 { C4 negra } }\n",
    },
    # Error 5: "rest" mal escrito como "pausa"
    {
        "name": "Palabra reservada alternativa para 'rest'",
        "code": "tempo 120\ntrack test { pausa negra }\n",
    },
    # Error 6: "volume" mal escrito como "volumen"
    {
        "name": "Typo en 'volume'",
        "code": "volumen 100\n",
    },
]

print("=" * 70)
print("TEST: Sistema de Sugerencias de Palabras Reservadas")
print("=" * 70)

for i, test in enumerate(test_cases, 1):
    print(f"\n[Test {i}] {test['name']}")
    print(f"Código:\n{test['code']}")
    print("-" * 70)
    
    try:
        tokens, errors = tokenize(test['code'], collect_errors=True)
        
        if errors:
            print(f" Errores léxicos encontrados:")
            for err in errors:
                print(f"   {err['msg']}")
        else:
            parser = BeatScriptParser(tokens)
            ast = parser.parse()
            
            if parser.errors:
                print(f" Sugerencias encontradas:")
                for err in parser.errors:
                    print(f"\n{err}")
            else:
                print(" Sin errores - código válido")
    
    except Exception as e:
        print(f"  Error durante el parsing: {e}")

print("\n" + "=" * 70)
print("Test completado")
print("=" * 70)
