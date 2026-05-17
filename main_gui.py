# main_gui.py — BeatScript IDE
# Ventana principal del compilador BeatScript
# Framework: customtkinter (modo oscuro) + tkinter.ttk (tablas)

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import pygame
import os

# Apariencia global
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


# ─────────────────────────────────────────────────────────────────────────────
# Ventana secundaria: Detalles Extra
# ─────────────────────────────────────────────────────────────────────────────
class DetallesExtraWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Detalles Extra")
        self.geometry("520x360")
        self.resizable(False, False)
        self.grab_set()  # bloquea la ventana principal mientras está abierta
        self.lift()
        self.focus_force()

        ctk.CTkLabel(
            self,
            text="Detalles Extra",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(35, 10))

        ctk.CTkLabel(
            self,
            text=(
                "Aquí se mostrarán detalles adicionales del análisis:\n\n"
                "• Tabla de símbolos\n"
                "• Estadísticas de tokens\n"
                "• Errores semánticos\n"
                "• Información de la Etapa 3 en adelante"
            ),
            font=ctk.CTkFont(size=13),
            justify="left",
        ).pack(padx=40, pady=10, anchor="w")

        ctk.CTkButton(
            self,
            text="Cerrar",
            width=120,
            command=self.destroy,
        ).pack(pady=20)


# ─────────────────────────────────────────────────────────────────────────────
# Ventana principal
# ─────────────────────────────────────────────────────────────────────────────
class BeatScriptIDE(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BeatScript IDE")
        self.geometry("1200x800")
        self.state("zoomed")  # maximizada en Windows

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()

        self._build_toolbar()
        self._build_main_area()
        self._build_console()
        self._configure_treeview_style()
        self._cargar_ejemplo()

    # ── Barra superior ────────────────────────────────────────────────────────
    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, height=52, corner_radius=0)
        toolbar.pack(side="top", fill="x")
        toolbar.pack_propagate(False)

        ctk.CTkLabel(
            toolbar,
            text="BeatScript IDE",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=20)

        ctk.CTkButton(
            toolbar,
            text="▶  Compilar y Reproducir",
            fg_color="#2e7d32",
            hover_color="#388e3c",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=210,
            command=self._compilar,
        ).pack(side="left", padx=(0, 10), pady=10)

        ctk.CTkButton(
            toolbar,
            text="⏹  Detener",
            fg_color="#b71c1c",
            hover_color="#c62828",
            font=ctk.CTkFont(size=13),
            width=120,
            command=self._detener,
        ).pack(side="left", padx=(0, 10), pady=10)

        ctk.CTkButton(
            toolbar,
            text="Ver Detalles Extra",
            fg_color="#37474f",
            hover_color="#455a64",
            font=ctk.CTkFont(size=13),
            width=160,
            command=self._abrir_detalles,
        ).pack(side="left", pady=10)

    # ── Área principal: editor + paneles derechos ─────────────────────────────
    def _build_main_area(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

        main.columnconfigure(0, weight=5)  # editor
        main.columnconfigure(1, weight=6)  # paneles
        main.rowconfigure(0, weight=1)

        self._build_editor(main)
        self._build_right_panels(main)

    # ── Editor de código (izquierda) ──────────────────────────────────────────
    def _build_editor(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Editor de código",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        self.editor = ctk.CTkTextbox(
            frame,
            font=("Consolas", 13),
            wrap="none",
            activate_scrollbars=True,
        )
        self.editor.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    # ── Paneles derechos (tokens arriba, AST abajo) ───────────────────────────
    def _build_right_panels(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        frame.grid(row=0, column=1, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self._build_token_panel(frame)
        self._build_ast_panel(frame)

    # ── Panel de tokens (mitad superior derecha) ──────────────────────────────
    def _build_token_panel(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Tokens — Lexer",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#a5d6a7",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        tree_frame = tk.Frame(frame, bg="#2b2b2b")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columnas = ("#", "Tipo", "Valor", "Línea", "Columna")
        self.tabla_tokens = ttk.Treeview(
            tree_frame,
            columns=columnas,
            show="headings",
            style="Dark.Treeview",
        )

        anchos   = [45, 155, 175, 65, 75]
        anclajes = ["center", "w", "w", "center", "center"]
        for col, ancho, ancla in zip(columnas, anchos, anclajes):
            self.tabla_tokens.heading(col, text=col)
            self.tabla_tokens.column(col, width=ancho, anchor=ancla, stretch=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self.tabla_tokens.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tabla_tokens.xview)
        self.tabla_tokens.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tabla_tokens.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

    # ── Panel AST (mitad inferior derecha) ────────────────────────────────────
    def _build_ast_panel(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Árbol Sintáctico — Parser  (Etapa 2 — pendiente)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffcc80",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        tree_frame = tk.Frame(frame, bg="#2b2b2b")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tabla_ast = ttk.Treeview(
            tree_frame,
            columns=("Nodo", "Tipo", "Valor"),
            show="headings",
            style="Dark.Treeview",
        )
        for col, ancho in zip(("Nodo", "Tipo", "Valor"), (200, 150, 150)):
            self.tabla_ast.heading(col, text=col)
            self.tabla_ast.column(col, width=ancho, anchor="w", stretch=True)

        vsb2 = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tabla_ast.yview)
        self.tabla_ast.configure(yscrollcommand=vsb2.set)

        self.tabla_ast.grid(row=0, column=0, sticky="nsew")
        vsb2.grid(row=0, column=1, sticky="ns")

        self.tabla_ast.insert("", "end", values=("— El AST se generará aquí (Etapa 2) —", "", ""))

    # ── Consola inferior ──────────────────────────────────────────────────────
    def _build_console(self):
        frame = ctk.CTkFrame(self, height=145, corner_radius=8)
        frame.pack(side="bottom", fill="x", padx=8, pady=8)
        frame.pack_propagate(False)

        ctk.CTkLabel(
            frame,
            text="Consola",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ef9a9a",
        ).pack(anchor="w", padx=12, pady=(6, 2))

        self.consola = ctk.CTkTextbox(
            frame,
            font=("Consolas", 12),
            state="disabled",
            text_color="#e0e0e0",
            fg_color="#1a1a1a",
        )
        self.consola.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ── Estilo oscuro para Treeview ───────────────────────────────────────────
    def _configure_treeview_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.Treeview",
            background="#1e1e1e",
            foreground="#e0e0e0",
            fieldbackground="#1e1e1e",
            rowheight=26,
            font=("Consolas", 11),
        )
        style.configure(
            "Dark.Treeview.Heading",
            background="#2d2d2d",
            foreground="#90caf9",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", "#1565c0")],
            foreground=[("selected", "#ffffff")],
        )

    # ── Lógica del botón Compilar ─────────────────────────────────────────────
    def _compilar(self):
        for row in self.tabla_tokens.get_children():
            self.tabla_tokens.delete(row)
        self._log("", clear=True)

        source = self.editor.get("1.0", "end-1c").strip()
        if not source:
            self._log("⚠  El editor está vacío. Escribe código BeatScript primero.")
            return

        self._log("▶  Iniciando análisis léxico...")

        try:
            from beatscript.lexer import tokenize
            tokens, errors = tokenize(source, collect_errors=True)
        except ImportError:
            self._log("⚠  [Mock] beatscript.lexer no encontrado — usando datos de prueba")
            tokens, errors = self._mock_tokens(), []
        except Exception as e:
            self._log(f"✗  Error durante el análisis léxico: {e}")
            return

        # Error léxico → mostrar y detener
        if errors:
            for err in errors:
                self._log(f"✗  {err['msg']}")
            self._log(f"\n✗  Compilación detenida — {len(errors)} error(es) léxico(s) encontrado(s).")
            return

        # Validación post-léxica → detener si hay problemas
        avisos = self._validar_tokens_extra(tokens, source)
        if avisos:
            for av in avisos:
                self._log(f"✗  {av}")
            self._log(f"\n✗  Compilación detenida — {len(avisos)} error(es) de validación encontrado(s).")
            return

        # Sin errores → llenar tabla y continuar
        for i, tok in enumerate(tokens, 1):
            col = self._calcular_columna(source, tok)
            self.tabla_tokens.insert(
                "", "end",
                values=(i, tok.type, repr(tok.value), tok.lineno, col),
            )

        self._log(f"✔  Análisis léxico completado — {len(tokens)} tokens encontrados.")

        # Generar y reproducir MIDI
        try:
            from beatscript.midi_gen import tokens_to_midi
            midi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.mid")
            tokens_to_midi(tokens, midi_path)
            pygame.mixer.music.load(midi_path)
            pygame.mixer.music.play()
            self._log("♪  Reproduciendo output.mid ...")
        except Exception as e:
            self._log(f"⚠  No se pudo reproducir el MIDI: {e}")

    def _validar_tokens_extra(self, tokens: list, source: str) -> list:
        """Detecta patrones sospechosos que el lexer acepta pero son inválidos semánticamente."""
        import re
        avisos = []
        instrumentos_validos = {
            "piano", "violin", "viola", "cello", "contrabass", "harp",
            "flute", "piccolo", "recorder", "oboe", "clarinet", "bassoon", "saxophone",
            "trumpet", "trombone", "frenchhorn", "tuba",
            "marimba", "vibraphone", "xylophone", "celesta", "drums",
            "guitar", "bass", "banjo", "sitar", "harpsichord",
            "organ", "accordion", "harmonica",
        }
        i = 0
        while i < len(tokens):
            tok = tokens[i]

            if tok.type == "INSTRUMENT_KW":
                siguiente = tokens[i + 1] if i + 1 < len(tokens) else None
                if siguiente and siguiente.type == "IDENTIFIER":
                    col = self._calcular_columna(source, siguiente)
                    avisos.append(
                        f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                        f"'{siguiente.value}' no es un instrumento reconocido. "
                        f"Usa: piano, guitar, violin, flute, drums, bass, trumpet..."
                    )

            elif tok.type == "TEMPO_KW":
                siguiente = tokens[i + 1] if i + 1 < len(tokens) else None
                if siguiente and siguiente.type != "NUMBER":
                    col = self._calcular_columna(source, siguiente)
                    avisos.append(
                        f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                        f"se esperaba un número después de 'tempo', se encontró '{siguiente.value}'"
                    )

            elif tok.type == "VOLUME_KW":
                siguiente = tokens[i + 1] if i + 1 < len(tokens) else None
                if siguiente and siguiente.type != "NUMBER":
                    col = self._calcular_columna(source, siguiente)
                    avisos.append(
                        f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                        f"'volume' requiere un número entre 0 y 127, se encontró '{siguiente.value}'"
                    )
                elif siguiente and siguiente.type == "NUMBER":
                    if not (0 <= siguiente.value <= 127):
                        col = self._calcular_columna(source, siguiente)
                        avisos.append(
                            f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                            f"volumen {siguiente.value} fuera de rango — usa un valor entre 0 y 127"
                        )

            elif tok.type == "NOTE" or tok.type == "REST":
                siguiente = tokens[i + 1] if i + 1 < len(tokens) else None
                if siguiente and siguiente.type == "IDENTIFIER":
                    col = self._calcular_columna(source, siguiente)
                    avisos.append(
                        f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                        f"'{siguiente.value}' no es una duración válida — usa: "
                        f"negra, blanca, corchea, redonda, semicorchea, fusa, semifusa"
                    )

            elif tok.type == "IDENTIFIER":
                val = tok.value
                # Parece nota pero mal formada: empieza con A-G y termina con dígito
                if re.match(r"^[A-Ga-g].+\d$", val):
                    col = self._calcular_columna(source, tok)
                    avisos.append(
                        f"[AVISO] Línea {tok.lineno}, Col {col}: "
                        f"'{val}' parece una nota inválida — formato: [A-G][#b]?[octava], ej: C4, D#3, Eb5"
                    )

            i += 1
        return avisos

    def _detener(self):
        pygame.mixer.music.stop()
        self._log("⏹  Reproducción detenida.")

    def _calcular_columna(self, source: str, token) -> int:
        line_start = source.rfind("\n", 0, token.lexpos) + 1
        return token.lexpos - line_start + 1

    # ── Mock de tokens para demostración ─────────────────────────────────────
    def _mock_tokens(self) -> list:
        class FakeTok:
            def __init__(self, t, v, l, p):
                self.type = t
                self.value = v
                self.lineno = l
                self.lexpos = p

        return [
            FakeTok("TEMPO_KW",      "tempo",       1,  0),
            FakeTok("NUMBER",         120,           1,  6),
            FakeTok("INSTRUMENT_KW", "instrument",  3, 11),
            FakeTok("INSTR_NAME",    "piano",       3, 22),
            FakeTok("TRACK_KW",      "track",       5, 28),
            FakeTok("IDENTIFIER",    "melody",      5, 34),
            FakeTok("LBRACE",        "{",           5, 41),
            FakeTok("NOTE",          "C4",          6, 47),
            FakeTok("DURATION",      "negra",       6, 50),
            FakeTok("NOTE",          "D4",          7, 56),
            FakeTok("DURATION",      "negra",       7, 59),
            FakeTok("RBRACE",        "}",           8, 65),
        ]

    # ── Escribir en la consola ────────────────────────────────────────────────
    def _log(self, mensaje: str, clear: bool = False):
        self.consola.configure(state="normal")
        if clear:
            self.consola.delete("1.0", "end")
        if mensaje:
            self.consola.insert("end", mensaje + "\n")
        self.consola.see("end")
        self.consola.configure(state="disabled")

    # ── Abrir ventana secundaria ──────────────────────────────────────────────
    def _abrir_detalles(self):
        DetallesExtraWindow(self)

    # ── Código de ejemplo al iniciar ──────────────────────────────────────────
    def _cargar_ejemplo(self):
        ejemplo = """\
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
    F3 blanca
    C3 blanca
    G3 blanca
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
    C4 E4 G4 blanca
}

chord {
    F4 A4 C5 blanca
}

chord {
    G4 B4 D5 blanca
}

chord {
    C4 E4 G4 C5 redonda
}
"""
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", ejemplo)


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BeatScriptIDE()
    app.mainloop()
