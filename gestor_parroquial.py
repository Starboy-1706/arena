import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3, os, tempfile, hashlib, secrets, subprocess, sys
import random, json, glob, webbrowser, time, re, html
from datetime import datetime
from contextlib import contextmanager

try:
    from PIL import Image, ImageTk, ImageFilter
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False

CARPETA_FONDOS = "fondos_login"

CSS = {
    "slate_50":  "#FAFAFA",
    "slate_100": "#F5F5F5",
    "slate_200": "#E5E5E5",
    "slate_300": "#D4D4D4",
    "slate_400": "#A3A3A3",
    "slate_500": "#737373",
    "slate_600": "#525252",
    "slate_700": "#404040",
    "slate_800": "#262626",
    "slate_900": "#171717",
    "slate_950": "#0A0A0A",

    "blue_50":   "#FFFBEB",
    "blue_100":  "#FEF3C7",
    "blue_200":  "#FDE68A",
    "blue_300":  "#FCD34D",
    "blue_400":  "#FBBF24",
    "blue_500":  "#D4A017",
    "blue_600":  "#B8860B",
    "blue_700":  "#92400E",
    "blue_800":  "#78350F",
    "blue_900":  "#451A03",
    "blue_950":  "#2A1005",

    "emerald_50":  "#F0FDF4",
    "emerald_100": "#DCFCE7",
    "emerald_500": "#22C55E",
    "emerald_600": "#16A34A",
    "emerald_700": "#15803D",

    "amber_50":  "#FFFBEB",
    "amber_100": "#FEF3C7",
    "amber_500": "#D4A017",
    "amber_600": "#B8860B",
    "amber_700": "#92400E",

    "rose_50":   "#FFF1F2",
    "rose_100":  "#FFE4E6",
    "rose_500":  "#F43F5E",
    "rose_600":  "#E11D48",
    "rose_700":  "#BE123C",

    "violet_50":  "#F5F3FF",
    "violet_100": "#EDE9FE",
    "violet_500": "#8B5CF6",
    "violet_600": "#7C3AED",
    "violet_700": "#6D28D9",

    "cert_bg":     "#FAFAFA",
    "cert_border": "#D4A017",
    "cert_text":   "#262626",
    "cert_accent": "#B8860B",
    "cert_muted":  "#737373",
}

ESTADO_COLOR = {
    "Nuevo":   (CSS["blue_50"],    CSS["blue_600"]),
    "Bueno":   (CSS["emerald_50"], CSS["emerald_600"]),
    "Regular": (CSS["amber_50"],   CSS["amber_600"]),
    "Malo":    (CSS["rose_50"],    CSS["rose_600"]),
}

CATEGORIAS_INV = ["Todas", "Mobiliario", "Liturgico", "Electronico", "Oficina", "Limpieza", "Varios"]
ESTADOS_INV = ["Nuevo", "Bueno", "Regular", "Malo"]
SACRAMENTOS = ["Bautismo", "Comunion", "Confirmacion", "Matrimonio", "Defuncion"]

CONFIG_PARROQUIA = {
    "diocesis":     "DIÓCESIS DE EL VIGÍA-SAN CARLOS DEL ZULIA",
    "parroquia":    "PARROQUIA SANTA BÁRBARA",
    "direccion":    "Dirección: Sector 20 de mayo Av. 13, Calle 8. Telf.: 0275-5551649",
    "zona_postal":  "Zona Postal- 4157. Santa Bárbara del Zulia-Municipio Colon, Estado Zulia – Venezuela.",
    "rif":          "Rif: J-40302676-9",
    "color_lineas": "#D4A017",
}

MAX_INTENTOS = 5
BLOQUEO_BASE_SEG = 30 
MAX_LONGITUD_CAMPO = 64     

def hash_con_sal(pw: str, sal: str = None):
    if sal is None:
        sal = secrets.token_hex(16)
    h = hashlib.sha256((sal + pw).encode('utf-8')).hexdigest()
    return f"{sal}:{h}"

def verificar_pw(pw: str, almacenado: str) -> bool:
    try:
        sal, esperado = almacenado.split(":", 1)
        return hash_con_sal(pw, sal).split(":", 1)[1] == esperado
    except (ValueError, AttributeError):
        if len(almacenado) == 64:
            return hashlib.sha256(pw.encode('utf-8')).hexdigest() == almacenado
        return False

def sanitizar_usuario(texto: str) -> str:
    """Solo permite alfanumericos, puntos y guiones bajos"""
    return re.sub(r'[^a-zA-Z0-9._]', '', texto)[:MAX_LONGITUD_CAMPO]

def entero_seguro(valor, defecto=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto

def abrir_archivo(path: str):
    try:
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[Error] No se pudo abrir archivo: {e}")

def limpiar_temporales():
    d = tempfile.gettempdir()
    for pat in ['parroquia_*.txt', 'parroquia_*.html']:
        for f in glob.glob(os.path.join(d, pat)):
            try: os.remove(f)
            except: pass

DB_PATH = 'parroquia_unificado.db'

@contextmanager
def db_cursor():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con.cursor(), con
        con.commit()
    except Exception as e:
        con.rollback()
        raise e
    finally:
        con.close()

def inicializar_bd():
    with db_cursor() as (c, con):
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL CHECK(rol IN ('superusuario','secretaria','pastor')),
            ultimo_acceso TEXT,
            intentos_fallidos INTEGER DEFAULT 0,
            bloqueado_hasta TEXT
        )''')
        c.execute("PRAGMA table_info(certificados_inexistencia)")
        columnas = [col[1] for col in c.fetchall()]
        for col in ['testigo1_nombre', 'testigo1_ci', 'testigo1_parentesco',
                     'testigo2_nombre', 'testigo2_ci', 'testigo2_parentesco',
                     'libros_buscados']:
            if col not in columnas:
                c.execute(f"ALTER TABLE certificados_inexistencia ADD COLUMN {col} TEXT")
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_bautismo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, fecha_bautizo TEXT, fecha_nacimiento TEXT,
            padre TEXT, madre TEXT, padrino TEXT, madrina TEXT, ministro TEXT,
            ecl_libro TEXT NOT NULL, ecl_folio TEXT NOT NULL, ecl_num TEXT NOT NULL, ecl_ano TEXT,
            civil_num TEXT, civil_tomo TEXT, civil_folio TEXT, civil_ano TEXT,
            civil_parroquia TEXT, civil_municipio TEXT, civil_estado TEXT,
            nota_marginal TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_comunion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, fecha_comunion TEXT,
            padre TEXT, madre TEXT, padrino TEXT, madrina TEXT, ministro TEXT,
            ecl_libro TEXT NOT NULL, ecl_folio TEXT NOT NULL, ecl_num TEXT NOT NULL, ecl_ano TEXT,
            nota_marginal TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_confirmacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, fecha_confirmacion TEXT,
            padre TEXT, madre TEXT, padrino TEXT, ministro TEXT,
            ecl_libro TEXT NOT NULL, ecl_folio TEXT NOT NULL, ecl_num TEXT NOT NULL, ecl_ano TEXT,
            nota_marginal TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_matrimonio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            esposo TEXT NOT NULL, esposa TEXT NOT NULL, fecha_matrimonio TEXT,
            testigo1 TEXT, testigo2 TEXT, ministro TEXT,
            ecl_libro TEXT NOT NULL, ecl_folio TEXT NOT NULL, ecl_num TEXT NOT NULL, ecl_ano TEXT,
            civil_num TEXT, civil_tomo TEXT, civil_folio TEXT, civil_ano TEXT,
            civil_parroquia TEXT, civil_municipio TEXT, civil_estado TEXT,
            nota_marginal TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_defuncion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, fecha_defuncion TEXT, fecha_entierro TEXT,
            conyuge TEXT, madre TEXT, lugar_sepultura TEXT, cementerio TEXT,
            causa_muerte TEXT, ministro TEXT,
            ecl_libro TEXT NOT NULL, ecl_folio TEXT NOT NULL, ecl_num TEXT NOT NULL, ecl_ano TEXT,
            civil_num TEXT, civil_libro TEXT, civil_tomo TEXT, civil_folio TEXT, civil_ano TEXT,
            civil_parroquia TEXT, civil_municipio TEXT, civil_estado TEXT,
            nota_marginal TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_inexistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_sacramento TEXT NOT NULL,
            nombre TEXT NOT NULL,
            fecha_nacimiento TEXT,
            padre TEXT, madre TEXT,
            lugar_busqueda TEXT,
            anio_desde TEXT, anio_hasta TEXT,
            resultado TEXT DEFAULT 'No se encontró registro',
            ministro TEXT,
            fecha_emision TEXT,
            nota TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS certificados_participacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_sacramento TEXT NOT NULL DEFAULT 'Matrimonio',
            nombre_esposo TEXT NOT NULL,
            nombre_esposa TEXT NOT NULL,
            fecha_matrimonio TEXT,
            parroquia_destino TEXT,
            diocesis_destino TEXT,
            ministro TEXT,
            fecha_emision TEXT,
            nota TEXT
        )''')
        for sacr in ['bautismo', 'comunion', 'confirmacion', 'matrimonio', 'defuncion']:
            old_tbl = f"actas_{sacr}"
            new_tbl = f"certificados_{sacr}"
            try:
                c.execute(f"SELECT COUNT(*) FROM {old_tbl}")
                old_count = c.fetchone()[0]
                c.execute(f"SELECT COUNT(*) FROM {new_tbl}")
                new_count = c.fetchone()[0]
                if old_count > 0 and new_count == 0:
                    c.execute(f"SELECT * FROM {old_tbl}")
                    rows = c.fetchall()
                    c.execute(f"PRAGMA table_info({old_tbl})")
                    cols = [col[1] for col in c.fetchall()]
                    placeholders = ','.join(['?'] * len(cols))
                    col_names = ','.join(cols)
                    for row in rows:
                        c.execute(f"INSERT INTO {new_tbl} ({col_names}) VALUES ({placeholders})", row)
                    print(f"[Migracion] {old_count} registros migrados de {old_tbl} -> {new_tbl}")
            except sqlite3.OperationalError:
                pass
        for tbl in ['certificados_bautismo', 'certificados_matrimonio']:
            c.execute(f"PRAGMA table_info({tbl})")
            columnas = [col[1] for col in c.fetchall()]
            if 'civil_libro' not in columnas:
                c.execute(f"ALTER TABLE {tbl} ADD COLUMN civil_libro TEXT")
        c.execute('''CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            descripcion TEXT NOT NULL,
            unidad_medida TEXT DEFAULT 'Unidad',
            ubicacion TEXT,
            cantidad INTEGER DEFAULT 0,
            categoria TEXT DEFAULT 'Varios',
            estado TEXT DEFAULT 'Bueno' CHECK(estado IN ('Nuevo','Bueno','Regular','Malo')),
            fecha_registro TEXT
        )''')
        c.execute("PRAGMA table_info(certificados_defuncion)")
        columnas = [col[1] for col in c.fetchall()]
        for col in [
            'civil_num', 'civil_libro', 'civil_tomo', 'civil_folio',
            'civil_ano', 'civil_parroquia', 'civil_municipio', 'civil_estado'
        ]:
            if col not in columnas:
                c.execute(f"ALTER TABLE certificados_defuncion ADD COLUMN {col} TEXT")
        c.execute("SELECT COUNT(*) FROM usuarios")
        if c.fetchone()[0] == 0:
            for u, n, p, r in [
                ('admin',  'Pbro. Luis Manuel Sanchez',    'admin123',  'superusuario'),
                ('secre',  'Hermana Clara Gomez',           'secre123',  'secretaria'),
                ('pastor', 'Diacono Francisco Ruiz',        'pastor123', 'pastor'),
            ]:
                c.execute("INSERT INTO usuarios (usuario,nombre,password,rol) VALUES (?,?,?,?)",
                          (u, n, hash_con_sal(p), r))
        c.execute("PRAGMA table_info(certificados_participacion)")
        columnas = [col[1] for col in c.fetchall()]
        if 'tipo_sacramento' not in columnas:
            c.execute("ALTER TABLE certificados_participacion ADD COLUMN tipo_sacramento TEXT DEFAULT 'Matrimonio'")

class Boton(tk.Label):
    def __init__(self, parent, texto="", comando=None, color=None, fg="white",
                 fuente=None, padx=20, pady=9, cursor="hand2"):
        self._color = color or CSS["blue_600"]
        self._hover = self._ajustar(self._color, 0.88)
        self._pressed = self._ajustar(self._color, 0.76)
        self._fg = fg
        self._cmd = comando
        self._deshabilitado = False

        super().__init__(
            parent,
            text=texto,
            font=fuente or ("Segoe UI", 10, "bold"),
            bg=self._color,
            fg=self._fg,
            padx=padx,
            pady=pady,
            cursor=cursor,
            relief='flat',
            bd=0
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, e):
        if not self._deshabilitado:
            self.config(bg=self._hover)

    def _on_leave(self, e):
        if not self._deshabilitado:
            self.config(bg=self._color)

    def _on_click(self, e):
        if not self._deshabilitado:
            self.config(bg=self._pressed)

    def _on_release(self, e):
        if not self._deshabilitado:
            self.config(bg=self._hover)
            if self._cmd:
                self._cmd()

    def deshabilitar(self):
        self._deshabilitado = True
        self.config(bg=CSS["slate_300"], fg=CSS["slate_500"], cursor="")

    def habilitar(self):
        self._deshabilitado = False
        self.config(bg=self._color, fg=self._fg, cursor="hand2")

    @staticmethod
    def _ajustar(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f'#{r:02x}{g:02x}{b:02x}'
    
class Notificacion(tk.Toplevel):
    def __init__(self, parent, mensaje, tipo="exito"):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        colores = {
            "exito":   ("#F0FDF4", "#16A34A", "✓"),
            "error":   ("#FFF1F2", "#E11D48", "✗"),
            "aviso":   ("#FFFBEB", "#B8860B", "⚠"),
        }
        bg, fg, icono = colores.get(tipo, colores["exito"])
        self.config(bg=bg, highlightbackground=fg, highlightthickness=2)
        f = tk.Frame(self, bg=bg, padx=20, pady=14)
        f.pack()
        tk.Label(f, text=icono, font=("Segoe UI", 14, "bold"), bg=bg, fg=fg).pack(side='left', padx=(0, 10))
        tk.Label(f, text=mensaje, font=("Segoe UI", 10), bg=bg, fg="#262626").pack(side='left')
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + parent.winfo_width() - self.winfo_width() - 24
            y = parent.winfo_rooty() + 24
            self.geometry(f"+{x}+{y}")
        except:
            self.geometry("+800+50")
        self.after(3500, self.destroy)

class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor Parroquial · Acceso")
        self.root.configure(bg="#171717")
        self.root.resizable(False, False)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(480, sw - 40), min(620, sh - 80)
        self._win_w, self._win_h = w, h
        self.root.geometry(f'{w}x{h}+{(sw - w)//2}+{(sh - h)//2}')
        self._bg_img = None
        self._intentos_fallidos = 0
        self._rondas_bloqueo = 0
        self._bloqueado_hasta = 0
        self._timer_id = None
        self._pw_visible = False
        self._construir()

    def _buscar_fondo(self):
        if not PIL_DISPONIBLE:
            return None
        base = os.path.dirname(os.path.abspath(__file__))
        carpeta = os.path.join(base, CARPETA_FONDOS)
        if not os.path.isdir(carpeta):
            try:
                os.makedirs(carpeta, exist_ok=True)
                readme = os.path.join(carpeta, "LEEME.txt")
                if not os.path.exists(readme):
                    with open(readme, 'w', encoding='utf-8') as f:
                        f.write("Coloca aqui tus fotos para el fondo del login.\n")
                        f.write("Formatos: .jpg .jpeg .png .bmp .gif\n")
            except:
                pass
            return None
        imagenes = []
        for ext in ('*.jpg','*.jpeg','*.png','*.bmp','*.gif','*.JPG','*.JPEG','*.PNG','*.BMP','*.GIF'):
            imagenes.extend(glob.glob(os.path.join(carpeta, ext)))
        return random.choice(imagenes) if imagenes else None

    def _crear_fondo(self, ruta):
        try:
            img = Image.open(ruta)
            w, h = self._win_w, self._win_h
            escala = max(w / img.width, h / img.height)
            img = img.resize((int(img.width * escala), int(img.height * escala)), Image.LANCZOS)
            izq = (img.width - w) // 2
            arr = (img.height - h) // 2
            img = img.crop((izq, arr, izq + w, arr + h))
            img = img.filter(ImageFilter.GaussianBlur(radius=4))
            overlay = Image.new('RGBA', (w, h), (23, 23, 23, 180))
            img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay)
            return ImageTk.PhotoImage(img.convert('RGB'))
        except Exception as e:
            print(f"[Aviso] Fondo no cargado: {e}")
            return None

    def _construir(self):
        ruta = self._buscar_fondo()
        if ruta:
            self._bg_img = self._crear_fondo(ruta)
        if self._bg_img:
            tk.Label(self.root, image=self._bg_img).place(relwidth=1, relheight=1)
        else:
            tk.Frame(self.root, bg="#171717").place(relwidth=1, relheight=1)

        # ═══ Tarjeta principal ═══
        card = tk.Frame(self.root, bg="#FAFAFA")
        card.place(relx=0.5, rely=0.5, anchor='center', width=380, height=520)

        # ─── Encabezado ───
        hdr = tk.Frame(card, bg="#FAFAFA", padx=40, pady=0)
        hdr.pack(fill='x')

        # Cruz dorada
        cruz_frame = tk.Frame(hdr, bg="#D4A017", width=48, height=48)
        cruz_frame.pack(pady=(28, 14))
        cruz_frame.pack_propagate(False)
        tk.Label(cruz_frame, text="✝", font=("Segoe UI", 22, "bold"),
                 bg="#D4A017", fg="#FAFAFA").place(relx=.5, rely=.5, anchor='center')

        tk.Label(hdr, text="Gestor Parroquial",
                 font=("Segoe UI", 18, "bold"), bg="#FAFAFA", fg="#262626").pack()

        tk.Label(hdr, text="Diócesis El Vigía – San Carlos del Zulia",
                 font=("Segoe UI", 8), bg="#FAFAFA", fg="#A3A3A3").pack(pady=(2, 0))

        # Línea dorada
        tk.Frame(hdr, bg="#D4A017", height=2).pack(fill='x', pady=(16, 0))

        # ─── Formulario ───
        fm = tk.Frame(card, bg="#FAFAFA", padx=40)
        fm.pack(fill='both', expand=True, pady=(20, 0))

        # Usuario
        tk.Label(fm, text="USUARIO", font=("Segoe UI", 8, "bold"),
                 bg="#FAFAFA", fg="#737373").pack(anchor='w')

        uf_border = tk.Frame(fm, bg="#D4D4D4")
        uf_border.pack(fill='x', pady=(4, 16))
        self.e_user = tk.Entry(uf_border, font=("Segoe UI", 11), bg="#FFFFFF",
                               fg="#262626", relief='flat', insertbackground="#262626")
        self.e_user.pack(fill='x', padx=1, pady=1, ipady=8)
        self.e_user.focus()

        # Contraseña
        tk.Label(fm, text="CONTRASEÑA", font=("Segoe UI", 8, "bold"),
                 bg="#FAFAFA", fg="#737373").pack(anchor='w')

        pf_border = tk.Frame(fm, bg="#D4D4D4")
        pf_border.pack(fill='x', pady=(4, 8))
        pf_inner = tk.Frame(pf_border, bg="#FFFFFF")
        pf_inner.pack(fill='x', padx=1, pady=1)

        self.e_pass = tk.Entry(pf_inner, font=("Segoe UI", 11), bg="#FFFFFF",
                               fg="#262626", relief='flat', show="●",
                               insertbackground="#262626")
        self.e_pass.pack(side='left', fill='x', expand=True, ipady=8)
        self.e_pass.bind('<Return>', lambda e: self._login())

        self.btn_ojo = tk.Label(pf_inner, text="👁", font=("Segoe UI", 11),
                                bg="#FFFFFF", fg="#A3A3A3", padx=10, cursor="hand2")
        self.btn_ojo.pack(side='right')
        self.btn_ojo.bind("<Button-1>", lambda e: self._toggle_pw_visibility())
        self.btn_ojo.bind("<Enter>", lambda e: self.btn_ojo.config(fg="#525252"))
        self.btn_ojo.bind("<Leave>", lambda e: self.btn_ojo.config(fg="#A3A3A3"))

        # Estado
        self.frm_estado = tk.Frame(fm, bg="#FAFAFA")
        self.frm_estado.pack(fill='x', pady=(0, 6))
        self.lbl_estado = tk.Label(self.frm_estado, text="", font=("Segoe UI", 9),
                                   bg="#FAFAFA", fg="#737373")
        self.lbl_estado.pack(anchor='w')

        # Bloqueo
        self.frm_bloqueo = tk.Frame(fm, bg="#FFF1F2", padx=12, pady=10)
        self.lbl_bloqueo = tk.Label(self.frm_bloqueo, text="", font=("Segoe UI", 9, "bold"),
                                    bg="#FFF1F2", fg="#E11D48")
        self.lbl_bloqueo.pack()
        self.lbl_timer = tk.Label(self.frm_bloqueo, text="", font=("Segoe UI", 11, "bold"),
                                  bg="#FFF1F2", fg="#E11D48")
        self.lbl_timer.pack()

        # Botón
        self.btn_login = Boton(fm, texto="Ingresar", comando=self._login,
                               color="#D4A017", fg="#FFFFFF", padx=0, pady=12,
                               fuente=("Segoe UI", 12, "bold"))
        self.btn_login.pack(fill='x', pady=(4, 0))

        # ─── Footer ───
        footer = tk.Frame(card, bg="#FAFAFA", padx=40)
        footer.pack(fill='x', pady=(12, 18))

        tk.Frame(footer, bg="#E5E5E5", height=1).pack(fill='x', pady=(0, 10))

        ft_row = tk.Frame(footer, bg="#FAFAFA")
        ft_row.pack()
        tk.Label(ft_row, text="🛡", font=("Segoe UI", 9),
                 bg="#FAFAFA", fg="#D4A017").pack(side='left', padx=(0, 6))
        tk.Label(ft_row, text="Acceso protegido",
                 font=("Segoe UI", 8), fg="#A3A3A3", bg="#FAFAFA").pack(side='left')

        tk.Label(footer, text="v5.1",
                 font=("Segoe UI", 8), bg="#FAFAFA", fg="#D4D4D4").pack(pady=(6, 0))

    def _toggle_pw_visibility(self):
        self._pw_visible = not self._pw_visible
        if self._pw_visible:
            self.e_pass.config(show="")
            self.btn_ojo.config(text="🔒")
        else:
            self.e_pass.config(show="●")
            self.btn_ojo.config(text="👁")

    def _esta_bloqueado(self):
        return time.time() < self._bloqueado_hasta

    def _tiempo_restante(self):
        return max(0, int(self._bloqueado_hasta - time.time()))

    def _iniciar_bloqueo(self):
        duracion = BLOQUEO_BASE_SEG * (2 ** self._rondas_bloqueo)
        self._bloqueado_hasta = time.time() + duracion
        self._rondas_bloqueo += 1
        self.btn_login.deshabilitar()
        self.e_user.config(state='disabled')
        self.e_pass.config(state='disabled')
        self.frm_bloqueo.pack(fill='x', pady=(0, 8))
        self.lbl_bloqueo.config(text=f"Cuenta bloqueada por {duracion} segundos")
        self._actualizar_timer()

    def _actualizar_timer(self):
        restante = self._tiempo_restante()
        if restante > 0:
            mins = restante // 60
            segs = restante % 60
            self.lbl_timer.config(text=f"Espere: {mins:02d}:{segs:02d}")
            self.lbl_estado.config(text="⛔ Demasiados intentos fallidos", fg="#E11D48")
            self._timer_id = self.root.after(1000, self._actualizar_timer)
        else:
            self._desbloquear()

    def _desbloquear(self):
        self._intentos_fallidos = 0
        self._bloqueado_hasta = 0
        self.btn_login.habilitar()
        self.e_user.config(state='normal')
        self.e_pass.config(state='normal')
        self.frm_bloqueo.pack_forget()
        self.lbl_estado.config(text="Cuenta desbloqueada. Intente de nuevo.", fg="#16A34A")
        if self._timer_id:
            try:
                self.root.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None

    def _registrar_acceso(self, usuario, resultado):
        try:
            with db_cursor() as (c, con):
                c.execute("INSERT INTO log_accesos (usuario, fecha, resultado) VALUES (?,?,?)",
                          (usuario, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), resultado))
        except Exception:
            pass

    def _login(self):
        if self._esta_bloqueado():
            Notificacion(self.root, f"Cuenta bloqueada. Espere {self._tiempo_restante()}s", "error")
            return

        u_raw = self.e_user.get().strip()
        p = self.e_pass.get()
        if not u_raw or not p:
            self.lbl_estado.config(text="Complete ambos campos", fg="#B8860B")
            return
        if len(u_raw) > MAX_LONGITUD_CAMPO or len(p) > MAX_LONGITUD_CAMPO:
            self.lbl_estado.config(text="Entrada demasiado larga", fg="#E11D48")
            return
        u = sanitizar_usuario(u_raw).lower()
        if not u:
            self.lbl_estado.config(text="Usuario contiene caracteres no permitidos", fg="#E11D48")
            return

        try:
            with db_cursor() as (c, con):
                c.execute("SELECT id,usuario,nombre,rol,password,bloqueado_hasta,intentos_fallidos FROM usuarios WHERE usuario=?", (u,))
                row = c.fetchone()
        except Exception:
            self.lbl_estado.config(text="Error interno del sistema", fg="#E11D48")
            return

        if row and row[5]:
            try:
                bloqueo_bd = datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S")
                if datetime.now() < bloqueo_bd:
                    self.lbl_estado.config(text="Esta cuenta esta temporalmente suspendida", fg="#E11D48")
                    self._registrar_acceso(u, "bloqueado")
                    return
                with db_cursor() as (c, con):
                    c.execute("UPDATE usuarios SET intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=?", (row[0],))
                row = row[:6] + (0,)
            except ValueError:
                pass

        if row and verificar_pw(p, row[4]):
            self._registrar_acceso(u, "exitoso")
            try:
                with db_cursor() as (c, con):
                    c.execute("UPDATE usuarios SET ultimo_acceso=?, intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=?",
                              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row[0]))
            except Exception:
                pass

            self._intentos_fallidos = 0
            self._rondas_bloqueo = 0
            self._bg_img = None

            for w in self.root.winfo_children():
                w.destroy()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            mw, mh = min(1440, sw - 40), min(940, sh - 60)
            self.root.geometry(f'{mw}x{mh}+{(sw - mw)//2}+{(sh - mh)//2}')
            self.root.resizable(True, True)
            AplicacionPrincipal(self.root, uid=row[0], usuario=row[1], nombre=row[2], rol=row[3])
        else:
            self._intentos_fallidos += 1
            self._registrar_acceso(u if u else "(vacio)", "fallido")
            if row:
                total_fallos = entero_seguro(row[6], 0) + 1
                try:
                    with db_cursor() as (c, con):
                        c.execute("UPDATE usuarios SET intentos_fallidos=? WHERE id=?", (total_fallos, row[0]))
                except Exception:
                    pass
                restantes = MAX_INTENTOS - total_fallos
            else:
                restantes = MAX_INTENTOS - self._intentos_fallidos

            if restantes <= 0:
                self._iniciar_bloqueo()
                if row:
                    duracion = BLOQUEO_BASE_SEG * (2 ** (self._rondas_bloqueo - 1))
                    bloqueo_hasta = datetime.now()
                    from datetime import timedelta
                    bloqueo_hasta = (bloqueo_hasta + timedelta(seconds=duracion)).strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        with db_cursor() as (c, con):
                            c.execute("UPDATE usuarios SET bloqueado_hasta=? WHERE id=?",
                                      (bloqueo_hasta, row[0]))
                    except Exception:
                        pass
            else:
                self.lbl_estado.config(
                    text=f"Credenciales incorrectas · {restantes} intento{'s' if restantes != 1 else ''} restante{'s' if restantes != 1 else ''}",
                    fg="#E11D48")
                if restantes <= 2:
                    self.lbl_estado.config(
                        text=f"⚠ {restantes} intento{'s' if restantes != 1 else ''} antes del bloqueo",
                        fg="#E11D48")

            self.e_pass.delete(0, tk.END)

class AplicacionPrincipal:
    TIPOS_INEXISTENCIA = ["Bautismo", "Comunion", "Confirmacion", "Matrimonio"]
    def _construir_inexistencias(self):
        f = self.frames['inexistencias']
        main = tk.Frame(f, bg=CSS["slate_50"])
        main.pack(expand=True, fill='both')

        left = tk.Frame(main, bg=CSS["slate_50"])
        left.pack(side='left', fill='both', expand=True, padx=(0, 10))
        pf = tk.Frame(left, bg=CSS["slate_50"]); pf.pack(fill='x', pady=(0, 8))
        self._inex_tipo_btns = {}
        for tp, clr in [("Bautismo", CSS["blue_500"]), ("Comunion", CSS["amber_500"]),
                         ("Confirmacion", CSS["violet_500"]), ("Matrimonio", CSS["rose_500"])]:
            b = tk.Label(pf, text=f"  {tp}", font=("Segoe UI", 8, "bold"),
                         bg="white", fg=CSS["slate_500"], padx=10, pady=6, cursor="hand2")
            b.pack(side='left', padx=2)
            b.bind("<Button-1>", lambda e, t=tp: self._sel_tipo_inex(t))
            self._inex_tipo_btns[tp] = (b, clr)

        cf = tk.Frame(left, bg=CSS["slate_50"]); cf.pack(fill='both', expand=True)
        self._inex_canvas = tk.Canvas(cf, bg=CSS["slate_50"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(cf, orient="vertical", command=self._inex_canvas.yview)
        self._inex_ff = tk.Frame(self._inex_canvas, bg="white")
        self._inex_ff.bind("<Configure>", lambda e: self._inex_canvas.configure(scrollregion=self._inex_canvas.bbox("all")))
        self._inex_canvas.create_window((0, 0), window=self._inex_ff, anchor="nw")
        self._inex_canvas.configure(yscrollcommand=sb.set)
        self._inex_canvas.bind('<Configure>', lambda e: self._inex_canvas.itemconfig(1, width=e.width))
        self._inex_canvas.bind("<Enter>", lambda e: self._inex_canvas.bind_all("<MouseWheel>", lambda ev: self._inex_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        self._inex_canvas.bind("<Leave>", lambda e: self._inex_canvas.unbind_all("<MouseWheel>"))
        sb.pack(side="right", fill="y"); self._inex_canvas.pack(side="left", fill="both", expand=True)

        self._inex_entries = {}
        self._inex_tipo_actual = "Bautismo"
        self._inex_selected_id = None
        self._construir_formulario_inex()

        bf = tk.Frame(left, bg=CSS["slate_50"], pady=6); bf.pack(fill='x')
        puede_editar = self.rol != 'pastor'
        if puede_editar:
            Boton(bf, texto="💾 Guardar", comando=self._inex_guardar, color=CSS["blue_600"]).pack(side='left', padx=(0, 3))
            Boton(bf, texto="🔄 Actualizar", comando=self._inex_actualizar, color=CSS["emerald_600"]).pack(side='left', padx=3)
            if self.rol == 'superusuario':
                Boton(bf, texto="🗑 Eliminar", comando=self._inex_eliminar, color=CSS["rose_600"]).pack(side='left', padx=3)
            Boton(bf, texto="✕ Limpiar", comando=self._inex_limpiar, color=CSS["slate_500"]).pack(side='left', padx=3)
        Boton(bf, texto="🖨 Imprimir", comando=self._inex_imprimir, color=CSS["slate_700"]).pack(side='right')

        right = tk.Frame(main, bg="white", width=380)
        right.pack(side='right', fill='y'); right.pack_propagate(False)

        rh = tk.Frame(right, bg="white", padx=14, pady=8); rh.pack(fill='x')
        tk.Label(rh, text="Inexistencias", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_800"]).pack(side='left')
        self._inex_lbl_cnt = tk.Label(rh, text="0 registros", font=("Segoe UI", 8),
                                      bg=CSS["slate_100"], fg=CSS["slate_500"], padx=6, pady=2)
        self._inex_lbl_cnt.pack(side='right')

        tk.Frame(right, bg=CSS["slate_100"], height=1).pack(fill='x')

        trf = tk.Frame(right, bg="white"); trf.pack(fill='both', expand=True, padx=4, pady=4)
        self._inex_tree = ttk.Treeview(trf, columns=("ID", "Tipo", "Nombre"), show='headings', style="A.Treeview")
        for col, w in [("ID", 40), ("Tipo", 100), ("Nombre", 200)]:
            self._inex_tree.column(col, width=w, anchor='center' if col == "ID" else 'w')
            self._inex_tree.heading(col, text=col)
        tsb = ttk.Scrollbar(trf, orient="vertical", command=self._inex_tree.yview)
        self._inex_tree.configure(yscrollcommand=tsb.set)
        self._inex_tree.pack(side='left', fill='both', expand=True); tsb.pack(side='right', fill='y')
        self._inex_tree.bind("<<TreeviewSelect>>", self._on_sel_inex)

    def _construir_participaciones(self):
        f = self.frames['participaciones']
        main = tk.Frame(f, bg=CSS["slate_50"])
        main.pack(expand=True, fill='both')

        left = tk.Frame(main, bg=CSS["slate_50"])
        left.pack(side='left', fill='both', expand=True, padx=(0, 10))

        pf = tk.Frame(left, bg=CSS["slate_50"]); pf.pack(fill='x', pady=(0, 8))
        self._part_tipo_btns = {}
        for tp, clr in [("Bautismo", CSS["blue_500"]), ("Comunion", CSS["amber_500"]),
                         ("Confirmacion", CSS["violet_500"]), ("Matrimonio", CSS["rose_500"])]:
            b = tk.Label(pf, text=f"  {tp}", font=("Segoe UI", 8, "bold"),
                         bg="white", fg=CSS["slate_500"], padx=10, pady=6, cursor="hand2")
            b.pack(side='left', padx=2)
            b.bind("<Button-1>", lambda e, t=tp: self._sel_tipo_part(t))
            self._part_tipo_btns[tp] = (b, clr)

        cf = tk.Frame(left, bg=CSS["slate_50"]); cf.pack(fill='both', expand=True)
        self._part_canvas = tk.Canvas(cf, bg=CSS["slate_50"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(cf, orient="vertical", command=self._part_canvas.yview)
        self._part_ff = tk.Frame(self._part_canvas, bg="white")
        self._part_ff.bind("<Configure>", lambda e: self._part_canvas.configure(scrollregion=self._part_canvas.bbox("all")))
        self._part_canvas.create_window((0, 0), window=self._part_ff, anchor="nw")
        self._part_canvas.configure(yscrollcommand=sb.set)
        self._part_canvas.bind('<Configure>', lambda e: self._part_canvas.itemconfig(1, width=e.width))
        self._part_canvas.bind("<Enter>", lambda e: self._part_canvas.bind_all("<MouseWheel>", lambda ev: self._part_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        self._part_canvas.bind("<Leave>", lambda e: self._part_canvas.unbind_all("<MouseWheel>"))
        sb.pack(side="right", fill="y"); self._part_canvas.pack(side="left", fill="both", expand=True)

        self._part_entries = {}
        self._part_tipo_actual = "Matrimonio"
        self._part_selected_id = None
        self._construir_formulario_part()

        bf = tk.Frame(left, bg=CSS["slate_50"], pady=6); bf.pack(fill='x')
        puede_editar = self.rol != 'pastor'
        if puede_editar:
            Boton(bf, texto="💾 Guardar", comando=self._part_guardar, color=CSS["blue_600"]).pack(side='left', padx=(0, 3))
            Boton(bf, texto="🔄 Actualizar", comando=self._part_actualizar, color=CSS["emerald_600"]).pack(side='left', padx=3)
            if self.rol == 'superusuario':
                Boton(bf, texto="🗑 Eliminar", comando=self._part_eliminar, color=CSS["rose_600"]).pack(side='left', padx=3)
            Boton(bf, texto="✕ Limpiar", comando=self._part_limpiar, color=CSS["slate_500"]).pack(side='left', padx=3)
        Boton(bf, texto="🖨 Imprimir", comando=self._part_imprimir, color=CSS["slate_700"]).pack(side='right')

        right = tk.Frame(main, bg="white", width=380)
        right.pack(side='right', fill='y'); right.pack_propagate(False)

        rh = tk.Frame(right, bg="white", padx=14, pady=8); rh.pack(fill='x')
        tk.Label(rh, text="Participaciones", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_800"]).pack(side='left')
        self._part_lbl_cnt = tk.Label(rh, text="0 registros", font=("Segoe UI", 8),
                                      bg=CSS["slate_100"], fg=CSS["slate_500"], padx=6, pady=2)
        self._part_lbl_cnt.pack(side='right')

        tk.Frame(right, bg=CSS["slate_100"], height=1).pack(fill='x')

        trf = tk.Frame(right, bg="white"); trf.pack(fill='both', expand=True, padx=4, pady=4)
        self._part_tree = ttk.Treeview(trf, columns=("ID", "Tipo", "Nombre"), show='headings', style="A.Treeview")
        for col, w in [("ID", 40), ("Tipo", 100), ("Nombre", 200)]:
            self._part_tree.column(col, width=w, anchor='center' if col == "ID" else 'w')
            self._part_tree.heading(col, text=col)
        tsb = ttk.Scrollbar(trf, orient="vertical", command=self._part_tree.yview)
        self._part_tree.configure(yscrollcommand=tsb.set)
        self._part_tree.pack(side='left', fill='both', expand=True); tsb.pack(side='right', fill='y')
        self._part_tree.bind("<<TreeviewSelect>>", self._on_sel_part)


        s1 = self._card(self._part_ff, "Datos de los Contrayentes", CSS["rose_50"])
        row1 = tk.Frame(s1, bg="white"); row1.pack(fill='x', pady=(4, 0))
        self._campo(row1, "NOMBRE DEL ESPOSO *", 22, 'nombre_esposo', store=self._part_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row1, "NOMBRE DE LA ESPOSA *", 22, 'nombre_esposa', store=self._part_entries)[0].pack(side='left', fill='x', expand=True)

        row2 = tk.Frame(s1, bg="white"); row2.pack(fill='x', pady=(8, 0))
        self._campo(row2, "FECHA DE MATRIMONIO", 14, 'fecha_matrimonio', store=self._part_entries)[0].pack(side='left', fill='x', expand=True)

        s2 = self._card(self._part_ff, "Parroquia de Destino", CSS["violet_50"])
        self._campo(s2, "PARROQUIA DE DESTINO", 28, 'parroquia_destino', store=self._part_entries)[0].pack(fill='x', pady=(4, 0))
        self._campo(s2, "DIÓCESIS DE DESTINO", 28, 'diocesis_destino', store=self._part_entries)[0].pack(fill='x', pady=(8, 0))

        s3 = self._card(self._part_ff, "Ministro y Emisión", CSS["slate_100"])
        row3 = tk.Frame(s3, bg="white"); row3.pack(fill='x', pady=(4, 0))
        self._campo(row3, "MINISTRO", 22, 'ministro', store=self._part_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row3, "FECHA DE EMISIÓN", 14, 'fecha_emision', store=self._part_entries)[0].pack(side='left', fill='x', expand=True)

        s4 = self._card(self._part_ff, "Notas", CSS["amber_50"])
        ef = tk.Frame(s4, bg=CSS["slate_200"]); ef.pack(fill='x', ipady=1)
        e_nota = tk.Entry(ef, font=("Segoe UI", 9), bg="white", fg=CSS["slate_800"], relief='flat')
        e_nota.pack(fill='x', padx=1, pady=1, ipady=4)
        self._part_entries['nota'] = e_nota

    def _get_part_data(self):
        data = {}
        for key, entry in self._part_entries.items():
            data[key] = entry.get().strip()
        data['tipo_sacramento'] = self._part_tipo_actual
        if self._part_tipo_actual != "Matrimonio":
            data['nombre_esposa'] = ''
        return data

    def _sel_tipo_part(self, tipo):
        self._part_tipo_actual = tipo
        for tp, (b, clr) in self._part_tipo_btns.items():
            if tp == tipo:
                b.config(bg=CSS["slate_100"], fg=clr)
            else:
                b.config(bg="white", fg=CSS["slate_500"])
        self._construir_formulario_part()
        self._part_limpiar()
        self._cargar_participaciones()

    def _part_guardar(self):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura", "aviso"); return
        data = self._get_part_data()
        if not data.get('nombre_esposo'):
            Notificacion(self.root, "El nombre es obligatorio", "aviso"); return
        if self._part_tipo_actual == "Matrimonio" and not data.get('nombre_esposa'):
            Notificacion(self.root, "El nombre de la esposa es obligatorio", "aviso"); return
        try:
            with db_cursor() as (c, con):
                c.execute("""INSERT INTO certificados_participacion
                    (tipo_sacramento, nombre_esposo, nombre_esposa, fecha_matrimonio,
                     parroquia_destino, diocesis_destino, ministro, fecha_emision, nota)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (data['tipo_sacramento'], data['nombre_esposo'], data.get('nombre_esposa',''),
                     data.get('fecha_matrimonio',''), data.get('parroquia_destino',''),
                     data.get('diocesis_destino',''), data.get('ministro',''),
                     data.get('fecha_emision',''), data.get('nota','')))
            Notificacion(self.root, "Participación registrada correctamente", "exito")
            self._part_limpiar()
            self._cargar_participaciones()
        except Exception as e:
            Notificacion(self.root, f"Error al guardar: {e}", "error")

    def _part_actualizar(self):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura", "aviso"); return
        if not self._part_selected_id:
            Notificacion(self.root, "Seleccione un registro", "aviso"); return
        data = self._get_part_data()
        if not data.get('nombre_esposo'):
            Notificacion(self.root, "El nombre es obligatorio", "aviso"); return
        try:
            with db_cursor() as (c, con):
                c.execute("""UPDATE certificados_participacion SET
                    tipo_sacramento=?, nombre_esposo=?, nombre_esposa=?, fecha_matrimonio=?,
                    parroquia_destino=?, diocesis_destino=?, ministro=?, fecha_emision=?, nota=?
                    WHERE id=?""",
                    (data['tipo_sacramento'], data['nombre_esposo'], data.get('nombre_esposa',''),
                     data.get('fecha_matrimonio',''), data.get('parroquia_destino',''),
                     data.get('diocesis_destino',''), data.get('ministro',''),
                     data.get('fecha_emision',''), data.get('nota',''), self._part_selected_id))
            Notificacion(self.root, "Registro actualizado", "exito")
            self._cargar_participaciones()
        except Exception as e:
            Notificacion(self.root, f"Error al actualizar: {e}", "error")

    def _part_eliminar(self):
        if not self._part_selected_id:
            Notificacion(self.root, "Seleccione un registro", "aviso"); return
        if not messagebox.askyesno("Confirmar", "¿Eliminar esta participación?"):
            return
        try:
            with db_cursor() as (c, con):
                c.execute("DELETE FROM certificados_participacion WHERE id=?", (self._part_selected_id,))
            Notificacion(self.root, "Registro eliminado", "exito")
            self._part_limpiar()
            self._cargar_participaciones()
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _part_limpiar(self):
        for entry in self._part_entries.values():
            entry.delete(0, tk.END)
        self._part_selected_id = None

    def _cargar_participaciones(self):
        for item in self._part_tree.get_children():
            self._part_tree.delete(item)
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT id, tipo_sacramento, nombre_esposo FROM certificados_participacion WHERE tipo_sacramento=? ORDER BY id DESC",
                          (self._part_tipo_actual,))
                rows = c.fetchall()
            for row in rows:
                self._part_tree.insert('', 'end', values=row)
            self._part_lbl_cnt.config(text=f"{len(rows)} registros")
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _on_sel_part(self, event):
        sel = self._part_tree.selection()
        if not sel:
            return
        item = self._part_tree.item(sel[0])
        rid = item['values'][0]
        self._part_selected_id = rid
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT * FROM certificados_participacion WHERE id=?", (rid,))
                cols = [d[0] for d in c.description]
                row = c.fetchone()
                if row:
                    data = dict(zip(cols, row))
                    self._part_limpiar()
                    self._part_selected_id = rid
                    for key, widget in self._part_entries.items():
                        val = str(data.get(key, '') or '')
                        if isinstance(widget, tuple) and len(widget) == 3:
                            partes = []
                            if '/' in val:
                                partes = val.split('/')
                            elif '-' in val:
                                p = val.split('-')
                                if len(p) == 3:
                                    partes = [p[2], p[1], p[0]]
                            if len(partes) == 3:
                                for i, parte in enumerate(partes):
                                    widget[i].delete(0, tk.END)
                                    widget[i].insert(0, parte)
                                    widget[i].config(fg=CSS["slate_800"])
                        elif isinstance(widget, tk.Text):
                            widget.delete("1.0", tk.END)
                            widget.insert("1.0", val)
                        else:
                            widget.delete(0, tk.END)
                            widget.insert(0, val)
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _part_imprimir(self):
        if not self._part_selected_id:
            Notificacion(self.root, "Seleccione un registro para imprimir", "aviso"); return
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT * FROM certificados_participacion WHERE id=?", (self._part_selected_id,))
                cols = [d[0] for d in c.description]
                data_row = c.fetchone()
                if not data_row:
                    Notificacion(self.root, "No se encontró el registro", "error"); return
                datos = dict(zip(cols, data_row))
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error"); return

        html_doc = self._generar_part_html(datos)

        f = tempfile.NamedTemporaryFile(mode='w', prefix='parroquia_part_', suffix='.html',
                                         delete=False, encoding='utf-8')
        f.write(html_doc)
        f.close()
        abrir_archivo(f.name)
        Notificacion(self.root, "Participación de matrimonio generada", "exito")
    
    def _generar_part_html(self, datos):
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
                 'septiembre','octubre','noviembre','diciembre']
        hoy = datetime.now()
        e = html.escape
        ministro = datos.get('ministro', '')
        tipo = datos.get('tipo_sacramento', 'Matrimonio')

        if tipo == "Matrimonio":
            nombre_bloque = f'''
                <div style="margin:20px 0;">
                    <div style="display:flex;margin-bottom:8px;">
                        <span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">ESPOSO:</span>
                        <span style="flex:1;border-bottom:1px solid black;text-transform:uppercase;font-size:13pt;font-weight:bold">{e(datos.get('nombre_esposo',''))}</span>
                    </div>
                    <div style="display:flex;margin-bottom:8px;">
                        <span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">ESPOSA:</span>
                        <span style="flex:1;border-bottom:1px solid black;text-transform:uppercase;font-size:13pt;font-weight:bold">{e(datos.get('nombre_esposa',''))}</span>
                    </div>
                </div>'''
        else:
            nombre_bloque = f'''
                <div style="text-align:center;margin:20px 0;border-bottom:1px solid black;padding-bottom:6px;">
                    <b style="font-size:14pt;text-transform:uppercase">{e(datos.get('nombre_esposo',''))}</b>
                </div>'''

        return f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Participación de {tipo}</title>
    <style>
        @page {{ size: letter; margin: 0.5in; }}
        html, body {{ height: 100%; margin: 0; padding: 0; font-family: Tahoma, sans-serif; font-size: 11pt; }}
        .wrapper {{ display: table; width: 100%; height: 10.2in; border-collapse: collapse; }}
        .content-row {{ display: table-row; height: 100%; }}
        .footer-row {{ display: table-row; height: 1px; }}
        .cell {{ display: table-cell; padding: 20px 42px; }}
        .footer-cell {{ display: table-cell; vertical-align: bottom; padding: 0 42px 10px 42px; }}
    </style>
    </head><body>
    <div class="wrapper">
        <div class="content-row">
            <div class="cell" style="vertical-align:top;">
                {self._html_encabezado()}
                <h2 style="text-align:center;font-family:Tahoma;border-top:2px solid black;border-bottom:2px solid black;padding:8px 0;margin:16px 0;">
                    PARTICIPACIÓN DE {e(tipo.upper())}
                </h2>

                <p style="text-align:justify;line-height:1.8;font-family:Tahoma;font-size:11pt;">
                    El Presbítero <b style="text-transform:uppercase">{e(ministro)}</b>,
                    Párroco de esta Parroquia, participa a la
                    <b>{e(datos.get('parroquia_destino',''))}</b>
                    de la <b>{e(datos.get('diocesis_destino',''))}</b>,
                    que en esta Parroquia se ha fijado la siguiente Proclama de {e(tipo)}:
                </p>

                {nombre_bloque}

                <div style="display:flex;margin-bottom:6px;">
                    <span style="min-width:200px;text-align:right;padding-right:8px;font-family:Tahoma">Fecha de {e(tipo)}:</span>
                    <span style="flex:1">{e(self._fecha_eclesiastica(datos.get('fecha_matrimonio','')))}</span>
                </div>

                <p style="margin-top:20px;text-align:justify;line-height:1.5;font-family:Tahoma">
                    Sin que hasta la fecha se haya presentado impedimento canónico alguno.
                </p>
                <p style="margin-top:16px;font-family:Tahoma">
                    Santa Bárbara de Zulia, a los {hoy.day} días del mes de {meses[hoy.month-1]} de {hoy.year}.
                </p>

                {self._html_firma(ministro)}
            </div>
        </div>
        <div class="footer-row">
            <div class="footer-cell">
                <div style="border-top:1px solid 999; padding-top:5px; font-family:Tahoma,sans-serif; font-size:8pt; line-height:1.2; text-align:center;">
                    <b>NOTA:</b> Si este certificado va a ser utilizado fuera de la Diocesis debe ser autenticado en la Cancilleria de la Curia Episcopal
                </div>
            </div>
        </div>
    </div>
    </body></html>'''
    
        bf = tk.Frame(left, bg=CSS["slate_50"], pady=6); bf.pack(fill='x')
        puede_editar = self.rol != 'pastor'
        if puede_editar:
            Boton(bf, texto="💾 Guardar", comando=self._inex_guardar, color=CSS["blue_600"]).pack(side='left', padx=(0, 3))
            Boton(bf, texto="🔄 Actualizar", comando=self._inex_actualizar, color=CSS["emerald_600"]).pack(side='left', padx=3)
            if self.rol == 'superusuario':
                Boton(bf, texto="🗑 Eliminar", comando=self._inex_eliminar, color=CSS["rose_600"]).pack(side='left', padx=3)
            Boton(bf, texto="✕ Limpiar", comando=self._inex_limpiar, color=CSS["slate_500"]).pack(side='left', padx=3)
        Boton(bf, texto="🖨 Imprimir", comando=self._inex_imprimir, color=CSS["slate_700"]).pack(side='right')

        right = tk.Frame(main, bg="white", width=380)
        right.pack(side='right', fill='y'); right.pack_propagate(False)

        rh = tk.Frame(right, bg="white", padx=14, pady=8); rh.pack(fill='x')
        tk.Label(rh, text="Inexistencias", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_800"]).pack(side='left')
        self._inex_lbl_cnt = tk.Label(rh, text="0 registros", font=("Segoe UI", 8),
                                      bg=CSS["slate_100"], fg=CSS["slate_500"], padx=6, pady=2)
        self._inex_lbl_cnt.pack(side='right')

        tk.Frame(right, bg=CSS["slate_100"], height=1).pack(fill='x')

        trf = tk.Frame(right, bg="white"); trf.pack(fill='both', expand=True, padx=4, pady=4)
        self._inex_tree = ttk.Treeview(trf, columns=("ID", "Tipo", "Nombre"), show='headings', style="A.Treeview")
        for col, w in [("ID", 40), ("Tipo", 100), ("Nombre", 200)]:
            self._inex_tree.column(col, width=w, anchor='center' if col == "ID" else 'w')
            self._inex_tree.heading(col, text=col)
        tsb = ttk.Scrollbar(trf, orient="vertical", command=self._inex_tree.yview)
        self._inex_tree.configure(yscrollcommand=tsb.set)
        self._inex_tree.pack(side='left', fill='both', expand=True); tsb.pack(side='right', fill='y')
        self._inex_tree.bind("<<TreeviewSelect>>", self._on_sel_inex)

    def _sel_tipo_inex(self, tipo):
        self._inex_tipo_actual = tipo
        for tp, (b, clr) in self._inex_tipo_btns.items():
            if tp == tipo:
                b.config(bg=CSS["slate_100"], fg=clr)
            else:
                b.config(bg="white", fg=CSS["slate_500"])
        self._construir_formulario_inex()
        self._inex_limpiar()
        self._cargar_inexistencias()
    
    def _construir_formulario_inex(self):
        for w in self._inex_ff.winfo_children():
            w.destroy()
        self._inex_entries = {}

        tipo = self._inex_tipo_actual

        s1 = self._card(self._inex_ff, f"Inexistencia de {tipo}", CSS["amber_50"])
        self._campo(s1, "NOMBRE COMPLETO *", 28, 'nombre', store=self._inex_entries)[0].pack(fill='x', pady=(4, 0))

        row2 = tk.Frame(s1, bg="white"); row2.pack(fill='x', pady=(8, 0))
        self._campo(row2, "FECHA DE NACIMIENTO", 14, 'fecha_nacimiento', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row2, "FECHA DE EMISIÓN", 14, 'fecha_emision', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True)

        s2 = self._card(self._inex_ff, "Datos de los Padres", CSS["emerald_50"])
        row3 = tk.Frame(s2, bg="white"); row3.pack(fill='x')
        self._campo(row3, "PADRE", 22, 'padre', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row3, "MADRE", 22, 'madre', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True)

        s3 = self._card(self._inex_ff, "Datos de la Búsqueda", CSS["violet_50"])
        row4 = tk.Frame(s3, bg="white"); row4.pack(fill='x', pady=(4, 0))
        self._campo(row4, "LIBROS BUSCADOS (Ej: X-XII)", 14, 'libros_buscados', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row4, "LUGAR DE BÚSQUEDA", 14, 'lugar_busqueda', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True)

        row5 = tk.Frame(s3, bg="white"); row5.pack(fill='x', pady=(8, 0))
        self._campo(row5, "AÑO DESDE", 10, 'anio_desde', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row5, "AÑO HASTA", 10, 'anio_hasta', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True)

        s4 = self._card(self._inex_ff, "1er. Testigo", CSS["blue_50"])
        row6 = tk.Frame(s4, bg="white"); row6.pack(fill='x', pady=(4, 0))
        self._campo(row6, "NOMBRE COMPLETO", 18, 'testigo1_nombre', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row6, "C.I.", 12, 'testigo1_ci', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row6, "PARENTESCO", 12, 'testigo1_parentesco', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True)

        s5 = self._card(self._inex_ff, "2do. Testigo", CSS["blue_50"])
        row7 = tk.Frame(s5, bg="white"); row7.pack(fill='x', pady=(4, 0))
        self._campo(row7, "NOMBRE COMPLETO", 18, 'testigo2_nombre', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row7, "C.I.", 12, 'testigo2_ci', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row7, "PARENTESCO", 12, 'testigo2_parentesco', store=self._inex_entries)[0].pack(side='left', fill='x', expand=True)

        s6 = self._card(self._inex_ff, "Resultado y Ministro", CSS["slate_100"])
        self._campo(s6, "RESULTADO", 28, 'resultado', store=self._inex_entries)[0].pack(fill='x', pady=(4, 0))
        self._campo(s6, "MINISTRO", 28, 'ministro', store=self._inex_entries)[0].pack(fill='x', pady=(8, 0))

        s7 = self._card(self._inex_ff, "Notas", CSS["rose_50"])
        ef = tk.Frame(s7, bg=CSS["slate_200"]); ef.pack(fill='x', ipady=1)
        e_nota = tk.Entry(ef, font=("Segoe UI", 9), bg="white", fg=CSS["slate_800"], relief='flat')
        e_nota.pack(fill='x', padx=1, pady=1, ipady=4)
        self._inex_entries['nota'] = e_nota

    def _construir_formulario_part(self):
        for w in self._part_ff.winfo_children():
            w.destroy()
        self._part_entries = {}

        tipo = self._part_tipo_actual

        s1 = self._card(self._part_ff, f"Participación de {tipo}", CSS["rose_50"])

        if tipo == "Matrimonio":
            row1 = tk.Frame(s1, bg="white"); row1.pack(fill='x', pady=(4, 0))
            self._campo(row1, "NOMBRE DEL ESPOSO *", 22, 'nombre_esposo', store=self._part_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row1, "NOMBRE DE LA ESPOSA *", 22, 'nombre_esposa', store=self._part_entries)[0].pack(side='left', fill='x', expand=True)
        else:
            self._campo(s1, "NOMBRE COMPLETO *", 28, 'nombre_esposo', store=self._part_entries)[0].pack(fill='x', pady=(4, 0))

        row2 = tk.Frame(s1, bg="white"); row2.pack(fill='x', pady=(8, 0))
        fecha_label = f"FECHA DE {tipo.upper()}" if tipo != "Matrimonio" else "FECHA DE MATRIMONIO"
        self._campo(row2, fecha_label, 14, 'fecha_matrimonio', store=self._part_entries)[0].pack(side='left', fill='x', expand=True)

        s2 = self._card(self._part_ff, "Parroquia de Destino", CSS["violet_50"])
        self._campo(s2, "PARROQUIA DE DESTINO", 28, 'parroquia_destino', store=self._part_entries)[0].pack(fill='x', pady=(4, 0))
        self._campo(s2, "DIÓCESIS DE DESTINO", 28, 'diocesis_destino', store=self._part_entries)[0].pack(fill='x', pady=(8, 0))

        s3 = self._card(self._part_ff, "Ministro y Emisión", CSS["slate_100"])
        row3 = tk.Frame(s3, bg="white"); row3.pack(fill='x', pady=(4, 0))
        self._campo(row3, "MINISTRO", 22, 'ministro', store=self._part_entries)[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
        self._campo(row3, "FECHA DE EMISIÓN", 14, 'fecha_emision', store=self._part_entries)[0].pack(side='left', fill='x', expand=True)

        s4 = self._card(self._part_ff, "Notas", CSS["amber_50"])
        ef = tk.Frame(s4, bg=CSS["slate_200"]); ef.pack(fill='x', ipady=1)
        e_nota = tk.Entry(ef, font=("Segoe UI", 9), bg="white", fg=CSS["slate_800"], relief='flat')
        e_nota.pack(fill='x', padx=1, pady=1, ipady=4)
        self._part_entries['nota'] = e_nota

    
    def _campo(self, parent, label, width, key, store=None):
        if store is None:
            store = self._form_entries

        f = tk.Frame(parent, bg=CSS["slate_50"])

        tk.Label(
            f,
            text=label,
            font=("Segoe UI", 8, "bold"),
            bg=CSS["slate_50"],
            fg=CSS["slate_600"]
        ).pack(anchor='w', pady=(0, 2))

        ef = tk.Frame(f, bg=CSS["slate_300"])
        ef.pack(fill='x')

        e = tk.Entry(
            ef,
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg=CSS["slate_800"],
            relief='flat',
            width=width,
            insertbackground=CSS["slate_800"]
        )
        e.pack(fill='x', padx=1, pady=1, ipady=6)

        store[key] = e
        return f, e
    def _normalizar_fecha_entry(self, widget, max_len):
        valor = widget.get()
        valor = ''.join(ch for ch in valor if ch.isdigit())[:max_len]
        widget.delete(0, tk.END)
        widget.insert(0, valor)

    def _fecha_autoavance(self, actual, siguiente, max_len):
        self._normalizar_fecha_entry(actual, max_len)
        if len(actual.get()) >= max_len and siguiente:
            siguiente.focus_set()

    def _campo_fecha(self, parent, label, key, store=None):
        if store is None:
            store = self._form_entries

        f = tk.Frame(parent, bg="white")
        tk.Label(
            f,
            text=label,
            font=("Segoe UI", 7, "bold"),
            bg="white",
            fg=CSS["slate_500"]
        ).pack(anchor='w')

        row = tk.Frame(f, bg="white")
        row.pack(fill='x')

        ef1 = tk.Frame(row, bg=CSS["slate_200"])
        ef1.pack(side='left', ipady=1, padx=(0, 2))
        e_dia = tk.Entry(
            ef1,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            width=4,
            justify='center'
        )
        e_dia.pack(padx=1, pady=1, ipady=4)

        tk.Label(row, text="/", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_500"]).pack(side='left')

        ef2 = tk.Frame(row, bg=CSS["slate_200"])
        ef2.pack(side='left', ipady=1, padx=(2, 2))
        e_mes = tk.Entry(
            ef2,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            width=4,
            justify='center'
        )
        e_mes.pack(padx=1, pady=1, ipady=4)

        tk.Label(row, text="/", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_500"]).pack(side='left')

        ef3 = tk.Frame(row, bg=CSS["slate_200"])
        ef3.pack(side='left', ipady=1, padx=(2, 0))
        e_ano = tk.Entry(
            ef3,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            width=4,
            justify='center'
        )
        e_ano.pack(padx=1, pady=1, ipady=4)

        e_dia.bind("<KeyRelease>", lambda ev: self._fecha_autoavance(e_dia, e_mes, 2))
        e_mes.bind("<KeyRelease>", lambda ev: self._fecha_autoavance(e_mes, e_ano, 2))
        e_ano.bind("<KeyRelease>", lambda ev: self._normalizar_fecha_entry(e_ano, 2))

        store[key] = (e_dia, e_mes, e_ano)
        return f

    def _fecha_eclesiastica(self, valor):
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
                 'septiembre','octubre','noviembre','diciembre']

        valor = str(valor or '').strip()
        if not valor:
            return ''

        if ' ' in valor:
            valor = valor.split()[0]

        if '-' in valor:
            try:
                a, m, d = valor.split('-')
                return f"{int(d)} de {meses[int(m)-1]} de {a}"
            except Exception:
                pass

        if '/' in valor:
            try:
                d, m, a = valor.split('/')
                if len(a) == 2:
                    a = '20' + a if int(a) < 50 else '19' + a
                return f"{int(d)} de {meses[int(m)-1]} de {a}"
            except Exception:
                pass

        return valor

    def _fecha_autoavance(self, actual, siguiente, max_len):
        self._normalizar_fecha_entry(actual, max_len)
        if len(actual.get()) >= max_len and siguiente:
            siguiente.focus_set()

    def _campo_fecha(self, parent, label, key, store=None):
        if store is None:
            store = self._form_entries

        f = tk.Frame(parent, bg="white")
        tk.Label(
            f,
            text=label,
            font=("Segoe UI", 7, "bold"),
            bg="white",
            fg=CSS["slate_500"]
        ).pack(anchor='w')

        row = tk.Frame(f, bg="white")
        row.pack(fill='x')

        ef1 = tk.Frame(row, bg=CSS["slate_200"])
        ef1.pack(side='left', ipady=1, padx=(0, 2))
        e_dia = tk.Entry(
            ef1,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            width=4,
            justify='center'
        )
        e_dia.pack(padx=1, pady=1, ipady=4)

        tk.Label(row, text="/", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_500"]).pack(side='left')

        ef2 = tk.Frame(row, bg=CSS["slate_200"])
        ef2.pack(side='left', ipady=1, padx=(2, 2))
        e_mes = tk.Entry(
            ef2,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            width=4,
            justify='center'
        )
        e_mes.pack(padx=1, pady=1, ipady=4)

        tk.Label(row, text="/", font=("Segoe UI", 10, "bold"), bg="white", fg=CSS["slate_500"]).pack(side='left')

        ef3 = tk.Frame(row, bg=CSS["slate_200"])
        ef3.pack(side='left', ipady=1, padx=(2, 0))
        e_ano = tk.Entry(
            ef3,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            width=4,
            justify='center'
        )
        e_ano.pack(padx=1, pady=1, ipady=4)

        e_dia.bind("<KeyRelease>", lambda ev: self._fecha_autoavance(e_dia, e_mes, 2))
        e_mes.bind("<KeyRelease>", lambda ev: self._fecha_autoavance(e_mes, e_ano, 2))
        e_ano.bind("<KeyRelease>", lambda ev: self._normalizar_fecha_entry(e_ano, 2))

        store[key] = (e_dia, e_mes, e_ano)
        return f

    def _fecha_eclesiastica(self, valor):
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
                 'septiembre','octubre','noviembre','diciembre']

        valor = str(valor or '').strip()
        if not valor:
            return ''

        if ' ' in valor:
            valor = valor.split()[0]

        if '-' in valor:
            try:
                a, m, d = valor.split('-')
                return f"{int(d)} de {meses[int(m)-1]} de {a}"
            except Exception:
                pass

        if '/' in valor:
            try:
                d, m, a = valor.split('/')
                if len(a) == 2:
                    a = '20' + a if int(a) < 50 else '19' + a
                return f"{int(d)} de {meses[int(m)-1]} de {a}"
            except Exception:
                pass

        return valor

    def _get_inex_data(self):
        data = {}
        for key, entry in self._inex_entries.items():
            data[key] = entry.get().strip()
        data['tipo_sacramento'] = self._inex_tipo_actual
        return data

    def _inex_guardar(self):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura", "aviso"); return
        data = self._get_inex_data()
        if not data.get('nombre'):
            Notificacion(self.root, "El nombre es obligatorio", "aviso"); return
        try:
            with db_cursor() as (c, con):
                c.execute("""INSERT INTO certificados_inexistencia
                    (tipo_sacramento, nombre, fecha_nacimiento, padre, madre,
                     lugar_busqueda, anio_desde, anio_hasta, resultado, ministro, fecha_emision, nota,
                     testigo1_nombre, testigo1_ci, testigo1_parentesco,
                     testigo2_nombre, testigo2_ci, testigo2_parentesco,
                     libros_buscados)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (data['tipo_sacramento'], data['nombre'], data.get('fecha_nacimiento',''),
                     data.get('padre',''), data.get('madre',''),
                     data.get('lugar_busqueda',''), data.get('anio_desde',''), data.get('anio_hasta',''),
                     data.get('resultado','No se encontró registro'), data.get('ministro',''),
                     data.get('fecha_emision',''), data.get('nota',''),
                     data.get('testigo1_nombre',''), data.get('testigo1_ci',''), data.get('testigo1_parentesco',''),
                     data.get('testigo2_nombre',''), data.get('testigo2_ci',''), data.get('testigo2_parentesco',''),
                     data.get('libros_buscados','')))
            Notificacion(self.root, "Inexistencia registrada correctamente", "exito")
            self._inex_limpiar()
            self._cargar_inexistencias()
        except Exception as e:
            Notificacion(self.root, f"Error al guardar: {e}", "error")

    def _inex_actualizar(self):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura", "aviso"); return
        if not self._inex_selected_id:
            Notificacion(self.root, "Seleccione un registro", "aviso"); return
        data = self._get_inex_data()
        if not data.get('nombre'):
            Notificacion(self.root, "El nombre es obligatorio", "aviso"); return
        try:
            with db_cursor() as (c, con):
                c.execute("""UPDATE certificados_inexistencia SET
                    tipo_sacramento=?, nombre=?, fecha_nacimiento=?, padre=?, madre=?,
                    lugar_busqueda=?, anio_desde=?, anio_hasta=?, resultado=?, ministro=?, fecha_emision=?, nota=?,
                    testigo1_nombre=?, testigo1_ci=?, testigo1_parentesco=?,
                    testigo2_nombre=?, testigo2_ci=?, testigo2_parentesco=?,
                    libros_buscados=?
                    WHERE id=?""",
                    (data['tipo_sacramento'], data['nombre'], data.get('fecha_nacimiento',''),
                     data.get('padre',''), data.get('madre',''),
                     data.get('lugar_busqueda',''), data.get('anio_desde',''), data.get('anio_hasta',''),
                     data.get('resultado',''), data.get('ministro',''),
                     data.get('fecha_emision',''), data.get('nota',''),
                     data.get('testigo1_nombre',''), data.get('testigo1_ci',''), data.get('testigo1_parentesco',''),
                     data.get('testigo2_nombre',''), data.get('testigo2_ci',''), data.get('testigo2_parentesco',''),
                     data.get('libros_buscados',''), self._inex_selected_id))
            Notificacion(self.root, "Registro actualizado", "exito")
            self._cargar_inexistencias()
        except Exception as e:
            Notificacion(self.root, f"Error al actualizar: {e}", "error")

    def _inex_eliminar(self):
        if not self._inex_selected_id:
            Notificacion(self.root, "Seleccione un registro", "aviso"); return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este registro de inexistencia?"):
            return
        try:
            with db_cursor() as (c, con):
                c.execute("DELETE FROM certificados_inexistencia WHERE id=?", (self._inex_selected_id,))
            Notificacion(self.root, "Registro eliminado", "exito")
            self._inex_limpiar()
            self._cargar_inexistencias()
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _inex_limpiar(self):
        for entry in self._inex_entries.values():
            entry.delete(0, tk.END)
        self._inex_selected_id = None

    def _cargar_inexistencias(self):
        for item in self._inex_tree.get_children():
            self._inex_tree.delete(item)
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT id, tipo_sacramento, nombre FROM certificados_inexistencia WHERE tipo_sacramento=? ORDER BY id DESC",
                          (self._inex_tipo_actual,))
                rows = c.fetchall()
            for row in rows:
                self._inex_tree.insert('', 'end', values=row)
            self._inex_lbl_cnt.config(text=f"{len(rows)} registros")
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _on_sel_inex(self, event):
        sel = self._inex_tree.selection()
        if not sel:
            return
        item = self._inex_tree.item(sel[0])
        rid = item['values'][0]
        self._inex_selected_id = rid
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT * FROM certificados_inexistencia WHERE id=?", (rid,))
                cols = [d[0] for d in c.description]
                row = c.fetchone()
                if row:
                    data = dict(zip(cols, row))
                    self._inex_limpiar()
                    self._inex_selected_id = rid
                    for key, widget in self._inex_entries.items():
                        val = str(data.get(key, '') or '')
                        if isinstance(widget, tuple) and len(widget) == 3:
                            partes = []
                            if '/' in val:
                                partes = val.split('/')
                            elif '-' in val:
                                p = val.split('-')
                                if len(p) == 3:
                                    partes = [p[2], p[1], p[0]]
                            if len(partes) == 3:
                                for i, parte in enumerate(partes):
                                    widget[i].delete(0, tk.END)
                                    widget[i].insert(0, parte)
                                    widget[i].config(fg=CSS["slate_800"])
                        elif isinstance(widget, tk.Text):
                            widget.delete("1.0", tk.END)
                            widget.insert("1.0", val)
                        else:
                            widget.delete(0, tk.END)
                            widget.insert(0, val)
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _inex_imprimir(self):
        if not self._inex_selected_id:
            Notificacion(self.root, "Seleccione un registro para imprimir", "aviso"); return
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT * FROM certificados_inexistencia WHERE id=?", (self._inex_selected_id,))
                cols = [d[0] for d in c.description]
                data_row = c.fetchone()
                if not data_row:
                    Notificacion(self.root, "No se encontró el registro", "error"); return
                datos = dict(zip(cols, data_row))
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error"); return

        fin = simpledialog.askstring("Fin del certificado",
            "¿Para qué fin se emite este certificado?",
            initialvalue="LO QUE CORRESPONDA", parent=self.root)
        if fin is None:
            return
        datos['fin_certificado'] = fin.strip() or "LO QUE CORRESPONDA"
        html_doc = self._generar_inex_html(datos)

        f = tempfile.NamedTemporaryFile(mode='w', prefix='parroquia_inex_', suffix='.html',
                                         delete=False, encoding='utf-8')
        f.write(html_doc)
        f.close()
        abrir_archivo(f.name)
        Notificacion(self.root, "Certificado de inexistencia generado", "exito")

    def _generar_inex_html(self, datos):
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
                 'septiembre','octubre','noviembre','diciembre']
        hoy = datetime.now()
        e = html.escape
        tipo = datos.get('tipo_sacramento', 'Bautismo')
        fin = e(datos.get('fin_certificado', 'LO QUE CORRESPONDA'))
        ministro = (datos.get('ministro', '') or '').strip().upper()
        nombre = e((datos.get('nombre', '') or '').strip().upper())

        fecha_bautizo = e(self._fecha_eclesiastica(datos.get('fecha_nacimiento', '')))
        libros = e(datos.get('libros_buscados', ''))
        anio_desde = e(datos.get('anio_desde', ''))
        anio_hasta = e(datos.get('anio_hasta', ''))

        padre = e((datos.get('padre', '') or '').strip().upper())
        madre = e((datos.get('madre', '') or '').strip().upper())

        t1_nombre = e((datos.get('testigo1_nombre', '') or '').strip().upper())
        t1_ci = e(datos.get('testigo1_ci', ''))
        t1_parentesco = e(datos.get('testigo1_parentesco', ''))
        t2_nombre = e((datos.get('testigo2_nombre', '') or '').strip().upper())
        t2_ci = e(datos.get('testigo2_ci', ''))
        t2_parentesco = e(datos.get('testigo2_parentesco', ''))

        return f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Inexistencia de {tipo}</title>
    <style>
        @page {{ size: letter; margin: 0.25in 0.3in 0.15in 0.3in; }}
        html, body {{ margin: 0; padding: 0; font-family: Tahoma, sans-serif; font-size: 11pt; color: #1a1a1a; }}
        body {{ padding: 8px 18px 55px 18px; box-sizing: border-box; }}
        .nota-pie {{
            position: fixed; left: 18px; right: 18px; bottom: 22px;
            border-top: 1px solid #999; padding-top: 4px; margin: 0;
            font-family: Tahoma, sans-serif; font-size: 8pt; line-height: 1.2;
            text-align: center; color: #555; background: white;
        }}
    </style>
    </head><body>

        {self._html_encabezado()}

        <table style="width:100%;border-collapse:collapse;margin:16px 0;" cellpadding="0" cellspacing="0">
            <tr>
                <td style="border-top:3px double black;border-bottom:3px double black;padding:8px 0;text-align:center;">
                    <div style="font-family:Impact,sans-serif;font-size:18pt;letter-spacing:1px;">
                        CONSTANCIA DE INEXISTENCIA DE CERTIFICADO DE {e(tipo.upper())}
                    </div>
                </td>
            </tr>
        </table>

        <p style="text-align:center;font-family:Tahoma;font-size:11pt;margin:12px 0 4px 0;">
            El Presbítero <b>{e(ministro)}</b>, Párroco de esta parroquia,
        </p>
        <p style="text-align:center;font-family:Tahoma;font-size:11pt;margin:0 0 8px 0;">
            hace constar que se buscó diligentemente
        </p>

        <div style="display:flex;justify-content:center;gap:8px;margin:8px 0;font-family:Tahoma;font-size:11pt;">
            <span>en los libros de {e(tipo.lower())} No.</span>
            <span style="border-bottom:1px solid black;min-width:80px;text-align:center;">{libros}</span>
            <span>correspondiente a los años</span>
            <span style="border-bottom:1px solid black;min-width:100px;text-align:center;">{anio_desde} - {anio_hasta}</span>
        </div>

        <p style="text-align:center;font-style:italic;font-family:Tahoma;font-size:11pt;margin:16px 0;">
            *** La Certificación de {e(tipo.lower())} solicitada no se encontró. ***
        </p>

        <div style="text-align:center;margin:16px 0;">
            <b style="font-size:14pt;font-family:Tahoma;">{nombre}</b>
        </div>

        <div style="margin:12px 0;font-family:Tahoma;font-size:11pt;line-height:1.8;">
            <div style="display:flex;margin-bottom:4px;">
                <b style="min-width:120px;text-align:right;padding-right:8px;">PADRES:</b>
                <span>{padre} y {madre}</span>
            </div>
            <div style="display:flex;margin-bottom:4px;">
                <b style="min-width:120px;text-align:right;padding-right:8px;">MINISTRO:</b>
                <span>PBRO. {e(ministro)}</span>
            </div>
        </div>

        <p style="font-family:Tahoma;font-size:11pt;margin:12px 0;">
            Según afirman bajo juramento, con las manos puestas en el Evangelio, {t1_parentesco} y {t2_parentesco}:
        </p>

        <div style="margin:16px 0;font-family:Tahoma;font-size:11pt;">
            <div style="display:flex;align-items:baseline;margin-bottom:16px;">
                <b style="min-width:90px;">1er. TEST.</b>
                <span style="min-width:200px;">{t1_nombre}</span>
                <span style="min-width:80px;text-align:right;padding-right:6px;">C.I.: V –</span>
                <span>{t1_ci}</span>
                <span style="flex:1;text-align:right;font-size:9pt;">________________</span>
            </div>
            <p style="text-align:right;font-size:9pt;margin:-8px 0 20px 0;">FIRMA</p>

            <div style="display:flex;align-items:baseline;margin-bottom:16px;">
                <b style="min-width:90px;">2do. TEST.</b>
                <span style="min-width:200px;">{t2_nombre}</span>
                <span style="min-width:80px;text-align:right;padding-right:6px;">C.I.: V –</span>
                <span>{t2_ci}</span>
                <span style="flex:1;text-align:right;font-size:9pt;">________________</span>
            </div>
            <p style="text-align:right;font-size:9pt;margin:-8px 0 12px 0;">FIRMA</p>
        </div>

        <p style="font-family:Tahoma;font-size:10pt;font-style:italic;margin:8px 0;">
            Los testigos presentan los siguientes documentos: Copia de Cédula del Bautizado,
            Fotografías, Copia de Cédula y su testimonio oral que ratifican bajo juramento.
        </p>

        <div style="display:flex;margin:8px 0;font-family:Tahoma;font-size:11pt;">
            <span>Se expide este certificado para fines:</span>
            <span style="flex:1;border-bottom:1px solid black;margin-left:8px;font-weight:bold;">{fin}</span>
        </div>

        <p style="font-family:Tahoma;font-size:11pt;margin:16px 0;">
            Santa Bárbara de Zulia, a los {hoy.day} días del mes de {meses[hoy.month-1]} de {hoy.year}.
        </p>

        {self._html_firma(datos.get('ministro',''))}

        <div class="nota-pie">
            <b>NOTA:</b> Si este certificado va a ser utilizado fuera de la Diocesis debe ser autenticado en la Cancilleria de la Curia Episcopal
        </div>

    </body></html>'''
    
    def __init__(self, root, uid, usuario, nombre, rol):
        self.root = root
        self.uid = uid
        self.usuario = usuario
        self.nombre = nombre
        self.rol = rol
        self.root.title(f"Gestor Parroquial v5.1 - {nombre}")
        self.root.configure(bg=CSS["slate_50"])
        self.modo_oscuro = False
        self._construir_ui()
        self._mostrar_pestana("dashboard")

    def _construir_ui(self):
        nav = tk.Frame(self.root, bg=CSS["slate_900"], height=62)
        nav.pack(fill='x')
        nav.pack_propagate(False)

        tk.Frame(self.root, bg="#D4A017", height=3).pack(fill='x')

        lf = tk.Frame(nav, bg=CSS["slate_900"])
        lf.pack(side='left', padx=(20, 0))

        ib = tk.Frame(lf, bg="#D4A017", width=38, height=38)
        ib.pack(side='left', padx=(0, 12))
        ib.pack_propagate(False)
        tk.Label(ib, text="✝", font=("Segoe UI", 16, "bold"), bg="#D4A017", fg=CSS["slate_900"]).place(relx=.5, rely=.5, anchor='center')

        tf = tk.Frame(lf, bg=CSS["slate_900"])
        tf.pack(side='left')
        tk.Label(tf, text="Gestor Parroquial", font=("Segoe UI", 12, "bold"), bg=CSS["slate_900"], fg="#F5F5F5").pack(anchor='w')
        tk.Label(tf, text="Administración Pastoral", font=("Segoe UI", 8), bg=CSS["slate_900"], fg=CSS["slate_400"]).pack(anchor='w')

        tk.Frame(nav, bg=CSS["slate_700"], width=1, height=32).pack(side='left', padx=16)

        tbf = tk.Frame(nav, bg=CSS["slate_900"])
        tbf.pack(side='left')

        self._botones_pestana = {}
        tabs = [
            ("dashboard",       "📊 Dashboard",       "#D4A017"),
            ("certificados",    "📜 Certificados",    "#D4A017"),
            ("inexistencias",   "📋 Inexistencias",   "#D4A017"),
            ("participaciones", "💒 Participaciones", "#D4A017"),
            ("inventario",      "📦 Inventario",      "#22C55E"),
        ]
        if self.rol == 'superusuario':
            tabs.append(("usuarios", "👥 Usuarios", "#D4A017"))
        tabs.append(("ajustes", "⚙ Ajustes", CSS["slate_400"]))

        for tid, label, clr in tabs:
            b = tk.Label(
                tbf, text=label,
                font=("Segoe UI", 9, "bold"),
                bg=CSS["slate_900"],
                fg=CSS["slate_400"],
                padx=12, pady=8,
                cursor="hand2"
            )
            b.pack(side='left', padx=2)

            def _enter(ev, lbl=b):
                if lbl.cget("fg") == CSS["slate_400"]:
                    lbl.config(bg=CSS["slate_800"])
            def _leave(ev, lbl=b):
                if lbl.cget("fg") == CSS["slate_400"]:
                    lbl.config(bg=CSS["slate_900"])

            b.bind("<Enter>", _enter)
            b.bind("<Leave>", _leave)
            b.bind("<Button-1>", lambda e, t=tid: self._mostrar_pestana(t))
            self._botones_pestana[tid] = (b, clr)

        rf = tk.Frame(nav, bg=CSS["slate_900"])
        rf.pack(side='right', padx=(0, 16))

        self.btn_modo = tk.Label(rf, text="🌙", font=("Segoe UI", 11),
                                 bg=CSS["slate_900"], fg=CSS["slate_400"], padx=8, pady=5, cursor="hand2")
        self.btn_modo.pack(side='right', padx=(8, 0))
        self.btn_modo.bind("<Button-1>", lambda e: self._toggle_modo())
        self.btn_modo.bind("<Enter>", lambda e: self.btn_modo.config(bg=CSS["slate_800"]))
        self.btn_modo.bind("<Leave>", lambda e: self.btn_modo.config(bg=CSS["slate_900"]))

        lo = tk.Label(rf, text="Salir", font=("Segoe UI", 9, "bold"),
                      bg=CSS["slate_900"], fg=CSS["rose_500"], padx=10, pady=5, cursor="hand2")
        lo.pack(side='right', padx=(8, 0))
        lo.bind("<Button-1>", lambda e: self._logout())
        lo.bind("<Enter>", lambda e: lo.config(bg=CSS["slate_800"]))
        lo.bind("<Leave>", lambda e: lo.config(bg=CSS["slate_900"]))

        uf = tk.Frame(rf, bg=CSS["slate_800"], padx=12, pady=5)
        uf.pack(side='right')
        ri = tk.Frame(uf, bg="#D4A017", width=26, height=26)
        ri.pack(side='left', padx=(0, 8))
        ri.pack_propagate(False)
        tk.Label(ri, text=self.nombre[0].upper(), font=("Segoe UI", 10, "bold"), bg="#D4A017", fg=CSS["slate_900"]).place(relx=.5, rely=.5, anchor='center')
        rl = {"superusuario": "Administrador", "secretaria": "Secretaria"}.get(self.rol, "Pastor")
        tk.Label(uf, text=rl, font=("Segoe UI", 9, "bold"), bg=CSS["slate_800"], fg="#F5F5F5").pack(side='left')

        self.contenedor = tk.Frame(self.root, bg=CSS["slate_50"])
        self.contenedor.pack(expand=True, fill='both', padx=0, pady=0)

        self.frames = {}
        for tid in ['dashboard', 'certificados', 'inexistencias', 'participaciones', 'inventario', 'usuarios', 'ajustes']:
            self.frames[tid] = tk.Frame(self.contenedor, bg=CSS["slate_50"])

        self._construir_dashboard()
        self._construir_certificados()
        self._construir_inexistencias()
        self._construir_participaciones()
        self._construir_inventario()
        if self.rol == 'superusuario':
            self._construir_usuarios()
        self._construir_ajustes()


    def _logout(self):
        if not messagebox.askyesno("Confirmar", "¿Desea cerrar sesion?"):
            return
        limpiar_temporales()
        for w in self.root.winfo_children():
            w.destroy()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(520, sw - 40), min(600, sh - 80)
        self.root.geometry(f'{w}x{h}+{(sw - w)//2}+{(sh - h)//2}')
        self.root.resizable(False, False)
        LoginApp(self.root)

    def _mostrar_pestana(self, tid):
        for f in self.frames.values():
            f.pack_forget()
        for t, (b, clr) in self._botones_pestana.items():
            b.config(bg=CSS["slate_900"], fg=CSS["slate_400"])
        self.frames[tid].pack(expand=True, fill='both')
        if tid in self._botones_pestana:
            b, clr = self._botones_pestana[tid]
            b.config(bg=CSS["slate_800"], fg=clr)
        if tid == 'dashboard':
            self._refrescar_dashboard()
        elif tid == 'certificados':
            self._cargar_certificados()
        elif tid == 'inventario':
            self._cargar_inventario()
        elif tid == 'usuarios':
            self._cargar_usuarios()
        elif tid == 'inexistencias':
            self._cargar_inexistencias()
        elif tid == 'participaciones':
            self._cargar_participaciones()

    def _construir_dashboard(self):
        f = self.frames['dashboard']
        self._dash_frame = tk.Frame(f, bg=CSS["slate_50"])
        self._dash_frame.pack(expand=True, fill='both')

    def _refrescar_dashboard(self):
        for w in self._dash_frame.winfo_children():
            w.destroy()

        hdr = tk.Frame(self._dash_frame, bg="#FFFBEB", padx=24, pady=18)
        hdr.pack(fill='x', pady=(0, 14))
        tk.Label(hdr, text=f"Paz y bien, {self.nombre}",
                 font=("Segoe UI", 16, "bold"), bg="#FFFBEB", fg=CSS["slate_800"]).pack(anchor='w')
        tk.Label(hdr, text="Bienvenido al sistema de administración pastoral.",
                 font=("Segoe UI", 10), bg="#FFFBEB", fg=CSS["slate_500"]).pack(anchor='w')

        with db_cursor() as (c, con):
            c.execute("SELECT COUNT(*) FROM certificados_bautismo")
            n_baut = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM certificados_comunion")
            n_com = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM certificados_confirmacion")
            n_conf = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM certificados_matrimonio")
            n_mat = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM certificados_defuncion")
            n_def = c.fetchone()[0]
            total_certs = n_baut + n_com + n_conf + n_mat + n_def
            c.execute("SELECT COUNT(*), COALESCE(SUM(cantidad),0) FROM inventario")
            n_reg, n_items = c.fetchone()
            c.execute("SELECT COUNT(DISTINCT categoria) FROM inventario")
            n_cat = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM inventario WHERE estado='Malo'")
            n_malo = c.fetchone()[0]

        sf = tk.Frame(self._dash_frame, bg=CSS["slate_50"])
        sf.pack(fill='x', pady=(0, 14))

        stats = [
            ("Certificados", str(total_certs), "#D4A017", "📜"),
            ("Inventario", str(entero_seguro(n_items)), "#16A34A", "📦"),
            ("Categorías", str(n_cat), "#B8860B", "📁"),
            ("Estado Malo", str(n_malo), "#E11D48", "⚠"),
        ]

        for title, val, clr, icon in stats:
            card_border = tk.Frame(sf, bg=CSS["slate_200"])
            card_border.pack(side='left', fill='x', expand=True, padx=5)

            card = tk.Frame(card_border, bg=CSS["slate_50"], padx=16, pady=14)
            card.pack(fill='x', padx=1, pady=1)

            top = tk.Frame(card, bg=CSS["slate_50"])
            top.pack(fill='x')

            ib = tk.Frame(top, bg=clr, width=40, height=40)
            ib.pack(side='left', padx=(0, 12))
            ib.pack_propagate(False)
            tk.Label(ib, text=icon, font=("Segoe UI", 15), bg=clr, fg="white").place(relx=.5, rely=.5, anchor='center')

            info = tk.Frame(top, bg=CSS["slate_50"])
            info.pack(side='left')
            tk.Label(info, text=val, font=("Segoe UI", 22, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')
            tk.Label(info, text=title, font=("Segoe UI", 9), bg=CSS["slate_50"], fg=CSS["slate_500"]).pack(anchor='w')

        chart_border = tk.Frame(self._dash_frame, bg=CSS["slate_200"])
        chart_border.pack(fill='x', pady=(0, 14))

        chart_frame = tk.Frame(chart_border, bg=CSS["slate_50"], padx=20, pady=16)
        chart_frame.pack(fill='x', padx=1, pady=1)

        tk.Label(chart_frame, text="Distribución de Certificados",
                 font=("Segoe UI", 11, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')

        canvas_h = 180
        canvas = tk.Canvas(chart_frame, bg=CSS["slate_50"], height=canvas_h, highlightthickness=0)
        canvas.pack(fill='x', pady=(10, 4))

        data = [
            ("Bautismo", n_baut, "#D4A017"),
            ("Comunión", n_com, "#B8860B"),
            ("Confirm.", n_conf, "#8B5CF6"),
            ("Matrimonio", n_mat, "#E11D48"),
            ("Defunción", n_def, "#737373"),
        ]
        max_val = max(v for _, v, _ in data) or 1
        bar_w = 65
        gap = 24
        start_x = 40

        for i, (label, val, clr) in enumerate(data):
            x = start_x + i * (bar_w + gap)
            bar_h = int((val / max_val) * (canvas_h - 50)) if max_val > 0 else 5
            y = canvas_h - 24 - bar_h
            canvas.create_rectangle(x, y, x + bar_w, canvas_h - 24, fill=clr, outline="")
            if val > 0:
                canvas.create_text(x + bar_w // 2, y - 10, text=str(val),
                                   font=("Segoe UI", 10, "bold"), fill=CSS["slate_700"])
            canvas.create_text(x + bar_w // 2, canvas_h - 8, text=label,
                               font=("Segoe UI", 8), fill=CSS["slate_500"])

        stat_border = tk.Frame(self._dash_frame, bg=CSS["slate_200"])
        stat_border.pack(fill='x', pady=(0, 14))

        stat2 = tk.Frame(stat_border, bg=CSS["slate_50"], padx=20, pady=16)
        stat2.pack(fill='x', padx=1, pady=1)

        tk.Label(stat2, text="Estado del Inventario",
                 font=("Segoe UI", 11, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')

        with db_cursor() as (c, con):
            c.execute("SELECT estado, COUNT(*) FROM inventario GROUP BY estado")
            est_data = dict(c.fetchall())

        est_row = tk.Frame(stat2, bg=CSS["slate_50"])
        est_row.pack(fill='x', pady=(10, 0))

        for est, clr in [("Nuevo", "#D4A017"), ("Bueno", "#16A34A"),
                          ("Regular", "#B8860B"), ("Malo", "#E11D48")]:
            f_est = tk.Frame(est_row, bg=CSS["slate_50"])
            f_est.pack(side='left', fill='x', expand=True, padx=6)
            tk.Label(f_est, text=str(est_data.get(est, 0)), font=("Segoe UI", 20, "bold"),
                     bg=CSS["slate_50"], fg=clr).pack()
            tk.Label(f_est, text=est, font=("Segoe UI", 9), bg=CSS["slate_50"], fg=CSS["slate_500"]).pack()

        with db_cursor() as (c, con):
            c.execute("SELECT codigo, descripcion, cantidad FROM inventario WHERE cantidad < 5 ORDER BY cantidad ASC")
            low_items = c.fetchall()

        if low_items:
            alert_border = tk.Frame(self._dash_frame, bg="#B8860B")
            alert_border.pack(fill='x', pady=(0, 0))

            alert = tk.Frame(alert_border, bg="#FFFBEB", padx=18, pady=12)
            alert.pack(fill='x', padx=1, pady=1)

            tk.Label(alert, text="⚠  Artículos con stock bajo",
                     font=("Segoe UI", 10, "bold"), bg="#FFFBEB", fg="#B8860B").pack(anchor='w')
            for cod, desc, cant in low_items:
                tk.Label(alert, text=f"   {cod}: {desc} ({cant} disp.)",
                         font=("Segoe UI", 9), bg="#FFFBEB", fg=CSS["slate_700"]).pack(anchor='w')

    def _construir_certificados(self):
        f = self.frames['certificados']
        self._cert_main = tk.Frame(f, bg=CSS["slate_50"])
        self._cert_main.pack(expand=True, fill='both')

        left = tk.Frame(self._cert_main, bg=CSS["slate_50"])
        left.pack(side='left', fill='both', expand=True, padx=(0, 10))

        pf = tk.Frame(left, bg=CSS["slate_50"])
        pf.pack(fill='x', pady=(0, 8))
        self.tipo_btns = {}
        for tp, clr in [("Bautismo", CSS["blue_500"]), ("Comunion", CSS["amber_500"]),
                         ("Confirmacion", CSS["violet_500"]), ("Matrimonio", CSS["rose_500"]),
                         ("Defuncion", CSS["slate_600"])]:
            b = tk.Label(pf, text=f"  {tp}", font=("Segoe UI", 9, "bold"),
                         bg=CSS["slate_50"], fg=CSS["slate_400"], padx=12, pady=7, cursor="hand2")
            b.pack(side='left', padx=3)

            def _enter(ev, lbl=b):
                if lbl.cget("fg") == CSS["slate_400"]:
                    lbl.config(bg=CSS["slate_100"])
            def _leave(ev, lbl=b):
                if lbl.cget("fg") == CSS["slate_400"]:
                    lbl.config(bg=CSS["slate_50"])

            b.bind("<Enter>", _enter)
            b.bind("<Leave>", _leave)
            b.bind("<Button-1>", lambda e, t=tp: self._sel_tipo_cert(t))
            self.tipo_btns[tp] = (b, clr)

        cf = tk.Frame(left, bg=CSS["slate_50"])
        cf.pack(fill='both', expand=True)
        self._cc = tk.Canvas(cf, bg=CSS["slate_50"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(cf, orient="vertical", command=self._cc.yview)
        self.ff = tk.Frame(self._cc, bg=CSS["slate_50"])
        self.ff.bind("<Configure>", lambda e: self._cc.configure(scrollregion=self._cc.bbox("all")))
        self._cc.create_window((0, 0), window=self.ff, anchor="nw")
        self._cc.configure(yscrollcommand=sb.set)
        self._cc.bind('<Configure>', lambda e: self._cc.itemconfig(1, width=e.width))
        self._cc.bind_all("<MouseWheel>", lambda e: self._cc.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        sb.pack(side="right", fill="y")
        self._cc.pack(side="left", fill="both", expand=True)

        self._form_entries = {}
        self._cert_tipo_actual = "Bautismo"
        self._cert_selected_id = None
        self._construir_formulario_certs()

        bf = tk.Frame(left, bg=CSS["slate_50"], pady=8)
        bf.pack(fill='x')
        puede_editar = self.rol != 'pastor'
        if puede_editar:
            Boton(bf, texto="💾 Guardar", comando=self._cert_guardar, color=CSS["blue_600"]).pack(side='left', padx=(0, 4))
            Boton(bf, texto="🔄 Actualizar", comando=self._cert_actualizar, color=CSS["emerald_600"]).pack(side='left', padx=4)
            if self.rol == 'superusuario':
                Boton(bf, texto="🗑 Eliminar", comando=self._cert_eliminar, color=CSS["rose_600"]).pack(side='left', padx=4)
            Boton(bf, texto="✕ Limpiar", comando=self._cert_limpiar, color=CSS["slate_500"]).pack(side='left', padx=4)
        else:
            tk.Label(bf, text="🔒 Modo solo lectura (Pastor)", font=("Segoe UI", 9),
                     bg=CSS["slate_50"], fg=CSS["slate_400"]).pack(side='left')
        Boton(bf, texto="🖨 Imprimir", comando=self._cert_imprimir, color=CSS["slate_700"]).pack(side='right')

        # ─── Panel derecho ───
        right = tk.Frame(self._cert_main, bg=CSS["slate_50"], width=400)
        right.pack(side='right', fill='y')
        right.pack_propagate(False)

        rh = tk.Frame(right, bg=CSS["slate_50"], padx=16, pady=12)
        rh.pack(fill='x')
        tk.Label(rh, text="Certificados", font=("Segoe UI", 11, "bold"),
                 bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(side='left')
        self.lbl_cnt = tk.Label(rh, text="0 registros", font=("Segoe UI", 8),
                                bg=CSS["slate_100"], fg=CSS["slate_500"], padx=8, pady=3)
        self.lbl_cnt.pack(side='right')

        sf = tk.Frame(right, bg=CSS["slate_50"], padx=16)
        sf.pack(fill='x', pady=(0, 8))
        search_border = tk.Frame(sf, bg=CSS["slate_300"])
        search_border.pack(fill='x')
        self.e_buscar = tk.Entry(search_border, font=("Segoe UI", 10),
                                 bg="#FFFFFF", fg=CSS["slate_800"], relief='flat')
        self.e_buscar.pack(fill='x', padx=1, pady=1, ipady=6)
        self.e_buscar.insert(0, "Buscar por nombre, libro, numero...")
        self.e_buscar.config(fg=CSS["slate_400"])
        self.e_buscar.bind("<FocusIn>", self._search_fi)
        self.e_buscar.bind("<FocusOut>", self._search_fo)
        self.e_buscar.bind("<KeyRelease>", lambda e: self._cargar_certificados())

        tk.Frame(right, bg=CSS["slate_200"], height=1).pack(fill='x')

        trf = tk.Frame(right, bg=CSS["slate_50"])
        trf.pack(fill='both', expand=True, padx=6, pady=6)

        st = ttk.Style()
        st.theme_use('clam')
        st.configure("A.Treeview",
                     background=CSS["slate_50"],
                     foreground=CSS["slate_800"],
                     fieldbackground=CSS["slate_50"],
                     rowheight=42,
                     font=("Segoe UI", 9),
                     borderwidth=0)
        st.configure("A.Treeview.Heading",
                     background=CSS["slate_100"],
                     foreground=CSS["slate_700"],
                     font=("Segoe UI", 8, "bold"),
                     borderwidth=0,
                     relief='flat')
        st.map("A.Treeview",
               background=[('selected', '#FFFBEB')],
               foreground=[('selected', '#B8860B')])

        self.tree_c = ttk.Treeview(trf, columns=("ID", "Nombre", "Fecha"),
                                   show='headings', style="A.Treeview")
        for col, w in [("ID", 45), ("Nombre", 200), ("Fecha", 95)]:
            self.tree_c.column(col, width=w, anchor='center' if col in ("ID", "Fecha") else 'w')
            self.tree_c.heading(col, text=col)
        tsb = ttk.Scrollbar(trf, orient="vertical", command=self.tree_c.yview)
        self.tree_c.configure(yscrollcommand=tsb.set)
        self.tree_c.pack(side='left', fill='both', expand=True)
        tsb.pack(side='right', fill='y')
        self.tree_c.bind("<<TreeviewSelect>>", self._on_sel_cert)

    def _search_fi(self, e):
        if self.e_buscar.get() == "Buscar por nombre, libro, numero...":
            self.e_buscar.delete(0, tk.END)
            self.e_buscar.config(fg=CSS["slate_800"])

    def _search_fo(self, e):
        if not self.e_buscar.get().strip():
            self.e_buscar.insert(0, "Buscar por nombre, libro, numero...")
            self.e_buscar.config(fg=CSS["slate_400"])

    def _get_search(self):
        v = self.e_buscar.get().strip()
        return "" if v == "Buscar por nombre, libro, numero..." else v
    
    def _tabla_cert(self):
        return {
            "Bautismo": "certificados_bautismo", "Comunion": "certificados_comunion",
            "Confirmacion": "certificados_confirmacion", "Matrimonio": "certificados_matrimonio",
            "Defuncion": "certificados_defuncion"
        }[self._cert_tipo_actual]

    def _sel_tipo_cert(self, tipo):
        self._cert_tipo_actual = tipo
        self._cert_selected_id = None
        self.tree_c.selection_remove(self.tree_c.selection())
        for t, (b, clr) in self.tipo_btns.items():
            b.config(bg="white", fg=clr if t == tipo else CSS["slate_500"])
        self._cert_limpiar(q=True)
        self._cargar_certificados()

    def _card(self, parent, titulo, color_hdr):
        outer = tk.Frame(parent, bg=CSS["slate_200"])
        outer.pack(fill='x', pady=(0, 12))

        f = tk.Frame(outer, bg=CSS["slate_50"])
        f.pack(fill='x', padx=1, pady=1)

        h = tk.Frame(f, bg=color_hdr, padx=18, pady=10)
        h.pack(fill='x')

        tk.Label(
            h,
            text=titulo,
            font=("Segoe UI", 10, "bold"),
            bg=color_hdr,
            fg=CSS["slate_800"]
        ).pack(side='left')

        body = tk.Frame(f, bg=CSS["slate_50"], padx=18, pady=14)
        body.pack(fill='x')

        return body
    
    def _construir_formulario_certs(self):
        for w in self.ff.winfo_children():
            w.destroy()
        self._form_entries = {}
        t = self._cert_tipo_actual

        if t == "Bautismo":
            s1 = self._card(self.ff, "Datos del Bautizado", CSS["blue_50"])
        elif t == "Comunion":
            s1 = self._card(self.ff, "Datos del Comulgante", CSS["amber_50"])
        elif t == "Confirmacion":
            s1 = self._card(self.ff, "Datos del Confirmado", CSS["violet_50"])
        elif t == "Matrimonio":
            s1 = self._card(self.ff, "Datos del Matrimonio", CSS["rose_50"])
        else:
            s1 = self._card(self.ff, "Datos del Fallecido", CSS["slate_100"])

        row1 = tk.Frame(s1, bg="white"); row1.pack(fill='x', pady=(4, 0))
        etiqueta_nombre = "ESPOSO *" if t == "Matrimonio" else "NOMBRE *"
        f1, e1 = self._campo(row1, etiqueta_nombre, 28, 'nombre')
        f1.pack(side='left', fill='x', expand=True, padx=(0, 6))

        if t == "Matrimonio":
            f1b, e1b = self._campo(row1, "ESPOSA *", 28, 'esposa')
            f1b.pack(side='left', fill='x', expand=True)

        f_min, e_min = self._campo(s1, "MINISTRO CELEBRANTE", 24, 'ministro')
        f_min.pack(fill='x', pady=(8, 0))

        row2 = tk.Frame(s1, bg="white"); row2.pack(fill='x', pady=(8, 0))
        if t == "Bautismo":
            self._campo(row2, "FECHA DE BAUTIZO *", 14, 'fecha_bautizo')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row2, "FECHA DE NACIMIENTO", 14, 'fecha_nacimiento')[0].pack(side='left', fill='x', expand=True)
        elif t == "Comunion":
            self._campo(row2, "FECHA DE COMUNION *", 14, 'fecha_comunion')[0].pack(side='left', fill='x', expand=True)
        elif t == "Confirmacion":
            self._campo(row2, "FECHA DE CONFIRMACION *", 14, 'fecha_confirmacion')[0].pack(side='left', fill='x', expand=True)
        elif t == "Matrimonio":
            self._campo(row2, "FECHA DE MATRIMONIO *", 14, 'fecha_matrimonio')[0].pack(side='left', fill='x', expand=True)
        elif t == "Defuncion":
            self._campo(row2, "FECHA DE DEFUNCION *", 14, 'fecha_defuncion')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row2, "FECHA DE ENTIERRO", 14, 'fecha_entierro')[0].pack(side='left', fill='x', expand=True)
            self._campo(s1, "CAUSA DE MUERTE", 28, 'causa_muerte')[0].pack(fill='x', pady=(8, 0))

        if t == "Matrimonio":
            s2 = self._card(self.ff, "Testigos Instrumentales", CSS["violet_50"])
            row = tk.Frame(s2, bg="white"); row.pack(fill='x')
            self._campo(row, "TESTIGO 1", 20, 'testigo1')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row, "TESTIGO 2", 20, 'testigo2')[0].pack(side='left', fill='x', expand=True)
        elif t == "Defuncion":
            s2 = self._card(self.ff, "Datos de Sepultura", CSS["violet_50"])
            row = tk.Frame(s2, bg="white"); row.pack(fill='x')
            self._campo(row, "LUGAR DE SEPULTURA", 20, 'lugar_sepultura')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row, "CEMENTERIO", 20, 'cementerio')[0].pack(side='left', fill='x', expand=True)
            s3 = self._card(self.ff, "Familiares", CSS["slate_100"])
            row2 = tk.Frame(s3, bg="white"); row2.pack(fill='x')
            self._campo(row2, "CONYUGE O FAMILIAR", 20, 'conyuge')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row2, "MADRE", 20, 'madre')[0].pack(side='left', fill='x', expand=True)
        else:
            s2 = self._card(self.ff, "Datos de los Padres", CSS["emerald_50"])
            row = tk.Frame(s2, bg="white"); row.pack(fill='x')
            self._campo(row, "PADRE", 22, 'padre')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            self._campo(row, "MADRE", 22, 'madre')[0].pack(side='left', fill='x', expand=True)

        if t not in ("Matrimonio", "Defuncion", "Comunion"):
            s3 = self._card(self.ff, "Datos de los Padrinos", CSS["violet_50"])
            row = tk.Frame(s3, bg="white"); row.pack(fill='x')
            self._campo(row, "PADRINO", 22, 'padrino')[0].pack(side='left', fill='x', expand=True, padx=(0, 6))
            if t != "Confirmacion":
                self._campo(row, "MADRINA", 22, 'madrina')[0].pack(side='left', fill='x', expand=True)

        s4 = self._card(self.ff, "Registro Eclesiastico *", CSS["amber_50"])
        row = tk.Frame(s4, bg="white"); row.pack(fill='x')
        for lbl, key in [("LIBRO *", "ecl_libro"), ("FOLIO *", "ecl_folio"), ("NUMERO *", "ecl_num"), ("ANO", "ecl_ano")]:
            self._campo(row, lbl, 8, key)[0].pack(side='left', fill='x', expand=True, padx=(0, 4))

        if t not in ("Comunion", "Confirmacion"):
            s5 = self._card(self.ff, "Registro Civil (Opcional)", CSS["slate_100"])
            row1 = tk.Frame(s5, bg="white"); row1.pack(fill='x', pady=(0, 4))
            self._campo(row1, "NUMERO", 10, "civil_num")[0].pack(side='left', fill='x', expand=True, padx=(0, 4))
            self._campo(row1, "LIBRO", 10, "civil_libro")[0].pack(side='left', fill='x', expand=True, padx=(0, 4))
            self._campo(row1, "TOMO", 10, "civil_tomo")[0].pack(side='left', fill='x', expand=True, padx=(0, 4))
            self._campo(row1, "FOLIO", 10, "civil_folio")[0].pack(side='left', fill='x', expand=True, padx=(0, 4))
            self._campo(row1, "ANO", 10, "civil_ano")[0].pack(side='left', fill='x', expand=True)

            row2 = tk.Frame(s5, bg="white"); row2.pack(fill='x', pady=(4, 0))
            self._campo(row2, "PARROQUIA", 18, "civil_parroquia")[0].pack(side='left', fill='x', expand=True, padx=(0, 4))
            self._campo(row2, "MUNICIPIO", 18, "civil_municipio")[0].pack(side='left', fill='x', expand=True, padx=(0, 4))
            self._campo(row2, "ESTADO", 18, "civil_estado")[0].pack(side='left', fill='x', expand=True)

        s6 = self._card(self.ff, "Notas Marginales", CSS["rose_50"])
        ef = tk.Frame(s6, bg=CSS["slate_200"]); ef.pack(fill='both', expand=True, ipady=1)
        e_nota = tk.Text(
            ef,
            font=("Segoe UI", 9),
            bg="white",
            fg=CSS["slate_800"],
            relief='flat',
            height=5,
            wrap='word'
        )
        e_nota.pack(fill='both', expand=True, padx=1, pady=1)
        self._form_entries['nota_marginal'] = e_nota

    def _get_form_data(self):
        data = {}
        for key, widget in self._form_entries.items():
            if isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", tk.END).strip()
            else:
                data[key] = widget.get().strip()
        return data

    def _limpiar_campos(self):
        for key, widget in self._form_entries.items():
            if isinstance(widget, tuple) and len(widget) == 3:
                for i, placeholder in enumerate(["DD", "MM", "AAAA"]):
                    widget[i].delete(0, tk.END)
                    widget[i].insert(0, placeholder)
                    widget[i].config(fg=CSS["slate_400"])
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
            else:
                widget.delete(0, tk.END)

    def _cert_limpiar(self, q=False):
        self._limpiar_campos()
        if not q:
            self.tree_c.selection_remove(self.tree_c.selection())
            self._cert_selected_id = None
        self._construir_formulario_certs()

    def _cargar_certificados(self):
        for r in self.tree_c.get_children():
            self.tree_c.delete(r)
        busq = self._get_search()
        tbl = self._tabla_cert()
        try:
            with db_cursor() as (c, con):
                if tbl == "certificados_bautismo":
                    col_n, col_f = "nombre", "fecha_bautizo"
                    where = "nombre LIKE ? OR ecl_libro LIKE ? OR ecl_num LIKE ?"
                elif tbl == "certificados_comunion":
                    col_n, col_f = "nombre", "fecha_comunion"
                    where = "nombre LIKE ? OR ecl_libro LIKE ? OR ecl_num LIKE ?"
                elif tbl == "certificados_confirmacion":
                    col_n, col_f = "nombre", "fecha_confirmacion"
                    where = "nombre LIKE ? OR ecl_libro LIKE ? OR ecl_num LIKE ?"
                elif tbl == "certificados_matrimonio":
                    col_n, col_f = "TRIM(esposo || ' y ' || esposa)", "fecha_matrimonio"
                    where = "esposo LIKE ? OR esposa LIKE ? OR ecl_libro LIKE ? OR ecl_num LIKE ?"
                else:
                    col_n, col_f = "nombre", "fecha_defuncion"
                    where = "nombre LIKE ? OR ecl_libro LIKE ? OR ecl_num LIKE ?"
                if busq:
                    params = [f"%{busq}%"] * (4 if tbl == "certificados_matrimonio" else 3)
                    c.execute(f"SELECT id, {col_n}, {col_f} FROM {tbl} WHERE {where}", params)
                else:
                    c.execute(f"SELECT id, {col_n}, {col_f} FROM {tbl}")
                rows = c.fetchall()
        except Exception as e:
            Notificacion(self.root, f"Error al cargar certificados: {e}", "error")
            return
        for r in rows:
            self.tree_c.insert("", tk.END, values=(r[0], r[1], r[2] or '-'))
        self.lbl_cnt.config(text=f"{len(rows)} certificado{'s' if len(rows) != 1 else ''}")

    def _on_sel_cert(self, e=None):
        sel = self.tree_c.selection()
        if not sel:
            return
        valores = self.tree_c.item(sel[0]).get('values', [])
        if not valores:
            return
        self._cert_selected_id = valores[0]
        tbl = self._tabla_cert()
        try:
            with db_cursor() as (c, con):
                c.execute(f"SELECT * FROM {tbl} WHERE id=?", (self._cert_selected_id,))
                cols = [d[0] for d in c.description]
                row = c.fetchone()
        except Exception:
            return

        if row:
            self._construir_formulario_certs()
            self._limpiar_campos()

            for col_name, val in zip(cols, row):
                if col_name == 'id':
                    continue

                # Mapear columna de BD a campo del formulario
                form_key = col_name
                if tbl == "certificados_matrimonio" and col_name == "esposo":
                    form_key = "nombre"

                if form_key in self._form_entries and val is not None:
                    widget = self._form_entries[form_key]
                    if isinstance(widget, tk.Text):
                        widget.delete("1.0", tk.END)
                        widget.insert("1.0", str(val))
                    else:
                        widget.delete(0, tk.END)
                        widget.insert(0, str(val))

    def _validar_cert(self):
        data = self._get_form_data()
        reglas = {
            "Bautismo": [
                ("nombre", "Nombre del bautizado"),
                ("fecha_bautizo", "Fecha de bautizo"),
                ("ecl_libro", "Libro eclesiastico"),
                ("ecl_folio", "Folio eclesiastico"),
                ("ecl_num", "Numero eclesiastico"),
            ],
            "Comunion": [
                ("nombre", "Nombre del comulgante"),
                ("fecha_comunion", "Fecha de comunion"),
                ("ecl_libro", "Libro eclesiastico"),
                ("ecl_folio", "Folio eclesiastico"),
                ("ecl_num", "Numero eclesiastico"),
            ],
            "Confirmacion": [
                ("nombre", "Nombre del confirmado"),
                ("fecha_confirmacion", "Fecha de confirmacion"),
                ("ecl_libro", "Libro eclesiastico"),
                ("ecl_folio", "Folio eclesiastico"),
                ("ecl_num", "Numero eclesiastico"),
            ],
            "Matrimonio": [
                ("nombre", "Nombre del esposo"),
                ("esposa", "Nombre de la esposa"),
                ("fecha_matrimonio", "Fecha de matrimonio"),
                ("ecl_libro", "Libro eclesiastico"),
                ("ecl_folio", "Folio eclesiastico"),
                ("ecl_num", "Numero eclesiastico"),
            ],
            "Defuncion": [
                ("nombre", "Nombre del fallecido"),
                ("fecha_defuncion", "Fecha de defuncion"),
                ("ecl_libro", "Libro eclesiastico"),
                ("ecl_folio", "Folio eclesiastico"),
                ("ecl_num", "Numero eclesiastico"),
            ],
        }
        for clave, etiqueta in reglas[self._cert_tipo_actual]:
            if not data.get(clave, '').strip():
                Notificacion(self.root, f"Falta campo obligatorio: {etiqueta}", "aviso")
                return False
        return True

    def _cert_guardar(self):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura: no puede crear certificados", "aviso")
            return
        if not self._validar_cert():
            return
        data = self._get_form_data()
        tbl = self._tabla_cert()
        try:
            with db_cursor() as (c, con):
                if tbl == "certificados_bautismo":
                    c.execute("INSERT INTO certificados_bautismo VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (data['nombre'], data.get('fecha_bautizo',''), data.get('fecha_nacimiento',''),
                         data.get('padre',''), data.get('madre',''), data.get('padrino',''), data.get('madrina',''),
                         data.get('ministro',''), data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('civil_num',''), data.get('civil_libro',''), data.get('civil_tomo',''), data.get('civil_folio',''), data.get('civil_ano',''),
                         data.get('civil_parroquia',''), data.get('civil_municipio',''), data.get('civil_estado',''),
                         data.get('nota_marginal','')))

                elif tbl == "certificados_comunion":
                    c.execute("INSERT INTO certificados_comunion VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (data['nombre'], data.get('fecha_comunion',''), data.get('padre',''), data.get('madre',''),
                         data.get('padrino',''), data.get('madrina',''), data.get('ministro',''),
                         data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('nota_marginal','')))

                elif tbl == "certificados_confirmacion":
                    c.execute("INSERT INTO certificados_confirmacion VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?)",
                        (data['nombre'], data.get('fecha_confirmacion',''), data.get('padre',''), data.get('madre',''),
                         data.get('padrino',''), data.get('ministro',''), data['ecl_libro'], data['ecl_folio'],
                         data['ecl_num'], data.get('ecl_ano',''), data.get('nota_marginal','')))

                elif tbl == "certificados_matrimonio":
                    c.execute("INSERT INTO certificados_matrimonio VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (data.get('nombre',''), data.get('esposa',''), data.get('fecha_matrimonio',''),
                         data.get('testigo1',''), data.get('testigo2',''), data.get('ministro',''),
                         data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('civil_num',''), data.get('civil_libro',''), data.get('civil_tomo',''), data.get('civil_folio',''), data.get('civil_ano',''),
                         data.get('civil_parroquia',''), data.get('civil_municipio',''), data.get('civil_estado',''),
                         data.get('nota_marginal','')))

                elif tbl == "certificados_defuncion":
                    c.execute("""INSERT INTO certificados_defuncion
                        (nombre, fecha_defuncion, fecha_entierro, conyuge, madre, lugar_sepultura,
                         cementerio, causa_muerte, ministro,
                         ecl_libro, ecl_folio, ecl_num, ecl_ano,
                         civil_num, civil_libro, civil_tomo, civil_folio, civil_ano,
                         civil_parroquia, civil_municipio, civil_estado,
                         nota_marginal)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (data['nombre'], data.get('fecha_defuncion',''), data.get('fecha_entierro',''),
                         data.get('conyuge',''), data.get('madre',''), data.get('lugar_sepultura',''),
                         data.get('cementerio',''), data.get('causa_muerte',''), data.get('ministro',''),
                         data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('civil_num',''), data.get('civil_libro',''), data.get('civil_tomo',''),
                         data.get('civil_folio',''), data.get('civil_ano',''),
                         data.get('civil_parroquia',''), data.get('civil_municipio',''),
                         data.get('civil_estado',''),
                         data.get('nota_marginal','')))

            Notificacion(self.root, "Certificado registrado correctamente", "exito")
            self._cert_limpiar()
            self._cargar_certificados()
        except Exception as e:
            Notificacion(self.root, f"Error al guardar: {e}", "error")

    def _cert_actualizar(self):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura", "aviso"); return
        if not self._cert_selected_id:
            Notificacion(self.root, "Seleccione un certificado", "aviso"); return
        if not self._validar_cert():
            return
        data = self._get_form_data()
        tbl = self._tabla_cert()
        cid = self._cert_selected_id
        try:
            with db_cursor() as (c, con):
                if tbl == "certificados_bautismo":
                    c.execute("UPDATE certificados_bautismo SET nombre=?,fecha_bautizo=?,fecha_nacimiento=?,padre=?,madre=?,padrino=?,madrina=?,ministro=?,ecl_libro=?,ecl_folio=?,ecl_num=?,ecl_ano=?,civil_num=?,civil_libro=?,civil_tomo=?,civil_folio=?,civil_ano=?,civil_parroquia=?,civil_municipio=?,civil_estado=?,nota_marginal=? WHERE id=?",
                        (data['nombre'], data.get('fecha_bautizo',''), data.get('fecha_nacimiento',''),
                         data.get('padre',''), data.get('madre',''), data.get('padrino',''), data.get('madrina',''),
                         data.get('ministro',''), data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('civil_num',''), data.get('civil_libro',''), data.get('civil_tomo',''), data.get('civil_folio',''), data.get('civil_ano',''),
                         data.get('civil_parroquia',''), data.get('civil_municipio',''), data.get('civil_estado',''),
                         data.get('nota_marginal',''), cid))

                elif tbl == "certificados_comunion":
                    c.execute("UPDATE certificados_comunion SET nombre=?,fecha_comunion=?,padre=?,madre=?,padrino=?,madrina=?,ministro=?,ecl_libro=?,ecl_folio=?,ecl_num=?,ecl_ano=?,nota_marginal=? WHERE id=?",
                        (data['nombre'], data.get('fecha_comunion',''), data.get('padre',''), data.get('madre',''),
                         data.get('padrino',''), data.get('madrina',''), data.get('ministro',''),
                         data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('nota_marginal',''), cid))

                elif tbl == "certificados_confirmacion":
                    c.execute("UPDATE certificados_confirmacion SET nombre=?,fecha_confirmacion=?,padre=?,madre=?,padrino=?,ministro=?,ecl_libro=?,ecl_folio=?,ecl_num=?,ecl_ano=?,nota_marginal=? WHERE id=?",
                        (data['nombre'], data.get('fecha_confirmacion',''), data.get('padre',''), data.get('madre',''),
                         data.get('padrino',''), data.get('ministro',''), data['ecl_libro'], data['ecl_folio'],
                         data['ecl_num'], data.get('ecl_ano',''), data.get('nota_marginal',''), cid))

                elif tbl == "certificados_matrimonio":
                    c.execute("UPDATE certificados_matrimonio SET esposo=?,esposa=?,fecha_matrimonio=?,testigo1=?,testigo2=?,ministro=?,ecl_libro=?,ecl_folio=?,ecl_num=?,ecl_ano=?,civil_num=?,civil_libro=?,civil_tomo=?,civil_folio=?,civil_ano=?,civil_parroquia=?,civil_municipio=?,civil_estado=?,nota_marginal=? WHERE id=?",
                        (data.get('nombre',''), data.get('esposa',''), data.get('fecha_matrimonio',''),
                         data.get('testigo1',''), data.get('testigo2',''), data.get('ministro',''),
                         data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('civil_num',''), data.get('civil_libro',''), data.get('civil_tomo',''), data.get('civil_folio',''), data.get('civil_ano',''),
                         data.get('civil_parroquia',''), data.get('civil_municipio',''), data.get('civil_estado',''),
                         data.get('nota_marginal',''), cid))

                elif tbl == "certificados_defuncion":
                    c.execute("""UPDATE certificados_defuncion SET
                        nombre=?, fecha_defuncion=?, fecha_entierro=?, conyuge=?, madre=?, lugar_sepultura=?,
                        cementerio=?, causa_muerte=?, ministro=?,
                        ecl_libro=?, ecl_folio=?, ecl_num=?, ecl_ano=?,
                        civil_num=?, civil_libro=?, civil_tomo=?, civil_folio=?, civil_ano=?,
                        civil_parroquia=?, civil_municipio=?, civil_estado=?,
                        nota_marginal=?
                        WHERE id=?""",
                        (data['nombre'], data.get('fecha_defuncion',''), data.get('fecha_entierro',''),
                         data.get('conyuge',''), data.get('madre',''), data.get('lugar_sepultura',''),
                         data.get('cementerio',''), data.get('causa_muerte',''), data.get('ministro',''),
                         data['ecl_libro'], data['ecl_folio'], data['ecl_num'], data.get('ecl_ano',''),
                         data.get('civil_num',''), data.get('civil_libro',''), data.get('civil_tomo',''),
                         data.get('civil_folio',''), data.get('civil_ano',''),
                         data.get('civil_parroquia',''), data.get('civil_municipio',''),
                         data.get('civil_estado',''),
                         data.get('nota_marginal',''), cid))

            Notificacion(self.root, "Certificado actualizado", "exito")
            self._cargar_certificados()
        except Exception as e:
            Notificacion(self.root, f"Error al actualizar: {e}", "error")

    def _cert_eliminar(self):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede eliminar certificados", "aviso")
            return
        if not self._cert_selected_id:
            Notificacion(self.root, "Seleccione un certificado", "aviso")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este certificado permanentemente?"):
            return
        tbl = self._tabla_cert()
        try:
            with db_cursor() as (c, con):
                c.execute(f"DELETE FROM {tbl} WHERE id=?", (self._cert_selected_id,))
            Notificacion(self.root, "Certificado eliminado", "exito")
            self._cert_selected_id = None
            self._limpiar_campos()
            self._cargar_certificados()
        except Exception as e:
            Notificacion(self.root, f"Error al eliminar: {e}", "error")

    def _valor_cert(self, valor, defecto="-"):
        if valor is None:
            return defecto
        valor = str(valor).strip()
        return valor if valor else defecto

    def _html_cert(self, valor, defecto="-"):
        return html.escape(self._valor_cert(valor, defecto))

    def _campo(self, parent, label, width, key, store=None):
        if store is None:
            store = self._form_entries

        f = tk.Frame(parent, bg=CSS["slate_50"])

        tk.Label(
            f,
            text=label,
            font=("Segoe UI", 8, "bold"),
            bg=CSS["slate_50"],
            fg=CSS["slate_600"]
        ).pack(anchor='w', pady=(0, 2))

        ef = tk.Frame(f, bg=CSS["slate_300"])
        ef.pack(fill='x')

        e = tk.Entry(
            ef,
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg=CSS["slate_800"],
            relief='flat',
            width=width,
            insertbackground=CSS["slate_800"]
        )
        e.pack(fill='x', padx=1, pady=1, ipady=6)

        store[key] = e
        return f, e
    
    def _seccion_cert_html(self, titulo, campos):
        contenido = "".join(self._campo_cert_html(etiqueta, valor) for etiqueta, valor in campos)
        return f"""
<div class="section">
  <div class="section-title">{html.escape(titulo)}</div>
  <div class="grid">{contenido}</div>
</div>"""

    def _registro_eclesiastico_html(self, row):
        campos = [
            ("Libro", row.get('ecl_libro')),
            ("Folio", row.get('ecl_folio')),
            ("Numero", row.get('ecl_num')),
            ("Ano", row.get('ecl_ano')),
        ]
        return self._seccion_cert_html("Registro Eclesiastico", campos)

    def _registro_civil_html(self, row):
        campos = [
        ("Numero", row.get('civil_num')),
        ("Libro", row.get('civil_libro')),
        ("Folio", row.get('civil_folio')),
        ("Tomo", row.get('civil_tomo')),
        ("Ano", row.get('civil_ano')),
        ("Parroquia", row.get('civil_parroquia')),
        ("Municipio", row.get('civil_municipio')),
        ("Estado", row.get('civil_estado')),
    ]
        return self._seccion_cert_html("Registro Civil", campos)
    def _nota_cert_html(self, row):
        nota = self._valor_cert(row.get('nota_marginal'), "")
        if not nota:
            return ""
        return f"""
<div class="nota">
  <div class="nota-label">Anotaciones Marginales</div>
  {html.escape(nota)}
</div>"""

    def _definicion_certificado(self, tipo, row):
        if tipo == "Bautismo":
            return {
                "tipo_label": "BAUTISMO",
                "declaracion": f"Certifica que {self._valor_cert(row.get('nombre'))} recibio el sacramento del Bautismo conforme consta en el archivo parroquial.",
                "civil": True,
                "secciones": [
                    ("Datos del Bautizado", [
                        ("Nombre completo", row.get('nombre')),
                        ("Fecha de bautizo", row.get('fecha_bautizo')),
                        ("Fecha de nacimiento", row.get('fecha_nacimiento')),
                        ("Ministro celebrante", row.get('ministro')),
                    ]),
                    ("Datos de los Padres", [
                        ("Padre", row.get('padre')),
                        ("Madre", row.get('madre')),
                    ]),
                    ("Datos de los Padrinos", [
                        ("Padrino", row.get('padrino')),
                        ("Madrina", row.get('madrina')),
                    ]),
                ],
            }
        if tipo == "Comunion":
            return {
                "tipo_label": "PRIMERA COMUNION",
                "declaracion": f"Certifica que {self._valor_cert(row.get('nombre'))} recibio la Primera Comunion conforme consta en el archivo parroquial.",
                "civil": False,
                "secciones": [
                    ("Datos del Comulgante", [
                        ("Nombre completo", row.get('nombre')),
                        ("Fecha de comunion", row.get('fecha_comunion')),
                        ("Ministro celebrante", row.get('ministro')),
                    ]),
                    ("Datos de los Padres", [
                        ("Padre", row.get('padre')),
                        ("Madre", row.get('madre')),
                    ]),
                    ("Datos de los Padrinos", [
                        ("Padrino", row.get('padrino')),
                        ("Madrina", row.get('madrina')),
                    ]),
                ],
            }
        if tipo == "Confirmacion":
            return {
                "tipo_label": "CONFIRMACION",
                "declaracion": f"Certifica que {self._valor_cert(row.get('nombre'))} recibio el sacramento de la Confirmacion conforme consta en el archivo parroquial.",
                "civil": False,
                "secciones": [
                    ("Datos del Confirmado", [
                        ("Nombre completo", row.get('nombre')),
                        ("Fecha de confirmacion", row.get('fecha_confirmacion')),
                        ("Ministro celebrante", row.get('ministro')),
                    ]),
                    ("Datos de los Padres", [
                        ("Padre", row.get('padre')),
                        ("Madre", row.get('madre')),
                    ]),
                    ("Padrino de Confirmacion", [
                        ("Padrino", row.get('padrino')),
                    ]),
                ],
            }
        if tipo == "Matrimonio":
            esposos = f"{self._valor_cert(row.get('esposo'))} y {self._valor_cert(row.get('esposa'))}"
            return {
                "tipo_label": "MATRIMONIO",
                "declaracion": f"Certifica que {esposos} contrajeron matrimonio canonico conforme consta en el archivo parroquial.",
                "civil": True,
                "secciones": [
                    ("Datos de los Contrayentes", [
                        ("Esposo", row.get('esposo')),
                        ("Esposa", row.get('esposa')),
                        ("Fecha de matrimonio", row.get('fecha_matrimonio')),
                        ("Ministro celebrante", row.get('ministro')),
                    ]),
                    ("Testigos Instrumentales", [
                        ("Testigo 1", row.get('testigo1')),
                        ("Testigo 2", row.get('testigo2')),
                    ]),
                ],
            }
        return {
            "tipo_label": "DEFUNCION",
            "declaracion": f"Certifica que {self._valor_cert(row.get('nombre'))} consta en el registro parroquial de defunciones.",
            "civil": False,
            "secciones": [
                ("Datos del Fallecido", [
                    ("Nombre completo", row.get('nombre')),
                    ("Fecha de defuncion", row.get('fecha_defuncion')),
                    ("Fecha de entierro", row.get('fecha_entierro')),
                    ("Causa de muerte", row.get('causa_muerte')),
                    ("Ministro", row.get('ministro')),
                ]),
                ("Familiares", [
                    ("Conyuge o familiar", row.get('conyuge')),
                    ("Madre", row.get('madre')),
                ]),
                ("Datos de Sepultura", [
                    ("Lugar de sepultura", row.get('lugar_sepultura')),
                    ("Cementerio", row.get('cementerio')),
                ]),
            ],
        }

    def _html_encabezado(self):
        import base64, os
        cfg = CONFIG_PARROQUIA
        base = os.path.dirname(os.path.abspath(__file__))

        def img_a_base64(nombre, ancho=105, alto=125):
            rutas = [
                os.path.join(base, nombre),
                os.path.join(base, "Encabezado_archivos", nombre),
            ]
            for ruta in rutas:
                if os.path.exists(ruta):
                    try:
                        ext = os.path.splitext(ruta)[1].lower()
                        mime = "image/png" if ext == ".png" else "image/jpeg"
                        with open(ruta, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                        return f'<img src="data:{mime};base64,{b64}" style="width:{ancho}px;height:{alto}px;object-fit:contain;">'
                    except Exception:
                        pass
            return ''

        img_izq = img_a_base64("image001.jpg", 120, 145)
        img_der = img_a_base64("image003.jpg", 105, 125)

        return f'''
        <div style="position:relative;width:100%;min-height:155px;margin-bottom:18px;">
            <div style="position:absolute;left:0;top:0;width:120px;text-align:left;">
                {img_izq}
            </div>

            <div style="position:absolute;right:0;top:0;width:105px;text-align:right;">
                {img_der}
            </div>

            <div style="margin-left:128px;">
                <div style="border-top:4px solid {cfg['color_lineas']}; border-bottom:4px solid {cfg['color_lineas']}; padding:10px 110px 10px 0; box-sizing:border-box;">
                    <div style="font-family:Tahoma,sans-serif;font-size:18pt;font-weight:bold;text-align:center;line-height:1.15;white-space:nowrap;letter-spacing:1px;">
                        {cfg['diocesis']}
                    </div>
                    <div style="font-family:Tahoma,sans-serif;font-size:15pt;text-align:center;line-height:1.15;white-space:nowrap;margin-top:4px;letter-spacing:0.5px;">
                        {cfg['parroquia']}
                    </div>
                </div>

                <div style="margin-top:14px;padding-right:110px;">
                    <div style="font-family:Tahoma,sans-serif;font-size:10pt;text-align:center;line-height:1.3;white-space:nowrap;">
                        {cfg['direccion']}
                    </div>
                    <div style="font-family:Tahoma,sans-serif;font-size:10pt;text-align:center;line-height:1.3;white-space:nowrap;">
                        {cfg['zona_postal']}
                    </div>
                    <div style="font-family:Tahoma,sans-serif;font-size:10pt;text-align:center;line-height:1.3;white-space:nowrap;">
                        {cfg['rif']}
                    </div>
                </div>
            </div>
        </div>
        '''
    def _html_titulo(self, tipo):
        titulos = {
            'Bautismo': 'CERTIFICADO DE BAUTISMO',
            'Comunion': 'CERTIFICADO DE PRIMERA COMUNIÓN',
            'Confirmacion': 'CERTIFICADO DE CONFIRMACIÓN',
            'Matrimonio': 'CERTIFICADO DE MATRIMONIO',
            'Defuncion': 'CERTIFICADO DE DEFUNCIÓN'
        }
        return f'''
        <div style="border-top:3px double black;border-bottom:3px double black;
             padding:8px 0;text-align:center;font-family:Impact,sans-serif;
             font-size:18pt;margin:15px 0">
            {titulos.get(tipo, 'CERTIFICADO')}
        </div>
        '''
    def _fecha_eclesiastica(self, valor):
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
                 'septiembre','octubre','noviembre','diciembre']

        valor = str(valor or '').strip()
        if not valor:
            return ''

        if ' ' in valor:
            valor = valor.split()[0]

        # Formato YYYY-MM-DD
        if '-' in valor:
            try:
                a, m, d = valor.split('-')
                return f"{int(d)} de {meses[int(m)-1]} de {a}"
            except Exception:
                pass

        # Formato DD/MM/AAAA o DD/MM/AA
        if '/' in valor:
            try:
                d, m, a = valor.split('/')
                a = str(a)
                if len(a) == 2:
                    a = '20' + a if int(a) < 50 else '19' + a
                return f"{int(d)} de {meses[int(m)-1]} de {a}"
            except Exception:
                pass

        return valor

    def _html_cuerpo_bautismo(self, d):
        e = html.escape
        return f'''
        <p style="text-align:justify;line-height:1.5;font-family:Tahoma,sans-serif">
            El Presbítero <b style="text-transform:uppercase">{e(d.get('ministro',''))}</b>,
            Párroco de esta Parroquia certifica que según consta en el Acta reseñada al margen,
            correspondiente al Libro de Bautismos, que reposa en los archivos de esta comunidad parroquial:
        </p>
        <div style="text-align:center;margin:16px 0;border-bottom:1px solid black;padding-bottom:4px">
            <b style="font-size:14pt;text-transform:uppercase">{e(d.get('nombre',''))}</b>
        </div>
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:160px;text-align:right;padding-right:8px;font-family:Tahoma">Fue bautizado(a) el día:</span>
            <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_bautizo','')))}</span>
        </div>
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:160px;text-align:right;padding-right:8px;font-family:Tahoma">Nació el día:</span>
            <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_nacimiento','')))}</span>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">PADRES:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('padre',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px"></span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('madre',''))}</span></div>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">PADRINOS:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('padrino',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px"></span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('madrina',''))}</span></div>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">MINISTRO:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">PBRO. {e(d.get('ministro',''))}</span></div>
        </div>
        '''
    def _html_cuerpo_comunion(self, d):
        e = html.escape
        return f'''
    <p style="text-align:justify;line-height:1.5;font-family:Tahoma,sans-serif">
        El Presbítero <b style="text-transform:uppercase">{e(d.get('ministro',''))}</b>,
        Párroco de esta Parroquia certifica que según consta en el Acta reseñada al margen,
        correspondiente al Libro de Primera Comunión:
    </p>
    <div style="text-align:center;margin:16px 0;border-bottom:1px solid black;padding-bottom:4px">
        <b style="font-size:14pt;text-transform:uppercase">{e(d.get('nombre',''))}</b>
    </div>
    <div style="display:flex;margin-bottom:6px">
        <span style="min-width:180px;text-align:right;padding-right:8px;font-family:Tahoma">Recibió la Primera Comunión:</span>
        <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_comunion','')))}</span>
    </div>
    <div style="margin-top:12px">
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">PADRES:</span>
            <span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('padre',''))}</span>
        </div>
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:100px"></span>
            <span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('madre',''))}</span>
        </div>
    </div>
    <div style="margin-top:12px">
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">MINISTRO:</span>
            <span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">PBRO. {e(d.get('ministro',''))}</span>
        </div>
    </div>
    '''
    def _html_cuerpo_confirmacion(self, d):
        e = html.escape
        return f'''
        <p style="text-align:justify;line-height:1.5;font-family:Tahoma,sans-serif">
            El Presbítero <b style="text-transform:uppercase">{e(d.get('ministro',''))}</b>,
            Párroco de esta Parroquia certifica que según consta en el Acta reseñada al margen,
            correspondiente al Libro de Confirmaciones:
        </p>
        <div style="text-align:center;margin:16px 0;border-bottom:1px solid black;padding-bottom:4px">
            <b style="font-size:14pt;text-transform:uppercase">{e(d.get('nombre',''))}</b>
        </div>
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:160px;text-align:right;padding-right:8px;font-family:Tahoma">Fue confirmado(a) el:</span>
            <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_confirmacion','')))}</span>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">PADRES:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('padre',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px"></span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('madre',''))}</span></div>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">PADRINO:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('padrino',''))}</span></div>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">MINISTRO:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">PBRO. {e(d.get('ministro',''))}</span></div>
        </div>
        '''

    def _html_cuerpo_matrimonio(self, d):
        e = html.escape
        return f'''
        <p style="text-align:justify;line-height:1.5;font-family:Tahoma,sans-serif">
            El Presbítero <b style="text-transform:uppercase">{e(d.get('ministro',''))}</b>,
            Párroco de esta Parroquia certifica que según consta en el Acta reseñada al margen,
            correspondiente al Libro de Matrimonios:
        </p>
        <div style="margin-top:16px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">ESPOSO:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('esposo',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">ESPOSA:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('esposa',''))}</span></div>
        </div>
        <div style="display:flex;margin:12px 0 6px">
            <span style="min-width:200px;text-align:right;padding-right:8px;font-family:Tahoma">Contrajeron Matrimonio el:</span>
            <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_matrimonio','')))}</span>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">TESTIGO 1:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('testigo1',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">TESTIGO 2:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('testigo2',''))}</span></div>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:100px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">MINISTRO:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">PBRO. {e(d.get('ministro',''))}</span></div>
        </div>
        '''

    def _html_cuerpo_defuncion(self, d):
        e = html.escape
        return f'''
        <p style="text-align:justify;line-height:1.5;font-family:Tahoma,sans-serif">
            El Presbítero <b style="text-transform:uppercase">{e(d.get('ministro',''))}</b>,
            Párroco de esta Parroquia certifica que según consta en el Acta reseñada al margen,
            correspondiente al Libro de Defunciones:
        </p>
        <div style="text-align:center;margin:16px 0;border-bottom:1px solid black;padding-bottom:4px">
            <b style="font-size:14pt;text-transform:uppercase">{e(d.get('nombre',''))}</b>
        </div>
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:160px;text-align:right;padding-right:8px;font-family:Tahoma">Falleció el:</span>
            <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_defuncion','')))}</span>
        </div>
        <div style="display:flex;margin-bottom:6px">
            <span style="min-width:160px;text-align:right;padding-right:8px;font-family:Tahoma">Fue sepultado(a) el:</span>
            <span style="flex:1">{e(self._fecha_eclesiastica(d.get('fecha_entierro','')))}</span>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:120px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">CÓNYUGE:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('conyuge',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:120px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">MADRE:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">{e(d.get('madre',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:120px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">CEMENTERIO:</span><span style="flex:1;border-bottom:1px solid black">{e(d.get('cementerio',''))}</span></div>
            <div style="display:flex;margin-bottom:6px"><span style="min-width:120px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">LUGAR:</span><span style="flex:1;border-bottom:1px solid black">{e(d.get('lugar_sepultura',''))}</span></div>
        </div>
        <div style="margin-top:12px">
            <div style="display:flex;margin-bottom:6px"><span style="min-width:120px;text-align:right;padding-right:8px;font-weight:bold;font-family:Tahoma">MINISTRO:</span><span style="flex:1;border-bottom:1px solid black;text-transform:uppercase">PBRO. {e(d.get('ministro',''))}</span></div>
        </div>
        '''
    def _html_registros(self, d, mostrar_civil=True):
        e = html.escape
        s = lambda k: e(str(d.get(k, '') or ''))

        reg = f'''<table style="border:1px solid black;border-collapse:collapse;width:100%;margin-bottom:12px;font-size:10pt;font-family:Tahoma">
            <tr><th colspan="2" style="border:1px solid black;padding:3px 6px;text-decoration:underline">REG. ECLESIÁSTICO</th></tr>
            <tr><td style="border:1px solid black;padding:3px 6px"><b>LIBRO</b></td><td style="border:1px solid black;padding:3px 6px"><b>{s('ecl_libro')}</b></td></tr>
            <tr><td style="border:1px solid black;padding:3px 6px"><b>FOLIO</b></td><td style="border:1px solid black;padding:3px 6px"><b>{s('ecl_folio')}</b></td></tr>
            <tr><td style="border:1px solid black;padding:3px 6px"><b>NUM.</b></td><td style="border:1px solid black;padding:3px 6px"><b>{s('ecl_num')}</b></td></tr>
            <tr><td style="border:1px solid black;padding:3px 6px"><b>AÑO</b></td><td style="border:1px solid black;padding:3px 6px"><b>{s('ecl_ano')}</b></td></tr>
        </table>'''

        civil = ""
        if mostrar_civil and (d.get('civil_num') or d.get('civil_libro') or d.get('civil_tomo') or d.get('civil_folio')):
            civil = f'''<table style="border:1px solid black;border-collapse:collapse;width:100%;margin-bottom:12px;font-size:10pt;font-family:Tahoma">
                <tr><th style="border:1px solid black;padding:3px 6px;text-decoration:underline">REGISTRO CIVIL</th></tr>
                <tr><td style="border:1px solid black;padding:3px 6px">
                    Nº {s('civil_num')}<br>
                    LIBRO: {s('civil_libro')}<br>
                    TOMO: {s('civil_tomo')}<br>
                    FOLIO: {s('civil_folio')}
                </td></tr>
                <tr><td style="border:1px solid black;padding:3px 6px;text-align:center">AÑO. {s('civil_ano')}</td></tr>
                <tr><td style="border:1px solid black;padding:3px 6px;text-align:center">PARROQUIA<br>{s('civil_parroquia')}</td></tr>
                <tr><td style="border:1px solid black;padding:3px 6px;text-align:center">MUNICIPIO<br>{s('civil_municipio')}</td></tr>
                <tr><td style="border:1px solid black;padding:3px 6px;text-align:center">ESTADO<br>{s('civil_estado')}</td></tr>
            </table>'''

        nota = ""
        if d.get('nota_marginal'):
            nota = f'''<table style="border:1px solid black;border-collapse:collapse;width:100%;font-size:10pt;font-family:Tahoma;table-layout:fixed;">
                <tr><th style="border:1px solid black;padding:3px 6px;text-decoration:underline">NOTA MARGINAL</th></tr>
                <tr>
                    <td style="border:1px solid black;padding:6px;font-size:8pt;line-height:1.35;vertical-align:top;text-align:justify;white-space:normal;word-wrap:break-word;word-break:break-word;min-height:120px;">
                        {s('nota_marginal')}
                    </td>
                </tr>
            </table>'''

        return reg + civil + nota
    
    def _html_firma(self, ministro):
        ministro = html.escape((ministro or "").strip().upper())
        nombre_firma = f"PBRO. {ministro}" if ministro else "PBRO."

        return f'''
        <div style="position:relative;margin-top:28px;height:140px;font-family:Tahoma,sans-serif;">
            
            <div style="position:absolute;left:38px;top:18px;font-size:11pt;font-weight:bold;">
                DOY FE
            </div>

            <div style="position:absolute;left:50%;transform:translateX(-50%);top:58px;width:280px;text-align:center;">
                <div style="border-top:1.5px solid black;width:100%;margin:0 auto 6px auto;"></div>
                <div style="font-size:11pt;font-weight:bold;">{nombre_firma}</div>
                <div style="font-size:10pt;">Párroco</div>
            </div>

            <div style="position:absolute;right:18px;top:82px;font-size:11pt;font-weight:bold;">
                SELLO
            </div>
        </div>
        '''
    def _generar_certificado_html(self, tipo, datos):
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
                'septiembre','octubre','noviembre','diciembre']
        hoy = datetime.now()
        cuerpos = {
            'Bautismo':     self._html_cuerpo_bautismo,
            'Comunion':     self._html_cuerpo_comunion,
            'Confirmacion': self._html_cuerpo_confirmacion,
            'Matrimonio':   self._html_cuerpo_matrimonio,
            'Defuncion':    self._html_cuerpo_defuncion,
        }
        mostrar_civil = tipo in ['Bautismo', 'Matrimonio', 'Defuncion']
        func_cuerpo = cuerpos.get(tipo, self._html_cuerpo_bautismo)
        fin = html.escape(datos.get('fin_certificado', 'los fines legales consiguientes'))
        ministro = datos.get('ministro', '')

        return f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Certificado de {tipo}</title>
    <style>
        @page {{
            size: letter;
            margin: 0.25in 0.3in 0.15in 0.3in;
        }}

        html, body {{
            margin: 0;
            padding: 0;
            font-family: Tahoma, sans-serif;
            font-size: 12pt;
            color: #1a1a1a;
        }}

        body {{
            padding: 8px 18px 55px 18px;
            box-sizing: border-box;
        }}

        .grid-principal {{
            display: grid;
            grid-template-columns: 1fr 185px;
            gap: 0;
        }}

        .col-izquierda {{
            border-right: 3px double black;
            padding-right: 14px;
        }}

        .col-derecha {{
            padding-left: 14px;
        }}

        .expedicion {{
            margin-top: 24px;
            text-align: justify;
            line-height: 2.0;
            font-family: Tahoma, sans-serif;
            font-size: 12pt;
        }}

        .fecha-emision {{
            margin-top: 20px;
            font-family: Tahoma, sans-serif;
            font-size: 12pt;
        }}

        .nota-pie {{
            position: fixed;
            left: 18px;
            right: 18px;
            bottom: 2px;
            border-top: 1px solid #999;
            padding-top: 4px;
            margin: 0;
            font-family: Tahoma, sans-serif;
            font-size: 8pt;
            line-height: 1.2;
            text-align: center;
            color: #555;
            background: white;
        }}
    </style>
    </head><body>

        {self._html_encabezado()}
        {self._html_titulo(tipo)}

        <div class="grid-principal">
            <div class="col-izquierda">
                {func_cuerpo(datos)}
                <p class="expedicion">
                    Se expide el presente certificado, a solicitud de parte interesada,
                    para fines única y exclusivamente: <b>{fin}</b>
                </p>
                <p class="fecha-emision">
                    Santa Bárbara de Zulia, a los {hoy.day} días del mes de {meses[hoy.month-1]} de {hoy.year}.
                </p>
            </div>
            <div class="col-derecha">
                {self._html_registros(datos, mostrar_civil)}
            </div>
        </div>

        {self._html_firma(ministro)}

        <div class="nota-pie">
            <b>NOTA:</b> Si este certificado va a ser utilizado fuera de la Diocesis debe ser autenticado en la Cancilleria de la Curia Episcopal
        </div>

    </body></html>'''
    
    
    def _cert_imprimir(self):
        if not self._cert_selected_id:
            Notificacion(self.root, "Seleccione un certificado para imprimir", "aviso")
            return
        
        tbl = self._tabla_cert()
        tipo = self._cert_tipo_actual
        
        try:
            with db_cursor() as (c, con):
                c.execute(f"SELECT * FROM {tbl} WHERE id=?", (self._cert_selected_id,))
                cols = [d[0] for d in c.description]
                data_row = c.fetchone()
                if not data_row:
                    Notificacion(self.root, "No se encontró el certificado", "error")
                    return
                datos = dict(zip(cols, data_row))
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")
            return
        
        fin = simpledialog.askstring(
            "Fin del certificado",
            "¿Para qué fin se emite este certificado?",
            initialvalue="LO QUE CORRESPONDA",
            parent=self.root
        )
        if fin is None:
            return
        datos['fin_certificado'] = fin.strip() or "LO QUE CORRESPONDA"

        html_doc = self._generar_certificado_html(tipo, datos)

        f = tempfile.NamedTemporaryFile(
            mode='w', prefix='parroquia_cert_', suffix='.html',
            delete=False, encoding='utf-8'
        )
        f.write(html_doc)
        f.close()
        abrir_archivo(f.name)
        Notificacion(self.root, f"Certificado de {tipo} generado", "exito")
    
    def _construir_inventario(self):
        f = self.frames['inventario']
        main = tk.Frame(f, bg=CSS["slate_50"]); main.pack(expand=True, fill='both')

        sf = tk.Frame(main, bg=CSS["slate_50"]); sf.pack(fill='x', pady=(0, 8))
        self._inv_stats = {}
        for key, title, clr, icon in [("reg", "Registros", CSS["blue_600"], ""),
                                       ("items", "Total Items", CSS["emerald_600"], "="),
                                       ("cats", "Categorias", CSS["amber_600"], "T"),
                                       ("est", "Por Estado", CSS["violet_600"], "%")]:
            card = tk.Frame(sf, bg="white", padx=12, pady=8)
            card.pack(side='left', fill='x', expand=True, padx=2)
            r = tk.Frame(card, bg="white"); r.pack(fill='x')
            ib = tk.Frame(r, bg=clr, width=34, height=34); ib.pack(side='left', padx=(0, 8)); ib.pack_propagate(False)
            tk.Label(ib, text=icon, font=("Segoe UI", 13, "bold"), bg=clr, fg="white").place(relx=.5, rely=.5, anchor='center')
            tf = tk.Frame(r, bg="white"); tf.pack(side='left')
            vl = tk.Label(tf, text="0", font=("Segoe UI", 16, "bold"), bg="white", fg=CSS["slate_900"])
            vl.pack(anchor='w')
            tk.Label(tf, text=title, font=("Segoe UI", 8), bg="white", fg=CSS["slate_500"]).pack(anchor='w')
            self._inv_stats[key] = vl

        tb = tk.Frame(main, bg=CSS["slate_50"]); tb.pack(fill='x', pady=(0, 8))
        sbx = tk.Frame(tb, bg="white", padx=10, pady=5)
        sbx.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.e_ib = tk.Entry(sbx, font=("Segoe UI", 9), bg="white", fg=CSS["slate_800"], relief='flat')
        self.e_ib.pack(side='left', fill='x', expand=True)
        self.e_ib.insert(0, "Buscar por codigo, descripcion...")
        self.e_ib.config(fg=CSS["slate_400"])
        self.e_ib.bind("<FocusIn>", lambda e: (self.e_ib.delete(0, tk.END), self.e_ib.config(fg=CSS["slate_800"])) if self.e_ib.get() == "Buscar por codigo, descripcion..." else None)
        self.e_ib.bind("<FocusOut>", lambda e: (self.e_ib.insert(0, "Buscar por codigo, descripcion..."), self.e_ib.config(fg=CSS["slate_400"])) if not self.e_ib.get().strip() else None)
        self.e_ib.bind("<KeyRelease>", lambda e: self._cargar_inventario())

        cfx = tk.Frame(tb, bg="white", padx=8, pady=5); cfx.pack(side='left', padx=(0, 4))
        self.cmb = ttk.Combobox(cfx, values=CATEGORIAS_INV, state="readonly", width=11, font=("Segoe UI", 9))
        self.cmb.current(0); self.cmb.pack()
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._cargar_inventario())

        bbx = tk.Frame(tb, bg=CSS["slate_50"]); bbx.pack(side='right')
        Boton(bbx, texto="🖨 Imprimir", comando=self._imprimir_inventario, color=CSS["slate_600"]).pack(side='left', padx=(0, 3))
        if self.rol != 'pastor':
            Boton(bbx, texto="+ Agregar", comando=self._inv_modal, color=CSS["emerald_600"]).pack(side='left')

        tc = tk.Frame(main, bg="white"); tc.pack(fill='both', expand=True)
        hdr = tk.Frame(tc, bg=CSS["slate_50"], padx=12, pady=6); hdr.pack(fill='x')
        for txt, w in [("Codigo", 10), ("Descripcion", 28), ("Und.", 7), ("Ubicacion", 13),
                        ("Cant.", 5), ("Categoria", 10), ("Estado", 9)]:
            tk.Label(hdr, text=txt, font=("Segoe UI", 8, "bold"), bg=CSS["slate_50"],
                     fg=CSS["slate_600"], width=w, anchor='w').pack(side='left', padx=1)
        if self.rol != 'pastor':
            tk.Label(hdr, text="Acc.", font=("Segoe UI", 8, "bold"), bg=CSS["slate_50"],
                     fg=CSS["slate_600"], width=6, anchor='center').pack(side='right')
        tk.Frame(tc, bg=CSS["slate_200"], height=1).pack(fill='x')

        lf = tk.Frame(tc, bg="white"); lf.pack(fill='both', expand=True)
        self._ic = tk.Canvas(lf, bg="white", highlightthickness=0, bd=0)
        isb = ttk.Scrollbar(lf, orient="vertical", command=self._ic.yview)
        self._ii = tk.Frame(self._ic, bg="white")
        self._ii.bind("<Configure>", lambda e: self._ic.configure(scrollregion=self._ic.bbox("all")))
        self._icw = self._ic.create_window((0, 0), window=self._ii, anchor="nw")
        self._ic.configure(yscrollcommand=isb.set)
        self._ic.bind('<Configure>', lambda e: self._ic.itemconfig(self._icw, width=e.width))
        isb.pack(side="right", fill="y"); self._ic.pack(side="left", fill="both", expand=True)

    def _get_ib(self):
        v = self.e_ib.get().strip()
        return "" if v == "Buscar por codigo, descripcion..." else v

    def _cargar_inventario(self):
        for w in self._ii.winfo_children():
            w.destroy()
        busq, cat = self._get_ib(), self.cmb.get()
        try:
            with db_cursor() as (c, con):
                q = "SELECT id,codigo,descripcion,unidad_medida,ubicacion,cantidad,categoria,estado FROM inventario WHERE 1=1"
                p = []
                if busq:
                    q += " AND (codigo LIKE ? OR descripcion LIKE ? OR ubicacion LIKE ?)"
                    p += [f"%{busq}%"] * 3
                if cat != "Todas":
                    q += " AND categoria=?"
                    p.append(cat)
                c.execute(q, p)
                items = c.fetchall()
                c.execute("SELECT COUNT(*),COALESCE(SUM(cantidad),0) FROM inventario")
                st = c.fetchone()
                c.execute("SELECT COUNT(DISTINCT categoria) FROM inventario WHERE categoria IS NOT NULL AND categoria!=''")
                nc = c.fetchone()[0]
                c.execute("SELECT estado,COUNT(*) FROM inventario GROUP BY estado")
                ec = dict(c.fetchall())
        except Exception as e:
            Notificacion(self.root, f"Error al cargar inventario: {e}", "error")
            return

        self._inv_stats["reg"].config(text=str(st[0]))
        self._inv_stats["items"].config(text=str(entero_seguro(st[1])))
        self._inv_stats["cats"].config(text=str(nc))
        et = " ".join(f"{k}:{v}" for k, v in list(ec.items())[:3]) if ec else "0"
        self._inv_stats["est"].config(text=et)

        if not items:
            ef = tk.Frame(self._ii, bg="white", pady=40); ef.pack(fill='x')
            tk.Label(ef, text="Sin items en inventario", font=("Segoe UI", 12, "bold"), bg="white", fg=CSS["slate_500"]).pack()
            tk.Label(ef, text="Comience agregando articulos", font=("Segoe UI", 9), bg="white", fg=CSS["slate_400"]).pack(pady=(4, 0))
            return

        for i, (iid, cod, desc, und, ubi, cant, cat_v, est) in enumerate(items):
            rbg = "white" if i % 2 == 0 else CSS["slate_50"]
            row = tk.Frame(self._ii, bg=rbg, padx=12, pady=6); row.pack(fill='x')

            cf = tk.Frame(row, bg=CSS["slate_200"], padx=4, pady=1); cf.pack(side='left', padx=(0, 3))
            tk.Label(cf, text=cod or "-", font=("Consolas", 8, "bold"), bg=CSS["slate_200"], fg=CSS["slate_700"]).pack()

            tk.Label(row, text=(desc or "-")[:30], font=("Segoe UI", 9), bg=rbg, fg=CSS["slate_800"],
                     width=28, anchor='w').pack(side='left', padx=1)
            tk.Label(row, text=und or "-", font=("Segoe UI", 8), bg=rbg, fg=CSS["slate_600"],
                     width=7, anchor='w').pack(side='left', padx=1)
            tk.Label(row, text=(ubi or "-")[:12], font=("Segoe UI", 8), bg=rbg, fg=CSS["slate_600"],
                     width=13, anchor='w').pack(side='left', padx=1)

            qf = tk.Frame(row, bg=CSS["blue_50"], padx=4, pady=0); qf.pack(side='left', padx=1)
            tk.Label(qf, text=str(entero_seguro(cant)), font=("Segoe UI", 9, "bold"), bg=CSS["blue_50"], fg=CSS["blue_700"]).pack()

            tk.Label(row, text=cat_v or "-", font=("Segoe UI", 8), bg=rbg, fg=CSS["slate_500"],
                     width=10, anchor='w').pack(side='left', padx=1)

            ebg, efg = ESTADO_COLOR.get(est, (CSS["slate_100"], CSS["slate_600"]))
            ef2 = tk.Frame(row, bg=ebg, padx=4, pady=0); ef2.pack(side='left', padx=1)
            tk.Label(ef2, text=f"● {est}", font=("Segoe UI", 7), bg=ebg, fg=efg).pack()

            if self.rol != 'pastor':
                af = tk.Frame(row, bg=rbg); af.pack(side='right')
                eb = tk.Label(af, text="Ed", font=("Segoe UI", 8, "bold"), bg=rbg, fg=CSS["blue_600"],
                              padx=4, cursor="hand2")
                eb.pack(side='left', padx=1)
                item_data = (iid, cod, desc, und, ubi, cant, cat_v, est)
                eb.bind("<Button-1>", lambda e, it=item_data: self._inv_modal(it))
                eb.bind("<Enter>", lambda e, lbl=eb: lbl.config(bg=CSS["blue_50"]))
                eb.bind("<Leave>", lambda e, lbl=eb, bg=rbg: lbl.config(bg=bg))

                if self.rol == 'superusuario':
                    db = tk.Label(af, text="X", font=("Segoe UI", 8, "bold"), bg=rbg, fg=CSS["rose_500"],
                                  padx=4, cursor="hand2")
                    db.pack(side='left', padx=1)
                    db.bind("<Button-1>", lambda e, x=iid: self._eliminar_inv(x))
                    db.bind("<Enter>", lambda e, lbl=db: lbl.config(bg=CSS["rose_50"]))
                    db.bind("<Leave>", lambda e, lbl=db, bg=rbg: lbl.config(bg=bg))

        self._ic.update_idletasks()
        self._ic.configure(scrollregion=self._ic.bbox("all"))

    def _inv_modal(self, item=None):
        if self.rol == 'pastor':
            Notificacion(self.root, "Modo solo lectura: no puede modificar inventario", "aviso")
            return
        m = tk.Toplevel(self.root)
        m.title("Editar Item" if item else "Nuevo Item")
        m.configure(bg="white"); m.resizable(False, False)
        m.transient(self.root); m.grab_set()
        mw, mh = 480, 500
        x = self.root.winfo_rootx() + (self.root.winfo_width() - mw) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - mh) // 2
        m.geometry(f"{mw}x{mh}+{x}+{y}")

        hf = tk.Frame(m, bg="white", padx=20, pady=10); hf.pack(fill='x')
        tk.Label(hf, text="Editar Item" if item else "Nuevo Item de Inventario",
                 font=("Segoe UI", 12, "bold"), bg="white", fg=CSS["slate_900"]).pack(side='left')
        cb = tk.Label(hf, text="✕", font=("Segoe UI", 13), bg="white", fg=CSS["slate_400"], cursor="hand2")
        cb.pack(side='right'); cb.bind("<Button-1>", lambda e: m.destroy())
        tk.Frame(m, bg=CSS["slate_200"], height=1).pack(fill='x')

        ct = tk.Frame(m, bg="white", padx=20, pady=12); ct.pack(fill='both', expand=True)

        def _lbl(p, t):
            tk.Label(p, text=t, font=("Segoe UI", 7, "bold"), bg="white", fg=CSS["slate_500"]).pack(anchor='w', pady=(6, 1))
        def _ent(p, w=20):
            ef = tk.Frame(p, bg=CSS["slate_200"]); ef.pack(fill='x', ipady=1)
            e = tk.Entry(ef, font=("Segoe UI", 9), bg="white", fg=CSS["slate_800"], relief='flat', width=w)
            e.pack(fill='x', padx=1, pady=1, ipady=4); return e

        r1 = tk.Frame(ct, bg="white"); r1.pack(fill='x')
        c1 = tk.Frame(r1, bg="white"); c1.pack(side='left', fill='x', expand=True, padx=(0, 4))
        _lbl(c1, "CODIGO *"); me_cod = _ent(c1)
        c2 = tk.Frame(r1, bg="white"); c2.pack(side='left', fill='x', expand=True, padx=(4, 0))
        _lbl(c2, "CANTIDAD"); me_cant = _ent(c2)

        _lbl(ct, "DESCRIPCION *"); me_desc = _ent(ct)

        r2 = tk.Frame(ct, bg="white"); r2.pack(fill='x')
        c3 = tk.Frame(r2, bg="white"); c3.pack(side='left', fill='x', expand=True, padx=(0, 4))
        _lbl(c3, "UNIDAD DE MEDIDA"); me_und = _ent(c3)
        c4 = tk.Frame(r2, bg="white"); c4.pack(side='left', fill='x', expand=True, padx=(4, 0))
        _lbl(c4, "UBICACION"); me_ubi = _ent(c4)

        _lbl(ct, "CATEGORIA")
        me_cat = ttk.Combobox(ct, values=CATEGORIAS_INV[1:], state="readonly", font=("Segoe UI", 9))
        me_cat.current(5); me_cat.pack(fill='x', pady=2)

        _lbl(ct, "ESTADO")
        esf = tk.Frame(ct, bg="white"); esf.pack(fill='x', pady=2)
        me_est = tk.StringVar(value="Bueno")
        for est in ESTADOS_INV:
            clr = ESTADO_COLOR[est][1]
            tk.Radiobutton(esf, text=est, variable=me_est, value=est, font=("Segoe UI", 8),
                           bg="white", fg=clr, selectcolor="white",
                           activebackground="white", cursor="hand2").pack(side='left', padx=(0, 10))

        edit_id = None
        if item:
            edit_id = item[0]
            for e, v in [(me_cod, item[1]), (me_desc, item[2]), (me_und, item[3]),
                         (me_ubi, item[4]), (me_cant, str(entero_seguro(item[5])) if item[5] else "0")]:
                e.insert(0, str(v or ""))
            if item[6]:
                try: me_cat.set(item[6])
                except: pass
            if item[7]:
                me_est.set(item[7])

        tk.Frame(m, bg=CSS["slate_200"], height=1).pack(fill='x', side='bottom')
        ff = tk.Frame(m, bg=CSS["slate_50"], padx=20, pady=8); ff.pack(fill='x', side='bottom')

        def _save():
            cod = me_cod.get().strip()
            desc = me_desc.get().strip()
            if not cod or not desc:
                Notificacion(self.root, "Codigo y descripcion obligatorios", "aviso"); return
            try:
                cant_val = int(me_cant.get().strip() or "0")
            except ValueError:
                Notificacion(self.root, "Cantidad debe ser un numero entero", "aviso"); return

            vals = (cod.upper(), desc, me_und.get().strip() or "Unidad",
                    me_ubi.get().strip(), cant_val, me_cat.get(), me_est.get(),
                    datetime.now().strftime("%Y-%m-%d"))

            try:
                if edit_id:
                    with db_cursor() as (c, con):
                        c.execute("""UPDATE inventario SET codigo=?,descripcion=?,unidad_medida=?,
                            ubicacion=?,cantidad=?,categoria=?,estado=?,fecha_registro=? WHERE id=?""",
                            vals + (edit_id,))
                    msg = "Item actualizado"
                else:
                    with db_cursor() as (c, con):
                        c.execute("""INSERT INTO inventario (codigo,descripcion,unidad_medida,
                            ubicacion,cantidad,categoria,estado,fecha_registro) VALUES (?,?,?,?,?,?,?,?)""", vals)
                    msg = "Item agregado correctamente"
                m.destroy()
                self._cargar_inventario()
                Notificacion(self.root, msg, "exito")
            except sqlite3.IntegrityError:
                Notificacion(self.root, f"El codigo '{cod.upper()}' ya existe. Debe ser unico.", "error")
            except Exception as e:
                Notificacion(self.root, f"Error al guardar: {e}", "error")

        tk.Label(ff, text="Cancelar", font=("Segoe UI", 9), bg=CSS["slate_50"], fg=CSS["slate_600"],
                 padx=10, pady=4, cursor="hand2").pack(side='left')
        ff.winfo_children()[-1].bind("<Button-1>", lambda e: m.destroy())
        Boton(ff, texto="Guardar" if not item else "Actualizar", comando=_save, color=CSS["emerald_600"]).pack(side='right')

    def _eliminar_inv(self, iid):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede eliminar items", "aviso"); return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este item permanentemente?"):
            return
        try:
            with db_cursor() as (c, con):
                c.execute("DELETE FROM inventario WHERE id=?", (iid,))
            self._cargar_inventario()
            Notificacion(self.root, "Item eliminado", "exito")
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _imprimir_inventario(self):
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT codigo,descripcion,unidad_medida,ubicacion,cantidad,categoria,estado FROM inventario")
                items = c.fetchall()
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error"); return
        if not items:
            Notificacion(self.root, "No hay datos en inventario", "aviso"); return
        now = datetime.now()

        html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Toma Fisica de Inventario</title>
<style>
body {{ margin:0; padding:30px; background:F5F5F4; font-family:'Segoe UI',Arial,sans-serif; }}
.container {{ max-width:900px; margin:0 auto; background:white; padding:40px; box-shadow:0 4px 20px rgba(0,0,0,0.1); }}
h1 {{ text-align:center; color:1C1917; font-size:20px; margin:0; text-transform:uppercase; }}
.sub {{ text-align:center; color:78716C; font-size:11px; margin:4px 0 20px 0; }}
.meta {{ display:flex; justify-content:space-between; font-size:11px; color:78716C; margin-bottom:20px; padding-bottom:10px; border-bottom:2px solid E7E5E4; }}
table {{ width:100%; border-collapse:collapse; font-size:11px; }}
th {{ background:F5F5F4; color:57534E; text-align:left; padding:8px 10px; font-weight:700; text-transform:uppercase; font-size:9px; letter-spacing:0.5px; border-bottom:2px solid D6D3D1; }}
td {{ padding:8px 10px; border-bottom:1px solid E7E5E4; color:44403C; }}
tr:hover {{ background:FAFAF9; }}
.codigo {{ font-family:Consolas,monospace; font-weight:700; background:F5F5F4; padding:2px 6px; border-radius:3px; font-size:10px; }}
.estado {{ padding:2px 8px; border-radius:12px; font-size:9px; font-weight:700; text-transform:uppercase; }}
.est-nuevo {{ background:DBEAFE; color:1D4ED8; }}
.est-bueno {{ background:D1FAE5; color:047857; }}
.est-regular {{ background:FEF3C7; color:B45309; }}
.est-malo {{ background:FFE4E6; color:BE123C; }}
.obs {{ margin-top:30px; padding:20px; border:1px dashed D6D3D1; border-radius:6px; }}
.obs-title {{ font-size:10px; font-weight:700; color:78716C; text-transform:uppercase; margin-bottom:10px; }}
.signatures {{ display:flex; justify-content:space-between; margin-top:40px; padding-top:20px; border-top:1px dashed D6D3D1; }}
.sig {{ text-align:center; flex:1; }}
.sig-line {{ width:200px; height:1px; background:78716C; margin:0 auto 6px auto; }}
.sig-name {{ font-size:11px; font-weight:900; color:1C1917; text-transform:uppercase; }}
.sig-title {{ font-size:9px; color:78716C; }}
@media print {{ body {{ background:white; }} .container {{ box-shadow:none; }} }}
</style></head><body>
<div class="container">
<h1>Toma Fisica de Inventario Parroquial</h1>
<p class="sub">Parroquia Eclesiastica de la Zona 2 · Santa Barbara de Zulia</p>
<div class="meta">
  <span><strong>Fecha:</strong> {now.strftime('%d/%m/%Y')}</span>
  <span><strong>Total Items:</strong> {len(items)}</span>
</div>
<table>
<thead><tr>
  <th>Codigo</th><th>Descripcion</th><th>Categoria</th><th>Ubicacion</th>
  <th style="text-align:center">Cant.</th><th style="text-align:center">Und.</th><th style="text-align:center">Estado</th>
</tr></thead>
<tbody>"""

        for it in items:
            estado = str(it[6] or '-')
            est_class = f"est-{estado.lower()}" if estado in ESTADOS_INV else ""
            html_doc += f"""<tr>
  <td><span class="codigo">{html.escape(str(it[0] or '-'))}</span></td>
  <td>{html.escape(str(it[1] or '-'))}</td>
  <td>{html.escape(str(it[5] or '-'))}</td>
  <td>{html.escape(str(it[3] or '-'))}</td>
  <td style="text-align:center;font-weight:700">{html.escape(str(it[4] if it[4] is not None else 0))}</td>
  <td style="text-align:center">{html.escape(str(it[2] or '-'))}</td>
  <td style="text-align:center"><span class="estado {est_class}">{html.escape(estado)}</span></td>
</tr>"""

        html_doc += f"""</tbody></table>
<div class="obs"><div class="obs-title">Observaciones y Anotaciones de Auditoria</div><div style="height:60px"></div></div>
<div class="signatures">
  <div class="sig"><div class="sig-line"></div><div class="sig-name">Responsable de Inventario</div><div class="sig-title">Parroco o Delegado Administrador</div></div>
  <div class="sig"><div class="sig-line"></div><div class="sig-name">Auditor Parroquial</div><div class="sig-title">Consejo de Asuntos Economicos</div></div>
</div>
</div></body></html>"""

        f = tempfile.NamedTemporaryFile(mode='w', prefix='parroquia_inv_', suffix='.html',
                                         delete=False, encoding='utf-8')
        f.write(html_doc); f.close()
        abrir_archivo(f.name)
        Notificacion(self.root, "Inventario generado para impresion", "exito")


    def _construir_usuarios(self):
        f = self.frames['usuarios']
        main = tk.Frame(f, bg=CSS["slate_50"]); main.pack(expand=True, fill='both')

        hf = tk.Frame(main, bg=CSS["slate_50"]); hf.pack(fill='x', pady=(0, 8))
        tk.Label(hf, text="Control de Operadores del Sistema",
                 font=("Segoe UI", 12, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(side='left')
        Boton(hf, texto="+ Registrar Operador", comando=self._user_modal, color=CSS["amber_600"]).pack(side='right')

        tc = tk.Frame(main, bg="white"); tc.pack(fill='both', expand=True)
        hdr = tk.Frame(tc, bg=CSS["slate_50"], padx=12, pady=6); hdr.pack(fill='x')
        for txt, w in [("ID", 5), ("Usuario", 12), ("Nombre Completo", 24), ("Rol", 14), ("Ultimo Acceso", 16), ("Acciones", 12)]:
            tk.Label(hdr, text=txt, font=("Segoe UI", 8, "bold"), bg=CSS["slate_50"],
                     fg=CSS["slate_600"], width=w, anchor='w').pack(side='left', padx=2)
        tk.Frame(tc, bg=CSS["slate_200"], height=1).pack(fill='x')

        lf = tk.Frame(tc, bg="white"); lf.pack(fill='both', expand=True)
        self._uc = tk.Canvas(lf, bg="white", highlightthickness=0, bd=0)
        usb = ttk.Scrollbar(lf, orient="vertical", command=self._uc.yview)
        self._ui = tk.Frame(self._uc, bg="white")
        self._ui.bind("<Configure>", lambda e: self._uc.configure(scrollregion=self._uc.bbox("all")))
        self._ucw = self._uc.create_window((0, 0), window=self._ui, anchor="nw")
        self._uc.configure(yscrollcommand=usb.set)
        self._uc.bind('<Configure>', lambda e: self._uc.itemconfig(self._ucw, width=e.width))
        usb.pack(side="right", fill="y"); self._uc.pack(side="left", fill="both", expand=True)    


    def _cargar_usuarios(self):
        for w in self._ui.winfo_children():
            w.destroy()
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT id,usuario,nombre,rol,ultimo_acceso FROM usuarios ORDER BY id")
                users = c.fetchall()
        except Exception:
            return

        for i, row_data in enumerate(users):
            uid = row_data[0]
            u = row_data[1]
            n = row_data[2]
            r = row_data[3]
            ultimo = row_data[4] if len(row_data) > 4 else None

            rbg = CSS["slate_50"] if i % 2 == 0 else CSS["slate_100"]
            row = tk.Frame(self._ui, bg=rbg, padx=12, pady=8)
            row.pack(fill='x')

            tk.Label(row, text=str(uid), font=("Segoe UI", 8), bg=rbg, fg=CSS["slate_500"],
                     width=5, anchor='center').pack(side='left')
            tk.Label(row, text=f"@{u}", font=("Segoe UI", 9, "bold"), bg=rbg, fg=CSS["blue_600"],
                     width=12, anchor='w').pack(side='left', padx=2)
            tk.Label(row, text=n, font=("Segoe UI", 9), bg=rbg, fg=CSS["slate_800"],
                     width=24, anchor='w').pack(side='left', padx=2)

            rl = {"superusuario": ("Administrador", CSS["blue_600"]),
                  "secretaria": ("Secretaria", CSS["emerald_600"]),
                  "pastor": ("Pastor (Consulta)", CSS["violet_600"])}.get(r, (r, CSS["slate_500"]))
            rf = tk.Frame(row, bg=rl[1], padx=8, pady=2)
            rf.pack(side='left', padx=4)
            tk.Label(rf, text=rl[0], font=("Segoe UI", 7, "bold"), bg=rl[1], fg="white").pack()

            ua_text = ultimo if ultimo else "Nunca"
            tk.Label(row, text=ua_text, font=("Segoe UI", 8), bg=rbg, fg=CSS["slate_400"],
                     width=16, anchor='w').pack(side='left', padx=4)

            af = tk.Frame(row, bg=rbg)
            af.pack(side='right')

            # Botón editar con función directa
            ud = (uid, u, n, r)
            Boton(af, texto="✏ Editar", comando=lambda datos=ud: self._user_modal(datos),
                  color=CSS["blue_600"], padx=8, pady=3,
                  fuente=("Segoe UI", 8, "bold")).pack(side='left', padx=2)

            if u != 'admin':
                Boton(af, texto="🗑 Eliminar", comando=lambda x=uid: self._user_eliminar(x),
                      color=CSS["rose_600"], padx=8, pady=3,
                      fuente=("Segoe UI", 8, "bold")).pack(side='left', padx=2)

        self._uc.update_idletasks()
        self._uc.configure(scrollregion=self._uc.bbox("all"))

    def _user_eliminar(self, uid):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede eliminar usuarios", "aviso")
            return
        try:
            with db_cursor() as (c, con):
                c.execute("SELECT usuario, rol FROM usuarios WHERE id=?", (uid,))
                objetivo = c.fetchone()
                if not objetivo:
                    Notificacion(self.root, "Usuario no encontrado", "aviso"); return
                if objetivo[0] == 'admin':
                    Notificacion(self.root, "El usuario admin principal no puede eliminarse", "aviso"); return
                if objetivo[1] == 'superusuario':
                    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='superusuario'")
                    if c.fetchone()[0] <= 1:
                        Notificacion(self.root, "No puede eliminar al ultimo Administrador", "aviso"); return
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error"); return
        if not messagebox.askyesno("Confirmar", "¿Dar de baja al operador?"):
            return
        try:
            with db_cursor() as (c, con):
                c.execute("DELETE FROM usuarios WHERE id=?", (uid,))
            self._cargar_usuarios()
            Notificacion(self.root, "Operador eliminado", "exito")
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")

    def _user_modal(self, user=None):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede gestionar usuarios", "aviso")
            return
        m = tk.Toplevel(self.root)
        m.title("Editar Operador" if user else "Nuevo Operador")
        m.configure(bg=CSS["slate_50"])
        m.resizable(False, False)
        m.transient(self.root)
        m.grab_set()
        mw, mh = 440, 440
        x = self.root.winfo_rootx() + (self.root.winfo_width() - mw) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - mh) // 2
        m.geometry(f"{mw}x{mh}+{x}+{y}")

        hf = tk.Frame(m, bg=CSS["slate_50"], padx=18, pady=10)
        hf.pack(fill='x')
        tk.Label(hf, text="Editar Operador" if user else "Registrar Nuevo Operador",
                 font=("Segoe UI", 12, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(side='left')
        cb = tk.Label(hf, text="✕", font=("Segoe UI", 12), bg=CSS["slate_50"], fg=CSS["slate_400"], cursor="hand2")
        cb.pack(side='right')
        cb.bind("<Button-1>", lambda e: m.destroy())
        tk.Frame(m, bg=CSS["slate_200"], height=1).pack(fill='x')

        ct = tk.Frame(m, bg=CSS["slate_50"], padx=18, pady=10)
        ct.pack(fill='both', expand=True)

        def _lbl(p, t):
            tk.Label(p, text=t, font=("Segoe UI", 8, "bold"), bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(6, 2))

        def _ent(p, show_char=None):
            ef = tk.Frame(p, bg=CSS["slate_300"])
            ef.pack(fill='x')
            e = tk.Entry(ef, font=("Segoe UI", 10), bg="#FFFFFF", fg=CSS["slate_800"],
                         relief='flat', insertbackground=CSS["slate_800"])
            if show_char:
                e.config(show=show_char)
            e.pack(fill='x', padx=1, pady=1, ipady=6)
            return e

        _lbl(ct, "USUARIO * (sin espacios, solo minúsculas)")
        me_u = _ent(ct)

        _lbl(ct, "NOMBRE COMPLETO *")
        me_n = _ent(ct)

        me_p = None
        if not user:
            _lbl(ct, "CONTRASEÑA * (mínimo 6 caracteres)")
            me_p = _ent(ct, show_char="●")

        _lbl(ct, "ROL / PRIVILEGIO")
        me_r = ttk.Combobox(ct, values=["superusuario", "secretaria", "pastor"],
                            state="readonly", font=("Segoe UI", 10))
        me_r.pack(fill='x', pady=2)
        me_r.set("pastor")

        if user:
            me_u.insert(0, user[1])
            me_n.insert(0, user[2])
            me_r.set(user[3])
            if user[1] == 'admin':
                me_u.config(state='disabled')
                me_r.config(state='disabled')

        tk.Frame(m, bg=CSS["slate_200"], height=1).pack(fill='x', side='bottom')
        ff = tk.Frame(m, bg=CSS["slate_50"], padx=18, pady=8)
        ff.pack(fill='x', side='bottom')

        def _save():
            u_val = me_u.get().strip().lower()
            n_val = me_n.get().strip()
            r_val = me_r.get()
            if not u_val or not n_val:
                Notificacion(self.root, "Usuario y nombre son obligatorios", "aviso")
                return
            if r_val not in ("superusuario", "secretaria", "pastor"):
                Notificacion(self.root, "Seleccione un rol válido", "aviso")
                return

            u_sanitized = sanitizar_usuario(u_val)
            if u_sanitized != u_val:
                Notificacion(self.root, "El usuario solo puede contener letras, números, puntos y guiones bajos", "aviso")
                return

            if not user:
                p_val = me_p.get()
                if not p_val or len(p_val) < 6:
                    Notificacion(self.root, "Contraseña debe tener al menos 6 caracteres", "aviso")
                    return
                pw_hash = hash_con_sal(p_val)
            else:
                pw_hash = None

            try:
                if user:
                    if user[3] == 'superusuario' and r_val != 'superusuario':
                        with db_cursor() as (c, con):
                            c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='superusuario'")
                            if c.fetchone()[0] <= 1:
                                Notificacion(self.root, "No puede degradar al último Administrador", "aviso")
                                return
                    if u_sanitized != user[1]:
                        with db_cursor() as (c, con):
                            c.execute("SELECT id FROM usuarios WHERE usuario=?", (u_sanitized,))
                            if c.fetchone():
                                Notificacion(self.root, f"El usuario '{u_val}' ya existe", "error")
                                return
                    with db_cursor() as (c, con):
                        c.execute("UPDATE usuarios SET usuario=?,nombre=?,rol=? WHERE id=?",
                                  (u_sanitized, n_val, r_val, user[0]))
                    msg = "Operador actualizado"
                else:
                    with db_cursor() as (c, con):
                        c.execute("INSERT INTO usuarios (usuario,nombre,password,rol) VALUES (?,?,?,?)",
                                  (u_sanitized, n_val, pw_hash, r_val))
                    msg = "Operador registrado exitosamente"
                m.destroy()
                self._cargar_usuarios()
                Notificacion(self.root, msg, "exito")
            except sqlite3.IntegrityError:
                Notificacion(self.root, f"El usuario '{u_val}' ya existe", "error")
            except Exception as e:
                Notificacion(self.root, f"Error: {e}", "error")

        cancel = tk.Label(ff, text="Cancelar", font=("Segoe UI", 9), bg=CSS["slate_50"],
                          fg=CSS["slate_600"], padx=10, pady=4, cursor="hand2")
        cancel.pack(side='left')
        cancel.bind("<Button-1>", lambda e: m.destroy())
        Boton(ff, texto="Guardar", comando=_save, color=CSS["amber_600"]).pack(side='right')

        def _lbl(p, t):
            tk.Label(p, text=t, font=("Segoe UI", 8, "bold"), bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(6, 2))

        def _ent(p, show_char=None):
            ef = tk.Frame(p, bg=CSS["slate_300"])
            ef.pack(fill='x')
            e = tk.Entry(ef, font=("Segoe UI", 10), bg="#FFFFFF", fg=CSS["slate_800"],
                         relief='flat', insertbackground=CSS["slate_800"])
            if show_char:
                e.config(show=show_char)
            e.pack(fill='x', padx=1, pady=1, ipady=6)
            return e

        _lbl(ct, "USUARIO * (sin espacios, solo minúsculas)")
        me_u = _ent(ct)

        _lbl(ct, "NOMBRE COMPLETO *")
        me_n = _ent(ct)

        me_p = None
        if not user:
            _lbl(ct, "CONTRASEÑA * (mínimo 6 caracteres)")
            me_p = _ent(ct, show_char="●")

        _lbl(ct, "ROL / PRIVILEGIO")
        me_r = ttk.Combobox(ct, values=["superusuario", "secretaria", "pastor"],
                            state="readonly", font=("Segoe UI", 10))
        me_r.pack(fill='x', pady=2)
        me_r.set("pastor")

        if user:
            me_u.insert(0, user[1])
            me_n.insert(0, user[2])
            me_r.set(user[3])
            me_u.config(state='disabled')
            if user[1] == 'admin':
                me_r.config(state='disabled')

        tk.Frame(m, bg=CSS["slate_200"], height=1).pack(fill='x', side='bottom')
        ff = tk.Frame(m, bg=CSS["slate_50"], padx=18, pady=8)
        ff.pack(fill='x', side='bottom')

        def _save():
            u_val = me_u.get().strip().lower()
            n_val = me_n.get().strip()
            r_val = me_r.get()
            if not u_val or not n_val:
                Notificacion(self.root, "Usuario y nombre son obligatorios", "aviso")
                return
            if r_val not in ("superusuario", "secretaria", "pastor"):
                Notificacion(self.root, "Seleccione un rol válido", "aviso")
                return

            u_sanitized = sanitizar_usuario(u_val)
            if u_sanitized != u_val:
                Notificacion(self.root, "El usuario solo puede contener letras, números, puntos y guiones bajos", "aviso")
                return

            if not user:
                p_val = me_p.get()
                if not p_val or len(p_val) < 6:
                    Notificacion(self.root, "Contraseña debe tener al menos 6 caracteres", "aviso")
                    return
                pw_hash = hash_con_sal(p_val)
            else:
                pw_hash = None

            try:
                if user:
                    if user[3] == 'superusuario' and r_val != 'superusuario':
                        with db_cursor() as (c, con):
                            c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='superusuario'")
                            if c.fetchone()[0] <= 1:
                                Notificacion(self.root, "No puede degradar al último Administrador", "aviso")
                                return
                    with db_cursor() as (c, con):
                        c.execute("UPDATE usuarios SET nombre=?,rol=? WHERE id=?",
                                  (n_val, r_val, user[0]))
                    msg = "Operador actualizado"
                else:
                    with db_cursor() as (c, con):
                        c.execute("INSERT INTO usuarios (usuario,nombre,password,rol) VALUES (?,?,?,?)",
                                  (u_sanitized, n_val, pw_hash, r_val))
                    msg = "Operador registrado exitosamente"
                m.destroy()
                self._cargar_usuarios()
                Notificacion(self.root, msg, "exito")
            except sqlite3.IntegrityError:
                Notificacion(self.root, f"El usuario '{u_val}' ya existe", "error")
            except Exception as e:
                Notificacion(self.root, f"Error: {e}", "error")

        cancel = tk.Label(ff, text="Cancelar", font=("Segoe UI", 9), bg=CSS["slate_50"],
                          fg=CSS["slate_600"], padx=10, pady=4, cursor="hand2")
        cancel.pack(side='left')
        cancel.bind("<Button-1>", lambda e: m.destroy())
        Boton(ff, texto="Guardar", comando=_save, color=CSS["amber_600"]).pack(side='right')

    def _construir_ajustes(self):
        f = self.frames['ajustes']
        main = tk.Frame(f, bg=CSS["slate_50"]); main.pack(expand=True, fill='both')

        # Info del sistema
        card = tk.Frame(main, bg=CSS["slate_50"], padx=20, pady=16)
        card.pack(fill='x')
        tk.Label(card, text="Información del Sistema",
                 font=("Segoe UI", 11, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')
        tk.Frame(card, bg=CSS["slate_200"], height=1).pack(fill='x', pady=8)
        self._lbl_info_usuario = tk.Label(card, text="", font=("Segoe UI", 9), bg=CSS["slate_50"], fg=CSS["slate_600"])
        self._lbl_info_usuario.pack(anchor='w', pady=1)
        self._actualizar_info_usuario()
        for line in [
            "Base de datos: SQLite (parroquia_unificado.db)",
            "Motor de UI: Tkinter (Python 3)",
            f"Seguridad: Login con bloqueo progresivo ({MAX_INTENTOS} intentos max)",
            "Versión: Gestor Parroquial v5.1",
        ]:
            tk.Label(card, text=line, font=("Segoe UI", 9), bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=1)

        # Cambiar nombre
        card_nombre = tk.Frame(main, bg=CSS["slate_50"], padx=20, pady=16)
        card_nombre.pack(fill='x', pady=(6, 0))
        tk.Label(card_nombre, text="Cambiar Nombre de Usuario",
                 font=("Segoe UI", 11, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')
        tk.Frame(card_nombre, bg=CSS["slate_200"], height=1).pack(fill='x', pady=8)

        nombre_form = tk.Frame(card_nombre, bg=CSS["slate_50"])
        nombre_form.pack(fill='x')

        tk.Label(nombre_form, text="NUEVO NOMBRE COMPLETO", font=("Segoe UI", 8, "bold"),
                 bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(0, 2))
        ef_nombre_border = tk.Frame(nombre_form, bg=CSS["slate_300"])
        ef_nombre_border.pack(fill='x')
        self._nuevo_nombre = tk.Entry(ef_nombre_border, font=("Segoe UI", 10), bg="#FFFFFF",
                                       fg=CSS["slate_800"], relief='flat', insertbackground=CSS["slate_800"])
        self._nuevo_nombre.pack(fill='x', padx=1, pady=1, ipady=6)
        self._nuevo_nombre.insert(0, self.nombre)

        tk.Label(nombre_form, text="CONTRASEÑA ACTUAL (para confirmar)", font=("Segoe UI", 8, "bold"),
                 bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(10, 2))
        ef_pw_border = tk.Frame(nombre_form, bg=CSS["slate_300"])
        ef_pw_border.pack(fill='x')
        self._pw_confirmar_nombre = tk.Entry(ef_pw_border, font=("Segoe UI", 10), bg="#FFFFFF",
                                              fg=CSS["slate_800"], relief='flat', show="●",
                                              insertbackground=CSS["slate_800"])
        self._pw_confirmar_nombre.pack(fill='x', padx=1, pady=1, ipady=6)

        Boton(nombre_form, texto="✏ Cambiar Nombre", comando=self._cambiar_nombre,
              color=CSS["blue_600"]).pack(anchor='w', pady=(10, 0))

        # Cambiar contraseña
        card_pw = tk.Frame(main, bg=CSS["slate_50"], padx=20, pady=16)
        card_pw.pack(fill='x', pady=(6, 0))
        tk.Label(card_pw, text="Cambiar Contraseña",
                 font=("Segoe UI", 11, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')
        tk.Frame(card_pw, bg=CSS["slate_200"], height=1).pack(fill='x', pady=8)

        pw_form = tk.Frame(card_pw, bg=CSS["slate_50"])
        pw_form.pack(fill='x')

        tk.Label(pw_form, text="CONTRASEÑA ACTUAL", font=("Segoe UI", 8, "bold"),
                 bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(0, 2))
        ef1_border = tk.Frame(pw_form, bg=CSS["slate_300"])
        ef1_border.pack(fill='x', pady=(0, 8))
        self._pw_actual = tk.Entry(ef1_border, font=("Segoe UI", 10), bg="#FFFFFF", fg=CSS["slate_800"],
                                   relief='flat', show="●", insertbackground=CSS["slate_800"])
        self._pw_actual.pack(fill='x', padx=1, pady=1, ipady=6)

        tk.Label(pw_form, text="NUEVA CONTRASEÑA (mínimo 6 caracteres)", font=("Segoe UI", 8, "bold"),
                 bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(0, 2))
        ef2_border = tk.Frame(pw_form, bg=CSS["slate_300"])
        ef2_border.pack(fill='x', pady=(0, 8))
        self._pw_nueva = tk.Entry(ef2_border, font=("Segoe UI", 10), bg="#FFFFFF", fg=CSS["slate_800"],
                                  relief='flat', show="●", insertbackground=CSS["slate_800"])
        self._pw_nueva.pack(fill='x', padx=1, pady=1, ipady=6)

        tk.Label(pw_form, text="CONFIRMAR NUEVA CONTRASEÑA", font=("Segoe UI", 8, "bold"),
                 bg=CSS["slate_50"], fg=CSS["slate_600"]).pack(anchor='w', pady=(0, 2))
        ef3_border = tk.Frame(pw_form, bg=CSS["slate_300"])
        ef3_border.pack(fill='x', pady=(0, 8))
        self._pw_confirmar = tk.Entry(ef3_border, font=("Segoe UI", 10), bg="#FFFFFF", fg=CSS["slate_800"],
                                      relief='flat', show="●", insertbackground=CSS["slate_800"])
        self._pw_confirmar.pack(fill='x', padx=1, pady=1, ipady=6)

        Boton(pw_form, texto="🔐 Cambiar Contraseña", comando=self._cambiar_pw,
              color=CSS["blue_600"]).pack(anchor='w', pady=(4, 0))

        # Respaldo
        card2 = tk.Frame(main, bg=CSS["slate_50"], padx=20, pady=16)
        card2.pack(fill='x', pady=(6, 0))
        tk.Label(card2, text="Respaldo y Restauración de Datos",
                 font=("Segoe UI", 11, "bold"), bg=CSS["slate_50"], fg=CSS["slate_800"]).pack(anchor='w')
        tk.Frame(card2, bg=CSS["slate_200"], height=1).pack(fill='x', pady=8)
        tk.Label(card2, text="Exporte todos los datos a un archivo JSON para respaldo.",
                 font=("Segoe UI", 9), bg=CSS["slate_50"], fg=CSS["slate_500"]).pack(anchor='w')

        bf = tk.Frame(card2, bg=CSS["slate_50"])
        bf.pack(fill='x', pady=(8, 0))
        if self.rol == 'superusuario':
            Boton(bf, texto="📥 Exportar Datos", comando=self._exportar_datos, color=CSS["emerald_600"]).pack(side='left', padx=(0, 4))
            Boton(bf, texto="📤 Importar Datos", comando=self._importar_datos, color=CSS["amber_600"]).pack(side='left', padx=4)
            Boton(bf, texto="🔄 Restablecer Todo", comando=self._reset_db, color=CSS["rose_500"]).pack(side='left', padx=4)
        else:
            tk.Label(bf, text="Solo el Administrador puede exportar, importar o restablecer datos.",
                     font=("Segoe UI", 8), bg=CSS["slate_50"], fg=CSS["slate_400"]).pack(anchor='w')



    def _actualizar_info_usuario(self):
        self._lbl_info_usuario.config(text=f"Usuario actual: {self.nombre} ({self.rol})")

    def _cambiar_nombre(self):
        nuevo = self._nuevo_nombre.get().strip()
        pw = self._pw_confirmar_nombre.get()

        if not nuevo:
            Notificacion(self.root, "Escriba el nuevo nombre", "aviso")
            return

        if len(nuevo) < 3:
            Notificacion(self.root, "El nombre debe tener al menos 3 caracteres", "aviso")
            return

        if not pw:
            Notificacion(self.root, "Escriba su contraseña para confirmar", "aviso")
            return

        try:
            with db_cursor() as (c, con):
                c.execute("SELECT password FROM usuarios WHERE id=?", (self.uid,))
                row = c.fetchone()
                if not row or not verificar_pw(pw, row[0]):
                    Notificacion(self.root, "Contraseña incorrecta", "error")
                    return
                c.execute("UPDATE usuarios SET nombre=? WHERE id=?", (nuevo, self.uid))

            self.nombre = nuevo
            self.root.title(f"Gestor Parroquial v5.1 - {self.nombre}")
            self._actualizar_info_usuario()
            self._pw_confirmar_nombre.delete(0, tk.END)
            Notificacion(self.root, "Nombre actualizado correctamente", "exito")
        except Exception as e:
            Notificacion(self.root, f"Error al cambiar nombre: {e}", "error")

    def _cambiar_pw(self):
        actual = self._pw_actual.get()
        nueva = self._pw_nueva.get()
        confirmar = self._pw_confirmar.get()

        if not actual or not nueva or not confirmar:
            Notificacion(self.root, "Complete todos los campos de contrasena", "aviso"); return
        if len(nueva) < 6:
            Notificacion(self.root, "La nueva contrasena debe tener al menos 6 caracteres", "aviso"); return
        if nueva != confirmar:
            Notificacion(self.root, "Las contrasenas nuevas no coinciden", "error"); return

        try:
            with db_cursor() as (c, con):
                c.execute("SELECT password FROM usuarios WHERE id=?", (self.uid,))
                row = c.fetchone()
                if not row or not verificar_pw(actual, row[0]):
                    Notificacion(self.root, "La contrasena actual es incorrecta", "error"); return
                c.execute("UPDATE usuarios SET password=? WHERE id=?",
                          (hash_con_sal(nueva), self.uid))
            self._pw_actual.delete(0, tk.END)
            self._pw_nueva.delete(0, tk.END)
            self._pw_confirmar.delete(0, tk.END)
            Notificacion(self.root, "Contrasena actualizada correctamente", "exito")
        except Exception as e:
            Notificacion(self.root, f"Error al cambiar contrasena: {e}", "error")

    def _exportar_datos(self):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede exportar respaldos", "aviso")
            return
        try:
            with db_cursor() as (c, con):
                data = {}
                for tbl in ['certificados_bautismo', 'certificados_comunion', 'certificados_confirmacion',
                            'certificados_matrimonio', 'certificados_defuncion', 'inventario', 'usuarios']:
                    c.execute(f"SELECT * FROM {tbl}")
                    cols = [d[0] for d in c.description]
                    data[tbl] = [dict(zip(cols, row)) for row in c.fetchall()]
            filepath = f"respaldo_parroquia_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Notificacion(self.root, f"Respaldo exportado: {filepath}", "exito")
        except Exception as e:
            Notificacion(self.root, f"Error al exportar: {e}", "error")

    def _importar_datos(self):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede importar respaldos", "aviso")
            return
        if not messagebox.askyesno("Confirmar", "¿Importar datos desde JSON? Esto REEMPLAZARA todos los datos actuales."):
            return
        try:
            filepath = simpledialog.askstring("Importar", "Ruta del archivo JSON:")
            if not filepath or not os.path.exists(filepath):
                Notificacion(self.root, "Archivo no encontrado", "aviso"); return
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("El respaldo debe ser un objeto JSON con tablas")
            with db_cursor() as (c, con):
                for tbl in ['certificados_bautismo', 'certificados_comunion', 'certificados_confirmacion',
                            'certificados_matrimonio', 'certificados_defuncion', 'inventario', 'usuarios']:
                    if tbl in data:
                        if not isinstance(data[tbl], list):
                            raise ValueError(f"Formato invalido para tabla {tbl}")
                        c.execute(f"PRAGMA table_info({tbl})")
                        columnas_validas = {col[1] for col in c.fetchall()}
                        c.execute(f"DELETE FROM {tbl}")
                        for row in data[tbl]:
                            if not isinstance(row, dict):
                                raise ValueError(f"Fila invalida en tabla {tbl}")
                            limpio = {k: v for k, v in row.items() if k in columnas_validas}
                            if not limpio:
                                continue
                            cols = ', '.join(limpio.keys())
                            vals = ', '.join(['?'] * len(limpio))
                            c.execute(f"INSERT INTO {tbl} ({cols}) VALUES ({vals})", tuple(limpio.values()))
                c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='superusuario'")
                if c.fetchone()[0] == 0:
                    c.execute("SELECT id FROM usuarios WHERE usuario='admin'")
                    admin_existente = c.fetchone()
                    if admin_existente:
                        c.execute("UPDATE usuarios SET rol='superusuario' WHERE id=?", (admin_existente[0],))
                    else:
                        c.execute("INSERT INTO usuarios (usuario,nombre,password,rol) VALUES (?,?,?,?)",
                                  ('admin', 'Administrador Principal', hash_con_sal('admin123'), 'superusuario'))
            Notificacion(self.root, "Datos importados exitosamente", "exito")
        except Exception as e:
            Notificacion(self.root, f"Error al importar: {e}", "error")

    def _reset_db(self):
        if self.rol != 'superusuario':
            Notificacion(self.root, "Solo el Administrador puede restablecer la base de datos", "aviso")
            return
        if not messagebox.askyesno("Confirmar", "¿RESTABLECER toda la base de datos? Se perderan todos los datos."):
            return
        if not messagebox.askyesno("Confirmar (2/2)", "Esta accion es IRREVERSIBLE. ¿Continua?"):
            return
        try:
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            inicializar_bd()
            Notificacion(self.root, "Base de datos restablecida", "exito")
            self._mostrar_pestana('dashboard')
        except Exception as e:
            Notificacion(self.root, f"Error: {e}", "error")
if __name__ == "__main__":
    limpiar_temporales()
    inicializar_bd()
    root = tk.Tk()
    root.withdraw()
    try:
        if os.path.exists("icono.ico"):
            root.iconbitmap("icono.ico")
    except Exception:
        pass
    root.deiconify()
    LoginApp(root)
    root.mainloop()
