# main_gui.py — BeatScript IDE
# Ventana principal del compilador BeatScript
# Framework: customtkinter (modo oscuro) + tkinter.ttk (tablas)

import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
import pygame
import os
from beatscript.parser import BeatScriptParser, ast_to_tree_string, generate_visual_tree

# Apariencia global
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


# Ventana principal
class BeatScriptIDE(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BeatScript IDE")
        self.geometry("1200x800")
        self.after(0, lambda: self.state("zoomed"))

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()

        # AST del último compilado exitoso; None hasta que se compile correctamente
        self.current_ast = None

        self._build_toolbar()
        self._build_main_area()
        self._build_console()
        self._cargar_ejemplo()

    #  Barra superior 
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
            text="Compilar y Reproducir",
            fg_color="#2e7d32",
            hover_color="#388e3c",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=210,
            command=self._compilar,
        ).pack(side="left", padx=(0, 10), pady=10)

        ctk.CTkButton(
            toolbar,
            text="Detener",
            fg_color="#b71c1c",
            hover_color="#c62828",
            font=ctk.CTkFont(size=13),
            width=120,
            command=self._detener,
        ).pack(side="left", padx=(0, 10), pady=10)

        ctk.CTkButton(
            toolbar,
            text="Abrir Archivo",
            fg_color="#1565c0",
            hover_color="#1976d2",
            font=ctk.CTkFont(size=13),
            width=150,
            command=self._abrir_archivo,
        ).pack(side="left", padx=(0, 10), pady=10)

        ctk.CTkButton(
            toolbar,
            text="Guardar Archivo",
            fg_color="#4a148c",
            hover_color="#6a1b9a",
            font=ctk.CTkFont(size=13),
            width=160,
            command=self._guardar_archivo,
        ).pack(side="left", padx=(0, 10), pady=10)

        ctk.CTkButton(
            toolbar,
            text="Catalogo de Errores",
            fg_color="#00695c",
            hover_color="#00796b",
            font=ctk.CTkFont(size=13),
            width=185,
            command=self._mostrar_documentacion_errores,
        ).pack(side="left", padx=(0, 10), pady=10)

    #  Área principal: editor + paneles derechos 
    def _build_main_area(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

        main.columnconfigure(0, weight=5)  # Editor de código
        main.columnconfigure(1, weight=6)  # Paneles derecho
        main.rowconfigure(0, weight=1)

        self._build_editor(main)
        self._build_right_panels(main)

    #  Editor de código (izquierda) con barra de estado 
    _EDITOR_BG  = "#1e1e1e"
    _LINENUM_FG = "#4a5568"

    def _build_editor(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # pack: label arriba, status bar abajo, editor en el medio expandido
        ctk.CTkLabel(
            frame,
            text="Editor de código",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=12, pady=(8, 2))

        # Barra de estado (pack al fondo antes del editor) 
        status_bar = ctk.CTkFrame(frame, height=26, corner_radius=0, fg_color="#1a1a2e")
        status_bar.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_bar,
            text="  Línea: 1, Col: 1  |  Líneas totales: 1",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#78909c",
            anchor="w",
        )
        self.status_label.pack(side="left", padx=4, fill="x", expand=True)

        # ── Contenedor editor: canvas de números │ sep │ textbox 
        editor_container = tk.Frame(frame, bg=self._EDITOR_BG, bd=0)
        editor_container.pack(fill="both", expand=True, padx=8, pady=(0, 0))

        # Canvas para números de línea — dibuja cada número en la posición
        # exacta en píxeles usando dlineinfo, eliminando cualquier desfase
        self._line_canvas = tk.Canvas(
            editor_container,
            width=38,
            bg=self._EDITOR_BG,
            bd=0,
            highlightthickness=0,
            takefocus=False,
        )
        self._line_canvas.pack(side="left", fill="y")

        # Separador visual
        tk.Frame(editor_container, bg="#2a2a3e", width=1).pack(side="left", fill="y")

        # Editor principal
        self.editor = ctk.CTkTextbox(
            editor_container,
            font=("Consolas", 13),
            wrap="none",
            activate_scrollbars=True,
            fg_color=self._EDITOR_BG,
        )
        self.editor.pack(side="left", fill="both", expand=True)

        inner = self.editor._textbox
        inner.config(padx=6, pady=4, bd=0, highlightthickness=0)

        # Scroll: redibujar números en cada movimiento del scroll
        orig_yscroll = inner.cget("yscrollcommand")
        def _yscroll_chain(*args):
            if orig_yscroll:
                self.tk.call(orig_yscroll, *args)
            self.after_idle(self._actualizar_lineas)
        inner.config(yscrollcommand=_yscroll_chain)

        # MouseWheel sobre el canvas también scrollea el editor
        self._line_canvas.bind(
            "<MouseWheel>",
            lambda e: inner.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )

        # Eventos 
        inner.bind("<KeyRelease>",    self._actualizar_estado)
        inner.bind("<ButtonRelease>", self._actualizar_estado)
        inner.bind("<KeyRelease>",    self._on_key, add="+")
        inner.bind("<<Paste>>",       lambda e: self.after_idle(self._actualizar_lineas), add="+")
        inner.bind("<<Cut>>",         lambda e: self.after_idle(self._actualizar_lineas), add="+")
        inner.bind("<<Undo>>",        lambda e: self.after_idle(self._actualizar_lineas), add="+")
        inner.bind("<<Redo>>",        lambda e: self.after_idle(self._actualizar_lineas), add="+")
        inner.bind("<ButtonRelease>", lambda e: self.after_idle(self._actualizar_lineas), add="+")

        # Tags de color para resaltado de sintaxis 
        inner.tag_configure("hl_keyword",    foreground="#7986cb")
        inner.tag_configure("hl_note",       foreground="#66bb6a")
        inner.tag_configure("hl_duration",   foreground="#ffb74d")
        inner.tag_configure("hl_instrument", foreground="#4dd0e1")
        inner.tag_configure("hl_number",     foreground="#ff8a65")
        inner.tag_configure("hl_brace",      foreground="#e0e0e0")
        inner.tag_configure("hl_comment",    foreground="#546e7a")
        inner.tag_configure("hl_identifier", foreground="#cfd8dc")

    #  Panel derecho: tabla de tokens (50%) + árbol AST (50%) 
    def _build_right_panels(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        frame.grid(row=0, column=1, sticky="nsew")

        # Dos filas de igual peso → 50 % / 50 %
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self._build_token_panel(frame)  # Fila 0 — tabla léxica
        self._build_ast_panel(frame)    # Fila 1 — árbol sintáctico

    #  Panel de tokens (mitad superior del área derecha) 
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

        #  Estilo oscuro para el Treeview (ttk no hereda el tema de ctk) 
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

        #  Treeview con columnas: #, TIPO, VALOR, LÍNEA, COL 
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

    #  Panel AST (mitad inferior del área derecha) 
    def _build_ast_panel(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        #  Fila de encabezado: etiqueta + botón de árbol gráfico 
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.columnconfigure(0, weight=1)  # La etiqueta se expande

        self.ast_label = ctk.CTkLabel(
            header,
            text="Árbol Sintáctico — Parser (Etapa 2)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffcc80",
        )
        self.ast_label.grid(row=0, column=0, sticky="w")

        # Botón que abre el árbol de derivación visual (PNG via Graphviz)
        ctk.CTkButton(
            header,
            text="Ver Arbol de Derivacion",
            fg_color="#4527a0",
            hover_color="#512da8",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=210,
            height=28,
            command=self._abrir_arbol_visual,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

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

    #  Consola inferior 
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

    #  Números de línea (canvas) 
    def _actualizar_lineas(self):
        """
        Redibuja los números de línea en el canvas usando dlineinfo.
        Calcula el offset vertical entre el canvas y el _textbox interno
        para compensar el padding interno del CTkTextbox.
        """
        try:
            inner  = self.editor._textbox
            canvas = self._line_canvas
            canvas.delete("all")

            # Offset Y: diferencia entre el origen del canvas y el del _textbox
            # (el CTkTextbox añade padding interno que desplaza el _textbox)
            offset = inner.winfo_rooty() - canvas.winfo_rooty()

            first = int(inner.index("@0,0").split(".")[0])
            last  = int(inner.index(f"@0,{inner.winfo_height()}").split(".")[0])
            cw    = canvas.winfo_width() - 4

            for lineno in range(first, last + 2):
                info = inner.dlineinfo(f"{lineno}.0")
                if info is None:
                    break
                # info[1]=y_top, info[3]=height — aplicar offset del widget
                y_center = info[1] + info[3] // 2 + offset
                canvas.create_text(
                    cw, y_center,
                    text=str(lineno),
                    anchor="e",
                    fill=self._LINENUM_FG,
                    font=("Consolas", 13),
                )
        except Exception:
            pass

    def _on_editor_scroll(self, *args):
        """No se usa con el canvas — el chain en yscrollcommand llama a _actualizar_lineas."""
        pass

    #  Resaltado de sintaxis 
    # Mapa token-type → tag de color
    _TOKEN_TAG = {
        "TEMPO_KW":      "hl_keyword",
        "INSTRUMENT_KW": "hl_keyword",
        "TRACK_KW":      "hl_keyword",
        "REPEAT_KW":     "hl_keyword",
        "CHORD_KW":      "hl_keyword",
        "REST":          "hl_keyword",
        "VOLUME_KW":     "hl_keyword",
        "NOTE":          "hl_note",
        "DURATION":      "hl_duration",
        "INSTR_NAME":    "hl_instrument",
        "NUMBER":        "hl_number",
        "LBRACE":        "hl_brace",
        "RBRACE":        "hl_brace",
        "IDENTIFIER":    "hl_identifier",
    }

    def _on_key(self, event=None):
        """Dispara resaltado y actualización de líneas al escribir."""
        self._aplicar_resaltado()
        self.after_idle(self._actualizar_lineas)

    def _aplicar_resaltado(self):
        """
        Recorre el código fuente con el lexer y aplica tags de color
        al widget tk.Text interno del editor.
        """
        import re
        try:
            from beatscript.lexer import tokenize
        except ImportError:
            return

        inner  = self.editor._textbox
        source = inner.get("1.0", "end-1c")

        # Limpiar todos los tags de resaltado anteriores
        for tag in self._TOKEN_TAG.values():
            inner.tag_remove(tag, "1.0", "end")
        inner.tag_remove("hl_comment", "1.0", "end")

        #  Colorear comentarios primero (regex, el lexer los descarta) 
        for m in re.finditer(r"#[^\n]*", source):
            start = f"1.0 + {m.start()} chars"
            end   = f"1.0 + {m.end()} chars"
            inner.tag_add("hl_comment", start, end)

        #  Colorear tokens devueltos por el lexer 
        try:
            tokens, _ = tokenize(source, collect_errors=True)
        except Exception:
            return

        for tok in tokens:
            tag = self._TOKEN_TAG.get(tok.type)
            if tag is None:
                continue
            tok_len = len(str(tok.value))
            start   = f"1.0 + {tok.lexpos} chars"
            end     = f"1.0 + {tok.lexpos + tok_len} chars"
            inner.tag_add(tag, start, end)

    #  Barra de estado: actualizar posición del cursor 
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

            total = int(inner.index("end-1c").split(".")[0])
            # Descontar línea vacía final si el texto termina en newline
            if inner.get(f"{total}.0", f"{total}.end").strip() == "":
                total = max(1, total - 1)

            self.status_label.configure(
                text=f"  Línea: {linea}, Col: {col}  |  Líneas totales: {total}"
            )
        except Exception:
            pass

    #  Mostrar árbol sintáctico visual 
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

    #  Abrir árbol de derivación visual (Graphviz → PNG) 
    def _abrir_arbol_visual(self):
        """
        Genera el árbol de derivación en PNG usando Graphviz y lo abre
        automáticamente con el visor de imágenes predeterminado de Windows.

        Requiere:
          1. pip install graphviz
          2. Instalar el binario Graphviz desde https://graphviz.org/download/
             y añadirlo al PATH del sistema.
        """
        if self.current_ast is None:
            self._log(
                "  Primero compila el código correctamente para "
                "generar el árbol de derivación."
            )
            return

        self._log("Generando árbol de derivación visual...")
        try:
            ruta = generate_visual_tree(self.current_ast, output_filename="parse_tree")
            self._log(f"  Árbol generado: {ruta}")
            # os.startfile abre la imagen con el visor predeterminado del sistema
            os.startfile(ruta)
        except ImportError:
            self._log("  Error: el paquete Python 'graphviz' no está instalado.")
            self._log("  Solución: pip install graphviz")
        except Exception as e:
            self._log(f"  Error al generar el árbol: {e}")
            if any(k in str(e).lower() for k in ("not found", "dot", "executable")):
                self._log(
                    "  Graphviz no está en el PATH. Instálalo desde "
                    "https://graphviz.org/download/ y marca 'Add to PATH'."
                )

    # Lógica del botón Compilar 
    def _compilar(self):
        self._log("", clear=True)

        source = self.editor.get("1.0", "end-1c").strip()
        if not source:
            self._log("El editor está vacío. Escribe código BeatScript primero.")
            return

        #  ETAPA 1: ANÁLISIS LÉXICO 
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

        #  Llenar la tabla de tokens en el panel derecho 
        self._llenar_tabla_tokens(tokens, source)

        # ── ETAPA 2: ANÁLISIS SINTÁCTICO → Árbol Sintáctico (AST) 
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
            self.current_ast = ast   # Guardar para el botón de árbol gráfico
            self._mostrar_ast(ast)

        except Exception as e:
            self._log(f"Error durante el análisis sintáctico: {e}")
            return

        # Generar y reproducir MIDI 
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

    # Poblar la tabla de tokens del panel derecho 
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
                if siguiente and siguiente.type == "NUMBER":
                    # Caso E44, E44444, etc. — el lexer parte NOTE(E4) + NUMBER(4...)
                    col = self._calcular_columna(source, tok)
                    avisos.append(
                        f"[AVISO] Línea {tok.lineno}, Col {col}: "
                        f"'{tok.value}{siguiente.value}' parece una nota inválida — "
                        f"el número de octava debe ser un solo dígito: ej: E4, C4, D#3"
                    )
                elif siguiente and siguiente.type == "IDENTIFIER":
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

    # Abrir archivo .bs / .txt 
    def _abrir_archivo(self):
        """Abre un diálogo para seleccionar un archivo y carga su contenido en el editor."""
        ruta = filedialog.askopenfilename(
            title="Abrir archivo BeatScript",
            filetypes=[
                ("Archivos BeatScript", "*.bs"),
                ("Archivos de texto",   "*.txt"),
                ("Todos los archivos",  "*.*"),
            ],
        )
        if not ruta:
            return  # El usuario canceló

        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", contenido)
            self._actualizar_estado()
            self.after(100, self._actualizar_lineas)
            self.after(100, self._aplicar_resaltado)
            self.title(f"BeatScript IDE — {os.path.basename(ruta)}")
            self._log(f"Archivo abierto: {ruta}")
        except Exception as e:
            self._log(f"Error al abrir el archivo: {e}")

    #  Guardar archivo .bs / .txt 
    def _guardar_archivo(self):
        """Abre un diálogo para guardar el contenido del editor en un archivo."""
        ruta = filedialog.asksaveasfilename(
            title="Guardar archivo BeatScript",
            defaultextension=".bs",
            filetypes=[
                ("Archivos BeatScript", "*.bs"),
                ("Archivos de texto",   "*.txt"),
                ("Todos los archivos",  "*.*"),
            ],
        )
        if not ruta:
            return  # El usuario canceló

        try:
            contenido = self.editor.get("1.0", "end-1c")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            self.title(f"BeatScript IDE — {os.path.basename(ruta)}")
            self._log(f"Archivo guardado: {ruta}")
        except Exception as e:
            self._log(f"Error al guardar el archivo: {e}")

    # ── Catalogo de errores ───────────────────────────────────────────────────
    def _mostrar_documentacion_errores(self):
        """Ventana con documentacion tecnica de errores en formato de tarjetas."""

        ventana = ctk.CTkToplevel(self)
        ventana.title("Catalogo de Errores - BeatScript")
        ventana.geometry("720x600")
        ventana.resizable(True, True)
        ventana.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 720) // 2
        y = self.winfo_y() + (self.winfo_height() - 600) // 2
        ventana.geometry(f"720x600+{x}+{y}")

        # ── Titulo principal ──────────────────────────────────────────────────
        ctk.CTkLabel(
            ventana,
            text="Documentacion de Errores - BeatScript v1.0",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            ventana,
            text="Clasificacion: Validacion  |  Lexico  |  Sintactico",
            font=ctk.CTkFont(size=11),
            text_color="#546e7a",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        # ── Area scrollable con tarjetas ──────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(ventana, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # ── Helpers ───────────────────────────────────────────────────────────
        def seccion(texto):
            ctk.CTkLabel(
                scroll,
                text=texto,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#80cbc4",
                anchor="w",
            ).pack(fill="x", padx=4, pady=(14, 4))

        def tarjeta(codigo, titulo, causa, resolucion):
            card = ctk.CTkFrame(scroll, corner_radius=10, fg_color="#1e2a2a")
            card.pack(fill="x", padx=4, pady=5)

            # Codigo + Titulo
            ctk.CTkLabel(
                card,
                text=f"{codigo}  {titulo}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#e0e0e0",
                anchor="w",
            ).pack(anchor="w", padx=14, pady=(10, 4))

            sep = ctk.CTkFrame(card, height=1, fg_color="#2e3e3e")
            sep.pack(fill="x", padx=14, pady=(0, 6))

            # Causa
            fila_c = ctk.CTkFrame(card, fg_color="transparent")
            fila_c.pack(fill="x", padx=14, pady=(0, 2))
            ctk.CTkLabel(
                fila_c,
                text="Causa",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#ef9a9a",
                width=80,
                anchor="w",
            ).pack(side="left", anchor="n")
            ctk.CTkLabel(
                fila_c,
                text=causa,
                font=ctk.CTkFont(size=11),
                text_color="#b0bec5",
                wraplength=520,
                justify="left",
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            # Resolucion
            fila_r = ctk.CTkFrame(card, fg_color="transparent")
            fila_r.pack(fill="x", padx=14, pady=(2, 10))
            ctk.CTkLabel(
                fila_r,
                text="Resolucion",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#a5d6a7",
                width=80,
                anchor="w",
            ).pack(side="left", anchor="n")
            ctk.CTkLabel(
                fila_r,
                text=resolucion,
                font=ctk.CTkFont(size=11),
                text_color="#b0bec5",
                wraplength=520,
                justify="left",
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        # ── Seccion 1: Validacion ─────────────────────────────────────────────
        seccion("1. Errores de Validacion Logica  (Warnings)")

        tarjeta(
            "ERR-VAL-01", "Token de Identificador Corrupto",
            causa="El lexer genero un identificador que inicia con una letra valida de nota (A-G) pero contiene sufijos invalidos. Ej: E44, Er21",
            resolucion="Verificar la sintaxis de la nota. El formato estricto es [A-G][#b]?[0-9]",
        )
        tarjeta(
            "ERR-VAL-02", "Tipo de Dato Duracion Desconocido",
            causa="Se esperaba un valor de la enumeracion de duraciones (negra, blanca, etc.) pero se recibio un string no reconocido. Ej: blancaa, negra1",
            resolucion="Usar: negra | blanca | corchea | redonda | semicorchea | fusa | semifusa",
        )

        # ── Seccion 2: Lexico ─────────────────────────────────────────────────
        seccion("2. Errores Lexicos  (Lexical Errors)")

        tarjeta(
            "ERR-LEX-01", "Caracter Ilegal Detectado",
            causa="El automata finito detecto un simbolo que no pertenece al alfabeto de BeatScript. Ej: @tempo, dollar-track, C4!",
            resolucion="Eliminar el caracter no valido. El analizador lo saltara automaticamente pero marcara el error en consola.",
        )

        # ── Seccion 3: Sintactico ─────────────────────────────────────────────
        seccion("3. Errores Sintacticos  (Parsing Errors)")

        tarjeta(
            "ERR-SIN-01", "Violacion de Estructura de Evento",
            causa="Un bloque (track) contiene una secuencia de tokens que no forma un evento musical valido. Ej: NUMBER en lugar de DURATION tras una nota.",
            resolucion="Asegurar que cada instruccion cumpla la regla de produccion: evento -> NOTE DURATION",
        )
        tarjeta(
            "ERR-SIN-02", "EOF Inesperado / Bloque No Cerrado",
            causa="El compilador llego al final del archivo y el stack del parser detecto que falta un delimitador }.",
            resolucion="Cerrar todos los bloques track y repeat que fueron abiertos con {.",
        )
        tarjeta(
            "ERR-SIN-03", "Comando Global No Reconocido",
            causa="Fuera de los bloques se uso una palabra clave no definida como declaracion principal. Ej: trackk en lugar de track.",
            resolucion="El compilador entrara en Modo Panico y descartara tokens hasta encontrar una palabra reservada valida. Corregir la palabra clave.",
        )

        ctk.CTkButton(
            ventana,
            text="Cerrar",
            fg_color="#37474f",
            hover_color="#455a64",
            width=110,
            command=ventana.destroy,
        ).pack(pady=(0, 12))

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
        self._actualizar_estado()
        self.after(100, self._actualizar_lineas)
        self.after(100, self._aplicar_resaltado)


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BeatScriptIDE()
    app.mainloop()
