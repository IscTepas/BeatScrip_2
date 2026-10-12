"""
Tests del análisis semántico (Fase 3) — un caso inválido y uno válido por regla S1–S8.
Ejecutar:  python -m pytest beatscript/tests/test_semantic.py -v
"""
import unittest

from beatscript.lexer import tokenize
from beatscript.parser import BeatScriptParser
from beatscript.semantic import analyze, pitch_to_midi, SEMANTIC_ERRORS


def sem(source):
    """Lexer → parser → semántico. Falla si hay errores léxicos/sintácticos ."""
    tokens, lex_errors = tokenize(source, collect_errors=True)
    parser = BeatScriptParser(tokens, source)
    ast = parser.parse()
    assert not lex_errors and not parser.errors, (lex_errors, parser.errors)
    return analyze(ast)


def codigos(result):
    return [d.code for d in result.diagnostics]


class TestReglasSemanticas(unittest.TestCase):
    # S1 ---------------------------------------------------------------
    def test_s1_tempo_fuera_de_rango(self):
        self.assertEqual(codigos(sem("tempo 0\ntempo 5000\n")), ["S1", "S1"])

    def test_s1_limites_validos(self):
        self.assertEqual(codigos(sem("tempo 20\ntempo 400\n")), [])

    # S2 ---------------------------------------------------------------
    def test_s2_volumen_fuera_de_rango(self):
        self.assertEqual(codigos(sem("volume 150\n")), ["S2"])

    def test_s2_limites_validos(self):
        self.assertEqual(codigos(sem("volume 0\nvolume 127\n")), [])

    # S3 ---------------------------------------------------------------
    def test_s3_nota_fuera_de_midi(self):
        r = sem("instrument piano\ntrack t { C10 negra }\n")
        self.assertEqual(codigos(r), ["S3"])
        self.assertIn("MIDI 132", r.diagnostics[0].message)

    def test_s3_limite_g9_es_valido_y_ab9_no(self):
        self.assertEqual(pitch_to_midi("G9"), 127)
        self.assertEqual(codigos(sem("instrument piano\ntrack t { G9 negra }\n")), [])
        self.assertEqual(codigos(sem("instrument piano\ntrack t { G#9 negra }\n")), ["S3"])

    def test_pitch_to_midi(self):
        self.assertEqual(pitch_to_midi("C4"), 60)
        self.assertEqual(pitch_to_midi("A4"), 69)
        self.assertEqual(pitch_to_midi("EB5"), 75)   # el lexer normaliza Eb5 → EB5

    # S4 ---------------------------------------------------------------
    def test_s4_repeat_cero(self):
        self.assertEqual(codigos(sem("instrument piano\nrepeat 0 { C4 negra }\n")), ["S4"])

    def test_s4_repeat_dentro_de_track(self):
        self.assertEqual(codigos(sem("instrument piano\ntrack t { repeat 0 { C4 negra } }\n")), ["S4"])

    def test_s4_repeat_valido(self):
        self.assertEqual(codigos(sem("instrument piano\nrepeat 1 { C4 negra }\n")), [])

    # S5 ---------------------------------------------------------------
    def test_s5_track_repetido(self):
        r = sem("instrument piano\ntrack melodia { C4 negra }\ntrack melodia { D4 negra }\n")
        self.assertEqual(codigos(r), ["S5"])
        self.assertEqual(r.diagnostics[0].line, 3)
        self.assertIn("línea 2", r.diagnostics[0].message)   # apunta a la 1ª definición

    def test_s5_tabla_de_simbolos(self):
        r = sem("instrument violin\ntrack a { C4 negra }\ntrack b { D4 negra rest negra }\n")
        self.assertEqual([(s.name, s.instrument, s.events) for s in r.symbols.rows()],
                         [("a", "violin", 1), ("b", "violin", 2)])

    # S6 ---------------------------------------------------------------
    def test_s6_chord_vacio(self):
        self.assertEqual(codigos(sem("instrument piano\nchord { }\n")), ["S6"])

    def test_s6_chord_sin_duracion(self):
        self.assertEqual(codigos(sem("instrument piano\nchord { C4 E4 }\n")), ["S6"])

    def test_s6_duracion_repetida(self):
        r = sem("instrument piano\nchord { C4 E4 negra blanca }\n")
        self.assertEqual(codigos(r), ["S6"])
        self.assertIn("una sola vez al final", r.diagnostics[0].message)

    def test_s6_duracion_antes_de_las_notas(self):
        self.assertEqual(codigos(sem("instrument piano\nchord { C4 negra E4 }\n")), ["S6"])

    def test_s6_chord_valido(self):
        self.assertEqual(codigos(sem("instrument piano\nchord { C4 E4 G4 blanca }\n")), [])

    def test_s3_dentro_de_chord(self):
        self.assertEqual(codigos(sem("instrument piano\nchord { C13 E4 G4 negra }\n")), ["S3"])

    # S7 (warning) -----------------------------------------------------
    def test_s7_warning_sin_instrumento(self):
        r = sem("track t { C4 negra }\n")
        self.assertEqual(codigos(r), ["S7"])
        self.assertEqual(r.errors, [])           # es warning, no error
        self.assertEqual(len(r.warnings), 1)

    def test_s7_con_instrumento_no_avisa(self):
        self.assertEqual(codigos(sem("instrument piano\ntrack t { C4 negra }\n")), [])

    # S8 ---------------------------------------------------------------
    def test_s8_nota_invalida_en_chord(self):
        r = sem("instrument piano\nchord { H4 E4 blanca }\n")
        self.assertEqual(codigos(r), ["S8"])
        self.assertEqual((r.diagnostics[0].line, r.diagnostics[0].col), (2, 9))

    # Formato y catálogo ------------------------------------------------
    def test_formato_del_mensaje(self):
        msg = str(sem("tempo 0\n").diagnostics[0])
        self.assertTrue(msg.startswith("[ERROR SEMÁNTICO] Línea 1, Col 7: "), msg)

    def test_catalogo_cubre_s1_a_s8(self):
        self.assertEqual(sorted(SEMANTIC_ERRORS), [f"S{i}" for i in range(1, 9)])

    def test_ejemplo_completo_no_tiene_errores(self):
        import os
        ruta = os.path.join(os.path.dirname(__file__), "..", "..", "ejemplo_completo.bs")
        with open(ruta, encoding="utf-8") as f:
            self.assertEqual(sem(f.read()).errors, [])


if __name__ == "__main__":
    unittest.main()
