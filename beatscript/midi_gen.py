# beatscript/midi_gen.py — Generador MIDI (Etapa 4 simplificada)
# Interpreta tokens de BeatScript directamente y produce un archivo .mid

from midiutil import MIDIFile

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
    'guitar':     25,
    'violin':     40,
    'flute':      73,
    'drums':       0,
    'bass':       32,
    'trumpet':    56,
    'cello':      42,
    'saxophone':  65,
    'organ':      19,
    'harp':       46,
    'harpsichord': 6,
    'marimba':    12,
    'vibraphone': 11,
    'clarinet':   71,
    'oboe':       68,
    'tuba':       58,
}


def note_to_midi(note_str: str) -> int:
    """Convierte 'C4', 'D#3', 'EB5' → número MIDI."""
    s = note_str.upper()
    letter = s[0]
    rest   = s[1:]
    if rest and rest[0] in ('#', 'B') and len(rest) > 1:
        alt, octave = rest[0], int(rest[1])
    else:
        alt, octave = '', int(rest[0])
    pitch = NOTE_SEMITONES[letter] + (octave + 1) * 12
    if alt == '#': pitch += 1
    if alt == 'B': pitch -= 1
    return pitch


def _collect_block(tokens: list, start: int):
    """Retorna (tokens_dentro_del_bloque, índice_siguiente_al_RBRACE)."""
    depth, end = 1, start
    while end < len(tokens) and depth > 0:
        if   tokens[end].type == 'LBRACE': depth += 1
        elif tokens[end].type == 'RBRACE': depth -= 1
        end += 1
    return tokens[start:end - 1], end


def tokens_to_midi(tokens: list, output_path: str = "output.mid") -> str:
    """
    Recorre la lista de tokens y escribe un archivo MIDI.
    Retorna la ruta del archivo generado.
    """
    midi    = MIDIFile(1)
    track   = 0
    channel = 0
    tempo   = 120
    program = 0
    midi.addTempo(track, 0, tempo)
    midi.addProgramChange(track, channel, 0, program)

    def process(tok_list: list, t: float) -> float:
        nonlocal tempo, program
        j = 0
        while j < len(tok_list):
            tok = tok_list[j]

            # tempo N
            if tok.type == 'TEMPO_KW':
                if j + 1 < len(tok_list) and tok_list[j + 1].type == 'NUMBER':
                    tempo = tok_list[j + 1].value
                    midi.addTempo(track, t, tempo)
                    j += 2; continue

            # instrument NAME
            elif tok.type == 'INSTRUMENT_KW':
                if j + 1 < len(tok_list) and tok_list[j + 1].type == 'INSTR_NAME':
                    program = INSTRUMENT_PROGRAM.get(tok_list[j + 1].value, 0)
                    midi.addProgramChange(track, channel, t, program)
                    j += 2; continue

            # track NAME { ... }
            elif tok.type == 'TRACK_KW':
                k = j + 1
                while k < len(tok_list) and tok_list[k].type != 'LBRACE':
                    k += 1
                if k < len(tok_list):
                    block, end = _collect_block(tok_list, k + 1)
                    t = process(block, t)
                    j = end; continue

            # repeat N { ... }
            elif tok.type == 'REPEAT_KW':
                n, k = 1, j + 1
                if k < len(tok_list) and tok_list[k].type == 'NUMBER':
                    n = tok_list[k].value; k += 1
                while k < len(tok_list) and tok_list[k].type != 'LBRACE':
                    k += 1
                if k < len(tok_list):
                    block, end = _collect_block(tok_list, k + 1)
                    for _ in range(n):
                        t = process(block, t)
                    j = end; continue

            # chord { NOTE... DURATION }
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
                        midi.addNote(track, channel, note_to_midi(note), t, dur, 80)
                    t += dur
                    j = end; continue

            # NOTE [DURATION]
            elif tok.type == 'NOTE':
                dur = 1.0
                if j + 1 < len(tok_list) and tok_list[j + 1].type == 'DURATION':
                    dur = DURATION_BEATS.get(tok_list[j + 1].value, 1.0)
                    j += 1
                try:
                    midi.addNote(track, channel, note_to_midi(tok.value), t, dur, 80)
                except Exception:
                    pass
                t += dur

            # rest [DURATION]
            elif tok.type == 'REST':
                dur = 1.0
                if j + 1 < len(tok_list) and tok_list[j + 1].type == 'DURATION':
                    dur = DURATION_BEATS.get(tok_list[j + 1].value, 1.0)
                    j += 1
                t += dur

            j += 1
        return t

    process(tokens, 0.0)

    with open(output_path, 'wb') as f:
        midi.writeFile(f)

    return output_path
