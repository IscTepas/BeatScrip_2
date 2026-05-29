# main_gui.py — BeatScript IDE
# Ventana principal del compilador BeatScript
# Framework: customtkinter (modo oscuro) + tkinter.ttk (tablas)

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import pygame
import os
from beatscript.parser import BeatScriptParser, ast_to_tree_string

# Apariencia global
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


# ─────────────────────────────────────────────────────────────────────────────
# Ventana principal
# ─────────────────────────────────────────────────────────────────────────────
class BeatScriptIDE(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BeatScript IDE")
        self.geometry("1200x800")
        self.state("zoomed")  # Maximizada en Windows

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()

        self._build_toolbar()
        self._build_main_area()
        self._build_console()
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

    # ── Área principal: editor + paneles derechos ─────────────────────────────
    def _build_main_area(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

        main.columnconfigure(0, weight=5)  # Editor de código
        main.columnconfigure(1, weight=6)  # Paneles derecho
        main.rowconfigure(0, weight=1)

        self._build_editor(main)
        self._build_right_panels(main)

    # ── Editor de código (izquierda) con barra de estado ─────────────────────
    def _build_editor(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        frame.rowconfigure(1, weight=1)   # El textbox ocupa todo el espacio
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
        self.editor.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 0))

        # ── Barra de estado del editor (Línea / Col / Total líneas) ──────────
        # Se actualiza con cada pulsación de tecla o clic del ratón
        status_bar = ctk.CTkFrame(frame, height=26, corner_radius=0, fg_color="#1a1a2e")
        status_bar.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        status_bar.grid_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_bar,
            text="  Línea: 1, Col: 1  |  Líneas totales: 1",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#78909c",
            anchor="w",
        )
        self.status_label.pack(side="left", padx=4, fill="x", expand=True)

        # Enlazar eventos al widget interno de tk.Text para actualizar la barra
        inner = self.editor._textbox
        inner.bind("<KeyRelease>", self._actualizar_estado)
        inner.bind("<ButtonRelease>", self._actualizar_estado)

    # ── Panel derecho: tabla de tokens (50%) + árbol AST (50%) ───────────────
    def _build_right_panels(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        frame.grid(row=0, column=1, sticky="nsew")

        # Dos filas de igual peso → 50 % / 50 %
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self._build_token_panel(frame)  # Fila 0 — tabla léxica
        self._build_ast_panel(frame)    # Fila 1 — árbol sintáctico

    # ── Panel de tokens (mitad superior del área derecha) ────────────────────
    def _build_token_panel(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Tabla de Tokens — Lexer (Etapa 1)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#a5d6a7",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        # Contenedor para Treeview + scrollbars (ttk no tiene corner_radius)
        container = tk.Frame(frame, bg="#1e1e1e")
        container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        # ── Estilo oscuro para el Treeview (ttk no hereda el tema de ctk) ────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Token.Treeview",
            background="#1e1e1e",
            foreground="#e0e0e0",
            fieldbackground="#1e1e1e",
            rowheight=22,
            font=("Consolas", 10),
            borderwidth=0,
        )
        style.configure(
            "Token.Treeview.Heading",
            background="#2d2d2d",
            foreground="#90caf9",
            font=("Consolas", 10, "bold"),
            relief="flat",
        )
        style.map(
            "Token.Treeview",
            background=[("selected", "#1565c0")],
            foreground=[("selected", "#ffffff")],
        )

        # ── Treeview con columnas: #, TIPO, VALOR, LÍNEA, COL ────────────────
        self.token_tree = ttk.Treeview(
            container,
            columns=("num", "tipo", "valor", "linea", "col"),
            show="headings",   # Ocultar la columna árbol por defecto
            style="Token.Treeview",
            selectmode="browse",
        )

        # Encabezados
        self.token_tree.heading("num",   text="#")
        self.token_tree.heading("tipo",  text="TIPO")
        self.token_tree.heading("valor", text="VALOR")
        self.token_tree.heading("linea", text="LÍNEA")
        self.token_tree.heading("col",   text="COL")

        # Anchos de columna
        self.token_tree.column("num",   width=40,  anchor="center", stretch=False)
        self.token_tree.column("tipo",  width=150, anchor="w")
        self.token_tree.column("valor", width=140, anchor="w")
        self.token_tree.column("linea", width=58,  anchor="center", stretch=False)
        self.token_tree.column("col",   width=50,  anchor="center", stretch=False)

        # Colores alternos para las filas (efecto zebra)
        self.token_tree.tag_configure("par",   background="#252525")
        self.token_tree.tag_configure("impar", background="#1e1e1e")

        # Scrollbars sincronizadas
        v_scroll = ttk.Scrollbar(container, orient="vertical",   command=self.token_tree.yview)
        h_scroll = ttk.Scrollbar(container, orient="horizontal", command=self.token_tree.xview)
        self.token_tree.configure(
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
        )

        self.token_tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

    # ── Panel AST (mitad inferior del área derecha) ───────────────────────────
    def _build_ast_panel(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self.ast_label = ctk.CTkLabel(
            frame,
            text="Árbol Sintáctico — Parser (Etapa 2)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffcc80",
        )
        self.ast_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        self.ast_textbox = ctk.CTkTextbox(
            frame,
            font=("Consolas", 11),
            wrap="none",
            activate_scrollbars=True,
            text_color="#a1d995",
            fg_color="#1a1a1a",
        )
        self.ast_textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.ast_textbox.insert("1.0", "— El AST se generará aquí (Etapa 2) —")
        self.ast_textbox.configure(state="disabled")

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

    # ── Barra de estado: actualizar posición del cursor ───────────────────────
    def _actualizar_estado(self, event=None):
        """
        Actualiza la barra de estado inferior del editor con la posición
        actual del cursor y el total de líneas del documento.
        """
        try:
            inner = self.editor._textbox
            # "linea.columna" — las columnas empiezan en 0 en tk.Text
            pos = inner.index("insert")
            linea, col_raw = pos.split(".")
            col = int(col_raw) + 1  # Convertir a base 1

            # Total de líneas sin contar la línea vacía final de tk.Text
            total = int(inner.index("end-1c").split(".")[0])

            self.status_label.configure(
                text=f"  Línea: {linea}, Col: {col}  |  Líneas totales: {total}"
            )
        except Exception:
            pass

    # ── Mostrar árbol sintáctico visual ───────────────────────────────────────
    def _mostrar_ast(self, ast):
        """Muestra el árbol sintáctico (AST) en formato visual de árbol."""
        self.ast_textbox.configure(state="normal")
        self.ast_textbox.delete("1.0", "end")

        tree_str = ast_to_tree_string(ast)
        self.ast_textbox.insert("1.0", tree_str)
        self.ast_textbox.configure(state="disabled")

        # Actualizar etiqueta con conteo aproximado de nodos
        num_nodes = tree_str.count("\n") + 1
        self.ast_label.configure(
            text=f"Árbol Sintáctico — Parser (Etapa 2 — {num_nodes} nodos)"
        )

    # ── Lógica del botón Compilar ─────────────────────────────────────────────
    def _compilar(self):
        self._log("", clear=True)

        source = self.editor.get("1.0", "end-1c").strip()
        if not source:
            self._log("El editor está vacío. Escribe código BeatScript primero.")
            return

        # ── ETAPA 1: ANÁLISIS LÉXICO ──────────────────────────────────────────
        self._log("Iniciando análisis léxico...")

        try:
            from beatscript.lexer import tokenize
            tokens, errors = tokenize(source, collect_errors=True)
        except ImportError:
            self._log("beatscript.lexer no encontrado — usando datos de prueba")
            tokens, errors = self._mock_tokens(), []
        except Exception as e:
            self._log(f"Error durante el análisis léxico: {e}")
            return

        # Error léxico → mostrar y detener
        if errors:
            for err in errors:
                self._log(f"  {err['msg']}")
            self._log(
                f"\nCompilación detenida — {len(errors)} error(es) léxico(s) encontrado(s)."
            )
            return

        # Validación post-léxica
        avisos = self._validar_tokens_extra(tokens, source)
        if avisos:
            for av in avisos:
                self._log(f"  {av}")
            self._log(
                f"\n  Compilación detenida — {len(avisos)} error(es) de validación encontrado(s)."
            )
            return

        self._log(f"  Análisis léxico completado — {len(tokens)} tokens encontrados.")

        # ── Llenar la tabla de tokens en el panel derecho ─────────────────────
        self._llenar_tabla_tokens(tokens, source)

        # ── ETAPA 2: ANÁLISIS SINTÁCTICO → Árbol Sintáctico (AST) ────────────
        self._log("Iniciando análisis sintáctico...")

        try:
            # Pasar el código fuente para que el parser calcule columnas en errores
            parser = BeatScriptParser(tokens, source)
            ast = parser.parse()

            if parser.errors:
                for err in parser.errors:
                    self._log(f"  {err}")
                self._log(
                    f"\nCompilación detenida — {len(parser.errors)} "
                    f"error(es) sintáctico(s) encontrado(s)."
                )
                return

            self._log("  Análisis sintáctico completado.")
            self._mostrar_ast(ast)

        except Exception as e:
            self._log(f"Error durante el análisis sintáctico: {e}")
            return

        # ── Generar y reproducir MIDI ─────────────────────────────────────────
        try:
            from beatscript.midi_gen import tokens_to_midi
            midi_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "output.mid"
            )
            tokens_to_midi(tokens, midi_path)
            pygame.mixer.music.load(midi_path)
            pygame.mixer.music.play()
            self._log(" Reproduciendo output.mid ...")
        except Exception as e:
            self._log(f"  No se pudo reproducir el MIDI: {e}")

    # ── Poblar la tabla de tokens del panel derecho ───────────────────────────
    def _llenar_tabla_tokens(self, tokens: list, source: str):
        """
        Limpia la tabla de tokens y la rellena con los resultados del lexer.
        Aplica filas alternas (par/impar) para facilitar la lectura.
        """
        # Limpiar filas previas
        for item in self.token_tree.get_children():
            self.token_tree.delete(item)

        for i, tok in enumerate(tokens, 1):
            col = self._calcular_columna(source, tok)
            tag = "par" if i % 2 == 0 else "impar"
            self.token_tree.insert(
                "",
                "end",
                values=(i, tok.type, str(tok.value), tok.lineno, col),
                tags=(tag,),
            )

    def _validar_tokens_extra(self, tokens: list, source: str) -> list:
        """Detecta patrones sospechosos que el lexer acepta pero son inválidos semánticamente."""
        import re
        avisos = []
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
                        f"se esperaba un número después de 'tempo', "
                        f"se encontró '{siguiente.value}'"
                    )

            elif tok.type == "VOLUME_KW":
                siguiente = tokens[i + 1] if i + 1 < len(tokens) else None
                if siguiente and siguiente.type != "NUMBER":
                    col = self._calcular_columna(source, siguiente)
                    avisos.append(
                        f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                        f"'volume' requiere un número entre 0 y 127, "
                        f"se encontró '{siguiente.value}'"
                    )
                elif siguiente and siguiente.type == "NUMBER":
                    if not (0 <= siguiente.value <= 127):
                        col = self._calcular_columna(source, siguiente)
                        avisos.append(
                            f"[AVISO] Línea {siguiente.lineno}, Col {col}: "
                            f"volumen {siguiente.value} fuera de rango — "
                            f"usa un valor entre 0 y 127"
                        )

            elif tok.type in ("NOTE", "REST"):
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
                # Detecta posibles notas mal formadas (ej. "C4x", "D##3")
                if re.match(r"^[A-Ga-g].+\d$", val):
                    col = self._calcular_columna(source, tok)
                    avisos.append(
                        f"[AVISO] Línea {tok.lineno}, Col {col}: "
                        f"'{val}' parece una nota inválida — "
                        f"formato: [A-G][#b]?[octava], ej: C4, D#3, Eb5"
                    )

            i += 1
        return avisos

    def _detener(self):
        pygame.mixer.music.stop()
        self._log("Reproducción detenida.")

    def _calcular_columna(self, source: str, token) -> int:
        """Calcula la columna (1-indexada) de un token dentro de su línea."""
        line_start = source.rfind("\n", 0, token.lexpos) + 1
        return token.lexpos - line_start + 1

    # ── Mock de tokens para demostración (sin lexer instalado) ───────────────
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
"""
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", ejemplo)
        # Sincronizar la barra de estado con el contenido inicial
        self._actualizar_estado()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BeatScriptIDE()
    app.mainloop()
