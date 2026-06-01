#!/usr/bin/env python3
"""
Test script para verificar la visualización visual del AST
"""

from beatscript.lexer import tokenize
from beatscript.parser import BeatScriptParser, ast_to_tree_string

# Código de prueba
code = """
tempo 120
volume 80

instrument piano
track melody {
    C4 negra
    D4 negra
    E4 blanca
    rest negra
    
    repeat 2 {
        F4 corchea
        G4 corchea
    }
}

repeat 2 {
    instrument violin
    track harmony {
        C5 negra
        D5 negra
    }
}
"""

print("=" * 70)
print("TEST: Visualización Visual del AST")
print("=" * 70)

try:
    tokens, errors = tokenize(code, collect_errors=True)
    
    if errors:
        print(" Errores léxicos:")
        for err in errors:
            print(f"   {err['msg']}")
    else:
        parser = BeatScriptParser(tokens)
        ast = parser.parse()
        
        if parser.errors:
            print(" Errores sintácticos:")
            for err in parser.errors:
                print(f"   {err}")
        else:
            print(" Parse completado sin errores\n")
            print("VISUALIZACIÓN DEL AST:")
            print("-" * 70)
            tree_str = ast_to_tree_string(ast)
            print(tree_str)
            print("-" * 70)
            print(f"\n Estadísticas:")
            print(f"   Líneas: {tree_str.count(chr(10)) + 1}")
            print(f"   Caracteres: {len(tree_str)}")

except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
