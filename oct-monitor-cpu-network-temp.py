import os
import json
import time
import sys
import ctypes
import tkinter as tk
from tkinter import ttk
from tkinter import colorchooser
import psutil
import win32gui
import win32con
import win32api
import winsound
from PIL import Image, ImageDraw, ImageFont
import pystray
import threading
import subprocess
import urllib.request
import zipfile
import csv
from datetime import datetime

# =====================================================================
# FUNÇÕES E DIRETÓRIOS BASE
# =====================================================================
def log(message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

_base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_ct_dir = os.path.join(_base, "lib_coretemp")
_ct_exe = os.path.join(_ct_dir, "Core Temp.exe")
_ct_ini = os.path.join(_ct_dir, "CoreTemp.ini")

# =====================================================================
# ESTRUTURA C++ DO CORE TEMP (Ponte Direta para a Memória RAM)
# =====================================================================
class CoreTempSharedDataEx(ctypes.Structure):
    _fields_ = [
        ("uiLoad", ctypes.c_uint * 256),
        ("uiTjMax", ctypes.c_uint * 128),
        ("uiCoreCnt", ctypes.c_uint),
        ("uiCPUCnt", ctypes.c_uint),
        ("fTemp", ctypes.c_float * 256),
        ("fVID", ctypes.c_float),
        ("fCPUSpeed", ctypes.c_float),
        ("fFSBSpeed", ctypes.c_float),
        ("fMultiplier", ctypes.c_float),
        ("sCPUName", ctypes.c_char * 100),
        ("ucFahrenheit", ctypes.c_ubyte),
        ("ucDeltaToTjMax", ctypes.c_ubyte),
        ("ucTdpSupported", ctypes.c_ubyte),
        ("ucPowerSupported", ctypes.c_ubyte),
        ("uiStructVersion", ctypes.c_uint),
        ("uiTdp", ctypes.c_uint * 128),
        ("fPower", ctypes.c_float * 128),
        ("fMultipliers", ctypes.c_float * 256),
    ]

# =====================================================================
# GERENCIADOR DO CORE TEMP (DOWNLOAD, INI E WATCHDOG)
# =====================================================================
def ensure_coretemp():
    global _ct_exe
    if not os.path.exists(_ct_dir):
        os.makedirs(_ct_dir)

    if not os.path.exists(_ct_exe) and not os.path.exists(os.path.join(_ct_dir, "CoreTemp64.exe")):
        print("\n[INIT] ⚠️ Core Temp não encontrado. Baixando motor térmico...")
        url = "https://www.alcpu.com/CoreTemp/CoreTemp64.zip"
        zip_path = os.path.join(_ct_dir, "coretemp.zip")
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                out_file.write(response.read())
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(_ct_dir)
                
            os.remove(zip_path)
            print("[INIT] ✅ Core Temp baixado e extraído com sucesso!")
        except Exception as e:
            print(f"[INIT] ❌ Erro ao baixar o Core Temp: {e}")
            return False

    if os.path.exists(os.path.join(_ct_dir, "CoreTemp64.exe")):
        _ct_exe = os.path.join(_ct_dir, "CoreTemp64.exe")
    elif os.path.exists(os.path.join(_ct_dir, "Core Temp.exe")):
        _ct_exe = os.path.join(_ct_dir, "Core Temp.exe")

    ini_content = """[Advanced]
BusClk=0;
ShowDTJ=0;
SnmpSharedMemory=1;

[Display]
CloseToSystray=0;
Fahr=0;
HideTaskbarButton=1;
LabelColor=FF000000;
Minimized=1;
StatusColor=0000C0FF,000000FF;
TextColor=FF000000;

[General]
AutoUpdateCheck=0;
EnLog=0;
LogInt=10;
Plugins=1;
ReadInt=1000;
SingleInstance=1;

[Misc]
AlwaysOnTop=0;
MiniMode=0;
TjMaxOffset=0;
Version=0;

[System tray]
SystrayDisplayEffectiveFrequency=0;
SystrayDisplayFrequency=0;
SystrayDisplayLoad=0;
SystrayDisplayPower=0;
SystrayDisplayRam=0;
SystrayOption=0;
SystrayTransparentBack=1;

[UI]
DarkMode=1;
"""
    try:
        with open(_ct_ini, "w") as f:
            f.write(ini_content)
    except: pass
    
    return True

def ensure_coretemp_running():
    for proc in psutil.process_iter(['name']):
        try:
            if "core temp" in proc.info['name'].lower() or "coretemp" in proc.info['name'].lower():
                return True
        except: pass
        
    if os.path.exists(_ct_exe):
        log(f"[CORETEMP] 🚀 Iniciando o Motor: {_ct_exe}")
        try:
            subprocess.Popen([_ct_exe], cwd=_ct_dir)
            time.sleep(3) 
            return True
        except Exception as e:
            log(f"[CORETEMP] ❌ ERRO ao disparar executável: {e}")
    return False

def terminate_coretemp():
    for proc in psutil.process_iter(['name']):
        try:
            if "core temp" in proc.info['name'].lower() or "coretemp" in proc.info['name'].lower():
                proc.kill()
        except: pass

ensure_coretemp()
ensure_coretemp_running()

# =====================================================================
# AUDITORIA E LOG (EXCEL/CSV)
# =====================================================================
def log_telemetry(speed, temp, load):
    csv_path = os.path.join(_base, "relatorio_oct.csv")
    write_header = not os.path.exists(csv_path)

    if speed >= 1000 and temp < 75:
        cond, sit, act = "VERDE", "Operação Saudável", "Nenhuma ação. Fluxo normal."
    elif speed < 1000 and temp < 75:
        cond, sit, act = "AMARELO", "Gargalo Físico de Rede", "Máquina fria. Pressionar/Verificar cabo azul."
    elif speed >= 1000 and temp >= 75:
        cond, sit, act = "LARANJA", "Risco Térmico", "Concluir exame. Avaliar ar condicionado."
    else:
        cond, sit, act = "VERMELHO", "Colapso Térmico e de Tráfego", "Interromper exames. Desligar equipamento."

    try:
        with open(csv_path, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            if write_header:
                writer.writerow(["Data", "Hora", "Temp. Max (C)", "Velocidade (Mbps)", "Uso CPU (%)", "Condicao", "Situacao", "Acao Recomendada"])
            
            now = datetime.now()
            writer.writerow([now.strftime("%d/%m/%Y"), now.strftime("%H:%M:%S"), int(temp), int(speed), f"{int(load)}%", cond, sit, act])
    except Exception as e:
        log(f"Falha ao escrever CSV: {e}")

# =====================================================================
# CONSTANTES E CONFIGURAÇÕES
# =====================================================================
CONFIG_FILE = "config.json"
MEDIA_DIR = r"C:\Windows\Media"

DEFAULT_CONFIG = {
    "interface": "",
    "sensor": "Core Temp (Win32 API)",
    "sound_file": "Windows Battery Critical.wav",
    "reconnect_sound": "Windows Hardware Insert.wav",
    "silent_mode": False,
    "engine_mode": "Nativo",
    "pos_mode": "Âncora Inteligente", 
    "anchor_target": "Bandeja do Sistema (Systray)", 
    "anchor_side": "À Esquerda", 
    "offset_x": 0,
    "offset_y": 0,
    "origin_x": "Esquerda",
    "origin_y": "Topo",
    "abs_x": 0,
    "abs_y": 0,
    "saved_positions": {},
    "c_bg_norm": "#0f2042", "c_bd_norm": "#00cc44", "c_tx_norm": "white",
    "c_bg_warn": "#0f2042", "c_bd_warn": "#ffcc00", "c_tx_warn": "white",
    "c_bg_crit": "#cc0000", "c_bd_crit": "#ff3333", "c_tx_crit": "white",
    "c_bg_disc": "#0f2042",  
    "c_bd_disc": "#888888"   
}

def load_config():
    log("Carregando arquivo de configuração...")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            log(f"Erro ao ler config.json: {e}. Usando padrão.")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        log("Configuração salva com sucesso.")
    except Exception as e:
        log(f"Erro ao salvar configuração: {e}")

def get_network_interfaces():
    try: return list(psutil.net_if_stats().keys())
    except: return []

def get_temp_sensors():
    return ["Core Temp (Win32 API)"]

def get_available_sounds():
    if os.path.exists(MEDIA_DIR):
        return [f for f in os.listdir(MEDIA_DIR) if f.lower().endswith(".wav")]
    return []

# =====================================================================
# LEITURA TÉRMICA DIRETA DA MEMÓRIA DO WINDOWS (COM PROTEÇÃO 64-BITS)
# =====================================================================
def get_current_status(config):
    speed = 0 
    if config["interface"]:
        try:
            stats = psutil.net_if_stats()
            if config["interface"] in stats and stats[config["interface"]].isup:
                speed = stats[config["interface"]].speed
        except Exception as e:
            log(f"Erro ao ler velocidade de rede: {e}")

    temp = 0
    load = 0
    
    try:
        # A CURA DO SEGFAULT: Ensinando o Python a ler endereços de 64-bits
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenFileMappingW.restype = ctypes.c_void_p
        kernel32.MapViewOfFile.restype = ctypes.c_void_p
        kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        FILE_MAP_READ = 4
        map_name = None
        hMap = 0
        
        # Testando todos os mapeamentos oficiais do Core Temp
        for name in ["CoreTempMappingObjectEx", "Global\\CoreTempMappingObjectEx", "CoreTempMappingObject", "Global\\CoreTempMappingObject"]:
            hMap = kernel32.OpenFileMappingW(FILE_MAP_READ, False, name)
            if hMap:
                map_name = name
                break
                
        if not hMap:
            raise Exception("Sensores não expostos na RAM (Aguardando o motor ligar...)")
            
        # Agora o pBuf volta inteiro, sem ser mutilado pelo Python!
        pBuf = kernel32.MapViewOfFile(hMap, FILE_MAP_READ, 0, 0, 0)
        
        if not pBuf:
            kernel32.CloseHandle(hMap)
            raise Exception("Falha ao ler o bloco de memória.")
            
        data = CoreTempSharedDataEx.from_address(pBuf)
        core_count = data.uiCoreCnt
        
        if core_count > 0:
            temps = [data.fTemp[i] for i in range(core_count)]
            loads = [data.uiLoad[i] for i in range(core_count)]
            temp = max(temps)
            load = max(loads)
            
            print(f"\n--- [RAIO-X RAM NATIVO] ---")
            print(f"-> Mapa Localizado: {map_name}")
            print(f"-> CPU: {data.sCPUName.decode('utf-8', errors='ignore').strip()}")
            print(f"-> Núcleos: {core_count} | Temp Max: {temp:.1f}°C | Uso Max: {load}%")
            print(f"---------------------------\n")
            sys.stdout.flush()
        
        kernel32.UnmapViewOfFile(pBuf)
        kernel32.CloseHandle(hMap)
            
    except Exception as e:
        # Removi o "log()" vermelho daqui para não ficar floodando a sua tela a cada 3s caso demore a conectar
        pass
        
    return speed, temp, load

def create_icon_image(temp, color_hex):
    size = 64
    img = Image.new('RGB', (size, size), color=color_hex)
    draw = ImageDraw.Draw(img)
    font_paths = ["C:\\Windows\\Fonts\\segoeuib.ttf", "C:\\Windows\\Fonts\\arialbd.ttf", "arial.ttf"]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, 38)
            break
        except:
            continue
    if not font: font = ImageFont.load_default()

    text = f"{int(temp)}"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (size - w) / 2
        y = (size - h) / 2 - bbox[1]
    except:
        x, y = 10, 8
        
    text_color = "black" if color_hex in ["#ffcc00", "yellow"] else "white"
    draw.text((x, y), text, fill=text_color, font=font)
    return img.resize((32, 32), Image.Resampling.LANCZOS)

class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw() 
        self.root.title("Monitor OCT")
        
        self.is_running = True
        self.current_state_id = ""
        self.cycle_index = 0
        self.last_speed = 1000
        
        self.sim_active_until = 0
        self.sim_temp = 45
        self.sim_speed = 1000
        self.sim_load = 5
        
        self.muted_until = 0
        self.last_sound_time = 0
        self.banner_w = 320
        self.banner_h = 36 
        
        self.first_run = True
        
        self.root.update_idletasks() 
        self.root.overrideredirect(True)
        
        self.config = load_config()
        interfaces = get_network_interfaces()
        if not self.config["interface"] and interfaces:
            self.config["interface"] = interfaces[0]
            save_config(self.config)

        hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
        if hwnd_tb:
            tb_rect = win32gui.GetWindowRect(hwnd_tb)
            self.banner_h = tb_rect[3] - tb_rect[1]

        try:
            self.hwnd = self.root.winfo_id()
            style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            
            if self.config.get("engine_mode", "Nativo") == "Nativo":
                if hwnd_tb:
                    WS_EX_LAYERED = 0x00080000
                    WS_EX_TRANSPARENT = 0x00000020
                    style |= win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT
                    win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, style)
                    win32gui.SetLayeredWindowAttributes(self.hwnd, 0, 255, win32con.LWA_ALPHA)
                    
                    try:
                        set_window_long = ctypes.windll.user32.SetWindowLongPtrW
                    except AttributeError:
                        set_window_long = ctypes.windll.user32.SetWindowLongW
                    set_window_long(self.hwnd, -8, hwnd_tb) 
                    self.use_legacy = False
                    log("[INIT] Motor Nativo ativado com sucesso.")
                else:
                    raise Exception("Barra de tarefas não encontrada.")
            else:
                raise Exception("Modo Legado forçado nas opções.")
                
        except Exception as e:
            log(f"[INIT] Fallback para Motor Legado ativado: {e}")
            self.use_legacy = True
            try:
                style |= win32con.WS_EX_TOOLWINDOW
                win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, style)
            except: pass

        self.banner_frame = tk.Frame(self.root, bd=2, relief="flat")
        self.banner_frame.pack(fill="both", expand=True)
        
        self.canvas_width = 316
        self.canvas = tk.Canvas(self.banner_frame, width=self.canvas_width, height=self.banner_h, bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.font = ("Segoe UI", 11, "bold")
        self.text_id = self.canvas.create_text(self.canvas_width/2, self.banner_h/2, text="Aguardando Bandeja...", font=self.font, fill="white", anchor="center")
        
        self.needs_scroll = False
        self.scroll_x = 0
        self.text_width = 0
        
        self.icon_ready = False
        
        def setup_tray_icon():
            self.icon = pystray.Icon("MonitorOCT", create_icon_image(0, self.config.get("c_bd_norm", "#00cc44")), "Monitor OCT", menu=self.create_menu())
            self.icon_ready = True
            self.icon.run()

        threading.Thread(target=setup_tray_icon, daemon=True).start()
        
        self.wait_for_icon()
        self.root.mainloop()

    def wait_for_icon(self):
        if not self.icon_ready:
            self.root.after(100, self.wait_for_icon)
        else:
            log("Ícone do Pystray iniciado. Iniciando loop visual.")
            self.root.after(500, self.start_visuals)

    def start_visuals(self):
        self.update_loop()
        self.animate_marquee()

    def get_absolute_target_position(self, verbose=False):
        hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
        if not hwnd_tb: 
            return 0, 0
            
        tb_rect = win32gui.GetWindowRect(hwnd_tb)
        mode = self.config.get("pos_mode", "Âncora Inteligente")
        
        if mode == "Pixels Personalizados":
            abs_x = self.config.get("abs_x", 0)
            abs_y = self.config.get("abs_y", 0)
            orig_x = self.config.get("origin_x", "Esquerda")
            orig_y = self.config.get("origin_y", "Topo")
            
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            final_x = abs_x if orig_x == "Esquerda" else screen_w - abs_x - self.banner_w
            final_y = abs_y if orig_y == "Topo" else screen_h - abs_y - self.banner_h
            
            if not self.use_legacy:
                final_y = 0 
            return final_x, final_y
            
        target_name = self.config.get("anchor_target", "Bandeja do Sistema (Systray)")
        side = self.config.get("anchor_side", "À Esquerda")
        off_x = self.config.get("offset_x", 0)
        off_y = self.config.get("offset_y", 0)
        
        target_rect = tb_rect
        if target_name == "Bandeja do Sistema (Systray)":
            hwnd_t = win32gui.FindWindowEx(hwnd_tb, 0, "TrayNotifyWnd", None)
            if hwnd_t: target_rect = win32gui.GetWindowRect(hwnd_t)
        elif target_name == "Relógio":
            hwnd_t = win32gui.FindWindowEx(hwnd_tb, 0, "TrayNotifyWnd", None)
            if hwnd_t:
                hwnd_c = win32gui.FindWindowEx(hwnd_t, 0, "TrayClockWClass", None)
                if hwnd_c: target_rect = win32gui.GetWindowRect(hwnd_c)
        elif target_name == "Botão Iniciar":
            target_rect = (tb_rect[0], tb_rect[1], tb_rect[0]+50, tb_rect[3])
        elif target_name == "Barra de Tarefas (Centro)":
            target_rect = (tb_rect[0], tb_rect[1], tb_rect[2], tb_rect[3])
                
        L, T, R, B = target_rect
        tgt_w = R - L
        tgt_h = B - T
        
        base_x, base_y = 0, 0
        
        if target_name == "Barra de Tarefas (Centro)":
            base_x = L + (tgt_w - self.banner_w) // 2
            if side == "Acima": base_y = T - self.banner_h
            else: base_y = T + (tgt_h - self.banner_h) // 2
        else:
            if side == "À Esquerda":
                base_x = L - self.banner_w
                base_y = T + (tgt_h - self.banner_h) // 2
            elif side == "À Direita":
                base_x = R
                base_y = T + (tgt_h - self.banner_h) // 2
            elif side == "Acima":
                base_x = L + (tgt_w - self.banner_w) // 2
                base_y = T - self.banner_h
            elif side == "Sobrepor":
                base_x = L + (tgt_w - self.banner_w) // 2
                base_y = T + (tgt_h - self.banner_h) // 2

        if not self.use_legacy:
            base_y = 0
            off_y = 0 
            
        return base_x + off_x, base_y + off_y

    def apply_position(self, verbose=False, force=False):
            try:
                hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
                if hwnd_tb:
                    tb_rect = win32gui.GetWindowRect(hwnd_tb)
                    new_h = tb_rect[3] - tb_rect[1]
                    if new_h != self.banner_h and new_h > 0:
                        self.banner_h = new_h
                        self.canvas.config(height=self.banner_h)
                        self.canvas.coords(self.text_id, self.canvas_width/2, self.banner_h/2)

                abs_x, abs_y = self.get_absolute_target_position(verbose)
                
                new_geo = f"{self.banner_w}x{self.banner_h}+{abs_x}+{abs_y}"
                geo_changed = (self.root.geometry() != new_geo)
                
                if geo_changed:
                    self.root.geometry(new_geo)
                    self.root.update_idletasks() 
                    
                if not self.use_legacy:
                    if self.root.state() == "withdrawn":
                        self.root.deiconify()
                    try: 
                        win32gui.SetWindowPos(self.hwnd, 0, abs_x, 0, self.banner_w, self.banner_h, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
                    except: pass
                else:
                    if self.root.state() == "withdrawn":
                        self.root.deiconify()
                        
                    self.root.lift()
                    self.root.attributes("-topmost", True)
                    
                    if geo_changed or force or verbose:
                        try: 
                            win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, abs_x, abs_y, self.banner_w, self.banner_h, win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE)
                        except: pass
            except Exception as e:
                pass

    def create_menu(self):
        return pystray.Menu(
            pystray.MenuItem('Opções', lambda: self.root.after(0, self.open_options)),
            pystray.MenuItem('Mutar Temporariamente (5 min)', lambda: self.mute_temp()),
            pystray.MenuItem('Reiniciar', lambda: self.root.after(0, self.restart)),
            pystray.MenuItem('Encerrar', lambda: self.root.after(0, self.terminate))
        )

    def mute_temp(self):
        self.muted_until = time.time() + 300

    def restart(self):
        self.is_running = False
        print("\n[!] Reiniciando Monitor OCT...")
        try: self.icon.stop()
        except: pass
        try:
            self.root.quit()
            self.root.destroy()
        except: pass
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def terminate(self):
        self.is_running = False
        print("\n[!] Encerrando Monitor OCT e limpando processos...")
        try:
            terminate_coretemp()
        except: pass
        print("[!] Fechando console agora!")
        sys.stdout.flush()
        os._exit(0)

    def open_options(self):
        if not self.is_running: return
        options_win = tk.Toplevel(self.root)
        options_win.title("Configurações do Monitor OCT")
        options_win.geometry("640x720")
        options_win.resizable(False, False)
        options_win.attributes("-topmost", True)
        
        temp_config = self.config.copy()
        if "saved_positions" not in temp_config: temp_config["saved_positions"] = {}
        
        notebook = ttk.Notebook(options_win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # ================= ABA 1: POSICIONAMENTO =================
        tab_pos = ttk.Frame(notebook, padding=15)
        notebook.add(tab_pos, text="Ancoragem e Posição")
        
        ttk.Label(tab_pos, text="Modo de Posicionamento:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        cb_pos_mode = ttk.Combobox(tab_pos, values=["Âncora Inteligente", "Pixels Personalizados"], state="readonly", width=25)
        cb_pos_mode.grid(row=0, column=1, sticky="w", pady=5)
        cb_pos_mode.set(temp_config.get("pos_mode", "Âncora Inteligente"))
        
        frame_anchor = ttk.Frame(tab_pos)
        frame_pixels_main = ttk.Frame(tab_pos)
        
        ttk.Label(frame_anchor, text="Alvo (O que seguir):").grid(row=0, column=0, sticky="w", pady=5)
        cb_tgt = ttk.Combobox(frame_anchor, values=["Bandeja do Sistema (Systray)", "Relógio", "Botão Iniciar", "Barra de Tarefas (Centro)"], state="readonly", width=28)
        cb_tgt.grid(row=0, column=1, sticky="w", pady=5)
        cb_tgt.set(temp_config.get("anchor_target", "Bandeja do Sistema (Systray)"))
        
        ttk.Label(frame_anchor, text="Posição Relativa:").grid(row=1, column=0, sticky="w", pady=5)
        cb_side = ttk.Combobox(frame_anchor, values=["À Esquerda", "À Direita", "Acima", "Sobrepor"], state="readonly", width=28)
        cb_side.grid(row=1, column=1, sticky="w", pady=5)
        cb_side.set(temp_config.get("anchor_side", "À Esquerda"))
        
        def on_anchor_change(e):
            temp_config["anchor_target"] = cb_tgt.get()
            temp_config["anchor_side"] = cb_side.get()
            self.config.update(temp_config)
            self.apply_position(force=True)
            
        cb_tgt.bind("<<ComboboxSelected>>", on_anchor_change)
        cb_side.bind("<<ComboboxSelected>>", on_anchor_change)

        f_orig = ttk.Frame(frame_pixels_main)
        f_orig.pack(fill="x", pady=5)
        ttk.Label(f_orig, text="Origem X:").grid(row=0, column=0, sticky="w")
        cb_orig_x = ttk.Combobox(f_orig, values=["Esquerda", "Direita"], state="readonly", width=12)
        cb_orig_x.grid(row=0, column=1, padx=(5,15))
        cb_orig_x.set(temp_config.get("origin_x", "Esquerda"))
        
        ttk.Label(f_orig, text="Origem Y:").grid(row=0, column=2, sticky="w")
        cb_orig_y = ttk.Combobox(f_orig, values=["Topo", "Base"], state="readonly", width=12)
        cb_orig_y.grid(row=0, column=3, padx=5)
        cb_orig_y.set(temp_config.get("origin_y", "Topo"))
        
        f_inputs = ttk.Frame(frame_pixels_main)
        f_inputs.pack(fill="x", pady=5)
        ttk.Label(f_inputs, text="Posição X:").grid(row=0, column=0, sticky="w")
        
        var_abs_x = tk.StringVar(value=str(temp_config.get("abs_x", 0)))
        entry_x = ttk.Entry(f_inputs, textvariable=var_abs_x, width=15)
        entry_x.grid(row=0, column=1, padx=(5,15))
        
        ttk.Label(f_inputs, text="Posição Y:").grid(row=0, column=2, sticky="w")
        var_abs_y = tk.StringVar(value=str(temp_config.get("abs_y", 0)))
        entry_y = ttk.Entry(f_inputs, textvariable=var_abs_y, width=15)
        entry_y.grid(row=0, column=3, padx=5)

        def sync_pixel_inputs(*args):
            try: temp_config["abs_x"] = int(var_abs_x.get() or 0)
            except: temp_config["abs_x"] = 0
            try: temp_config["abs_y"] = int(var_abs_y.get() or 0)
            except: temp_config["abs_y"] = 0
            temp_config["origin_x"] = cb_orig_x.get()
            temp_config["origin_y"] = cb_orig_y.get()
            self.config.update(temp_config)
            self.apply_position(force=True)

        var_abs_x.trace_add("write", sync_pixel_inputs)
        var_abs_y.trace_add("write", sync_pixel_inputs)
        cb_orig_x.bind("<<ComboboxSelected>>", lambda e: sync_pixel_inputs())
        cb_orig_y.bind("<<ComboboxSelected>>", lambda e: sync_pixel_inputs())

        f_adj = ttk.LabelFrame(frame_pixels_main, text="Ajuste Fino (Move em Tempo Real)")
        f_adj.pack(fill="x", pady=10, ipadx=5, ipady=5)
        
        def move_pos(dx, dy):
            if cb_pos_mode.get() == "Pixels Personalizados":
                try: curr_x = int(var_abs_x.get() or 0)
                except: curr_x = 0
                try: curr_y = int(var_abs_y.get() or 0)
                except: curr_y = 0
                var_abs_x.set(str(curr_x + dx))
                var_abs_y.set(str(curr_y + dy))
            else:
                temp_config["offset_x"] = temp_config.get("offset_x", 0) + dx
                temp_config["offset_y"] = temp_config.get("offset_y", 0) + dy
                self.config.update(temp_config)
                self.apply_position(force=True)

        ttk.Label(f_adj, text="Eixo X:").grid(row=0, column=0, padx=5)
        ttk.Button(f_adj, text="-50", command=lambda: move_pos(-50, 0), width=4).grid(row=0, column=1, padx=2)
        ttk.Button(f_adj, text="-10", command=lambda: move_pos(-10, 0), width=4).grid(row=0, column=2, padx=2)
        ttk.Button(f_adj, text="+10", command=lambda: move_pos(10, 0), width=4).grid(row=0, column=3, padx=2)
        ttk.Button(f_adj, text="+50", command=lambda: move_pos(50, 0), width=4).grid(row=0, column=4, padx=2)
        
        ttk.Label(f_adj, text="Eixo Y:").grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(f_adj, text="-50", command=lambda: move_pos(0, -50), width=4).grid(row=1, column=1, padx=2, pady=5)
        ttk.Button(f_adj, text="-10", command=lambda: move_pos(0, -10), width=4).grid(row=1, column=2, padx=2, pady=5)
        ttk.Button(f_adj, text="+10", command=lambda: move_pos(0, 10), width=4).grid(row=1, column=3, padx=2, pady=5)
        ttk.Button(f_adj, text="+50", command=lambda: move_pos(0, 50), width=4).grid(row=1, column=4, padx=2, pady=5)

        f_presets = ttk.LabelFrame(frame_pixels_main, text="Posições Salvas (Presets)")
        f_presets.pack(fill="x", pady=5, ipadx=5, ipady=5)
        
        columns = ("nome", "modo")
        tv = ttk.Treeview(f_presets, columns=columns, show="headings", height=4)
        tv.heading("nome", text="Nome da Posição")
        tv.heading("modo", text="Modo")
        tv.column("nome", width=250)
        tv.column("modo", width=150)
        
        scrollbar = ttk.Scrollbar(f_presets, orient="vertical", command=tv.yview)
        tv.configure(yscroll=scrollbar.set)
        tv.grid(row=0, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        scrollbar.grid(row=0, column=3, sticky="ns", pady=5)
        
        def update_tv():
            for item in tv.get_children(): tv.delete(item)
            for k, v in temp_config["saved_positions"].items():
                tv.insert("", "end", iid=k, values=(k, v.get("pos_mode", "Âncora Inteligente")))
                
        update_tv()
        
        def load_preset():
            selected = tv.selection()
            if not selected: return
            name = selected[0]
            if name in temp_config["saved_positions"]:
                p = temp_config["saved_positions"][name]
                cb_pos_mode.set(p.get("pos_mode", "Âncora Inteligente"))
                temp_config["pos_mode"] = p.get("pos_mode", "Âncora Inteligente")
                temp_config["anchor_target"] = p.get("anchor_target", "Bandeja do Sistema (Systray)")
                temp_config["anchor_side"] = p.get("anchor_side", "À Esquerda")
                temp_config["origin_x"] = p.get("origin_x", "Esquerda")
                temp_config["origin_y"] = p.get("origin_y", "Topo")
                temp_config["abs_x"] = p.get("abs_x", 0)
                temp_config["abs_y"] = p.get("abs_y", 0)
                temp_config["offset_x"] = p.get("offset_x", 0)
                temp_config["offset_y"] = p.get("offset_y", 0)
                
                cb_tgt.set(temp_config["anchor_target"])
                cb_side.set(temp_config["anchor_side"])
                cb_orig_x.set(temp_config["origin_x"])
                cb_orig_y.set(temp_config["origin_y"])
                var_abs_x.set(str(temp_config["abs_x"]))
                var_abs_y.set(str(temp_config["abs_y"]))
                
                update_frames()
                self.config.update(temp_config)
                self.apply_position(verbose=True, force=True)
                
        def delete_preset():
            selected = tv.selection()
            for name in selected:
                if name in temp_config["saved_positions"]:
                    del temp_config["saved_positions"][name]
            update_tv()
            
        ttk.Button(f_presets, text="Aplicar Selecionada", command=load_preset).grid(row=1, column=0, padx=5, sticky="w")
        ttk.Button(f_presets, text="Excluir Selecionadas", command=delete_preset).grid(row=1, column=1, padx=5, sticky="w")
        
        f_save = ttk.Frame(f_presets)
        f_save.grid(row=2, column=0, columnspan=3, sticky="we", pady=10, padx=5)
        ttk.Label(f_save, text="Nome:").pack(side="left")
        new_name_var = tk.StringVar()
        ttk.Entry(f_save, textvariable=new_name_var, width=25).pack(side="left", padx=5)
        
        def save_preset():
            n = new_name_var.get().strip()
            if n:
                temp_config["saved_positions"][n] = {
                    "pos_mode": cb_pos_mode.get(),
                    "anchor_target": cb_tgt.get(), "anchor_side": cb_side.get(),
                    "origin_x": cb_orig_x.get(), "origin_y": cb_orig_y.get(),
                    "offset_x": temp_config.get("offset_x", 0), "offset_y": temp_config.get("offset_y", 0),
                    "abs_x": int(var_abs_x.get() or 0), "abs_y": int(var_abs_y.get() or 0)
                }
                update_tv()
                new_name_var.set("")
                
        ttk.Button(f_save, text="Salvar Posição Atual", command=save_preset).pack(side="left", padx=5)

        def update_frames(event=None):
            mode = cb_pos_mode.get()
            temp_config["pos_mode"] = mode
            if mode == "Âncora Inteligente":
                frame_pixels_main.grid_remove()
                frame_anchor.grid(row=1, column=0, columnspan=2, sticky="we", pady=10)
            else:
                frame_anchor.grid_remove()
                frame_pixels_main.grid(row=1, column=0, columnspan=2, sticky="we", pady=10)
            self.config.update(temp_config)
            self.apply_position(force=True)
            
        cb_pos_mode.bind("<<ComboboxSelected>>", update_frames)
        update_frames()

        ttk.Separator(tab_pos, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="we", pady=5)
        ttk.Button(tab_pos, text="✅ APLICAR POSIÇÃO (FORÇAR TESTE)", command=lambda: self.apply_position(verbose=True, force=True)).grid(row=3, column=0, columnspan=2, pady=10)

        # ================= ABA 2: DEFINIÇÕES =================
        tab_defs = ttk.Frame(notebook, padding=15)
        notebook.add(tab_defs, text="Definições Gerais")
        
        ttk.Label(tab_defs, text="Placa de Rede:").grid(row=0, column=0, sticky="w", pady=5)
        cb_net = ttk.Combobox(tab_defs, values=get_network_interfaces(), width=40, state="readonly")
        cb_net.grid(row=0, column=1, pady=5, sticky="we")
        cb_net.set(temp_config["interface"])
        
        ttk.Label(tab_defs, text="Sensor de Temp:").grid(row=1, column=0, sticky="w", pady=5)
        cb_temp = ttk.Combobox(tab_defs, values=get_temp_sensors(), width=40, state="readonly")
        cb_temp.grid(row=1, column=1, pady=5, sticky="we")
        cb_temp.set(temp_config["sensor"])
        
        ttk.Label(tab_defs, text="Som Alerta:").grid(row=2, column=0, sticky="w", pady=5)
        snd_frame = ttk.Frame(tab_defs)
        snd_frame.grid(row=2, column=1, pady=5, sticky="we")
        cb_snd = ttk.Combobox(snd_frame, values=get_available_sounds(), width=25, state="readonly")
        cb_snd.pack(side="left", fill="x", expand=True)
        cb_snd.set(temp_config["sound_file"])
        ttk.Button(snd_frame, text="Testar", command=lambda: winsound.PlaySound(os.path.join(MEDIA_DIR, cb_snd.get()), winsound.SND_FILENAME | winsound.SND_ASYNC), width=8).pack(side="right", padx=(5,0))
        
        ttk.Label(tab_defs, text="Som Reconexão:").grid(row=3, column=0, sticky="w", pady=5)
        rec_frame = ttk.Frame(tab_defs)
        rec_frame.grid(row=3, column=1, pady=5, sticky="we")
        cb_rec = ttk.Combobox(rec_frame, values=get_available_sounds(), width=25, state="readonly")
        cb_rec.pack(side="left", fill="x", expand=True)
        cb_rec.set(temp_config["reconnect_sound"])
        ttk.Button(rec_frame, text="Testar", command=lambda: winsound.PlaySound(os.path.join(MEDIA_DIR, cb_rec.get()), winsound.SND_FILENAME | winsound.SND_ASYNC), width=8).pack(side="right", padx=(5,0))
        
        chk_silent_var = tk.BooleanVar(value=temp_config["silent_mode"])
        ttk.Checkbutton(tab_defs, text="Modo Silencioso (Apenas avisos visuais)", variable=chk_silent_var).grid(row=4, column=0, columnspan=2, pady=15, sticky="w")
        
        ttk.Label(tab_defs, text="Motor Visual:").grid(row=5, column=0, sticky="w", pady=5)
        cb_engine = ttk.Combobox(tab_defs, values=["Nativo", "Legado"], width=25, state="readonly")
        cb_engine.grid(row=5, column=1, sticky="w", pady=5)
        cb_engine.set(temp_config.get("engine_mode", "Nativo"))
        ttk.Label(tab_defs, text="(Exige Reiniciar)").grid(row=5, column=1, sticky="e", pady=5)
        
        # ================= ABA 3: TESTES =================
        tab_tests = ttk.Frame(notebook, padding=15)
        notebook.add(tab_tests, text="Simulação e Testes")
        
        canvas_scroll = tk.Canvas(tab_tests, bd=0, highlightthickness=0)
        scrollbar_v = ttk.Scrollbar(tab_tests, orient="vertical", command=canvas_scroll.yview)
        scroll_frame = ttk.Frame(canvas_scroll)
        
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
        )
        canvas_scroll.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar_v.set)
        
        canvas_scroll.pack(side="left", fill="both", expand=True)
        scrollbar_v.pack(side="right", fill="y")
        
        def trigger_sim(temp, speed, duration=15):
            self.sim_temp = temp
            self.sim_speed = speed
            self.sim_active_until = time.time() + duration
            self.last_sound_time = 0  
            
        ttk.Label(scroll_frame, text="Simuladores Rápidos de Carga (Duração: 15 Segundos)", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))
        
        f_c1 = ttk.Frame(scroll_frame, padding=2)
        f_c1.pack(fill="x", pady=5)
        ttk.Label(f_c1, text="1. CAOS TOTAL: Temperatura em nível de queima de hardware e falta de rede simultânea.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c1, text="Disparar Caos Extremo (92°C + 0 Mbps)", command=lambda: trigger_sim(92, 0), width=50).pack(anchor="w", pady=2)
        
        f_c2 = ttk.Frame(scroll_frame, padding=2)
        f_c2.pack(fill="x", pady=5)
        ttk.Label(f_c2, text="2. CAOS MODERADO: Chip de rede fritando acima do limite, reduzindo tráfego para 100M.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c2, text="Disparar Caos Moderado (92°C + 100 Mbps)", command=lambda: trigger_sim(92, 100), width=50).pack(anchor="w", pady=2)
        
        f_c3 = ttk.Frame(scroll_frame, padding=2)
        f_c3.pack(fill="x", pady=5)
        ttk.Label(f_c3, text="3. TEMPERATURA CRÍTICA: Sala totalmente sem refrigeração. Risco térmico puro.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c3, text="Disparar Temp Crítica (92°C + 1000 Mbps)", command=lambda: trigger_sim(92, 1000), width=50).pack(anchor="w", pady=2)
        
        f_c4 = ttk.Frame(scroll_frame, padding=2)
        f_c4.pack(fill="x", pady=5)
        ttk.Label(f_c4, text="4. DESCONEXÃO ABSOLUTA: Rompimento total de fiação ou switch desligado na clínica.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c4, text="Disparar Queda de Rede (55°C + 0 Mbps)", command=lambda: trigger_sim(55, 0), width=50).pack(anchor="w", pady=2)
        
        f_c5 = ttk.Frame(scroll_frame, padding=2)
        f_c5.pack(fill="x", pady=5)
        ttk.Label(f_c5, text="5. ALERTA MISTO: Dilatação dos pinos por sala aquecida gerando mau contato de 100M.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c5, text="Disparar Alerta Misto (82°C + 100 Mbps)", command=lambda: trigger_sim(82, 100), width=50).pack(anchor="w", pady=2)
        
        f_c6 = ttk.Frame(scroll_frame, padding=2)
        f_c6.pack(fill="x", pady=5)
        ttk.Label(f_c6, text="6. SALA AQUECIDA: Ar condicionado desligado, mas o cabo preserva a negociação de 1G.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c6, text="Disparar Sala Aquecida (82°C + 1000 Mbps)", command=lambda: trigger_sim(82, 1000), width=50).pack(anchor="w", pady=2)
        
        f_c7 = ttk.Frame(scroll_frame, padding=2)
        f_c7.pack(fill="x", pady=5)
        ttk.Label(f_c7, text="7. REDE LIMITADA: Mau contato puramente físico/mecânico no conector. Aparelho frio.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c7, text="Disparar Rede Limitada (55°C + 100 Mbps)", command=lambda: trigger_sim(55, 100), width=50).pack(anchor="w", pady=2)
        
        f_c8 = ttk.Frame(scroll_frame, padding=2)
        f_c8.pack(fill="x", pady=5)
        ttk.Label(f_c8, text="8. SISTEMA NORMAL: Força o retorno imediato ao estado estável padrão de produção.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c8, text="Forçar Estado Normalizado (55°C + 1000 Mbps)", command=lambda: trigger_sim(55, 1000), width=50).pack(anchor="w", pady=2)
        
        ttk.Separator(scroll_frame, orient="horizontal").pack(fill="x", pady=15)
        
        ttk.Label(scroll_frame, text="Simulação Customizada Direta:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        f_cust = ttk.Frame(scroll_frame)
        f_cust.pack(fill="x", pady=5)
        
        ttk.Label(f_cust, text="Temp (°C):").grid(row=0, column=0, sticky="w", pady=2)
        sim_temp_var_sim = tk.StringVar(value="85")
        ttk.Entry(f_cust, textvariable=sim_temp_var_sim, width=15).grid(row=0, column=1, sticky="w", pady=2, padx=5)
        
        ttk.Label(f_cust, text="Rede (Mbps):").grid(row=1, column=0, sticky="w", pady=2)
        sim_net_var_sim = tk.StringVar(value="100")
        ttk.Entry(f_cust, textvariable=sim_net_var_sim, width=15).grid(row=1, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(f_cust, text="Duração (Seg):").grid(row=2, column=0, sticky="w", pady=2)
        sim_dur_var_sim = tk.StringVar(value="15")
        ttk.Entry(f_cust, textvariable=sim_dur_var_sim, width=15).grid(row=2, column=1, sticky="w", pady=2, padx=5)
        
        sim_disc_var = tk.StringVar(value="Não")
        ttk.Label(f_cust, text="Forçar Desconexão:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Combobox(f_cust, values=["Não", "Sim"], textvariable=sim_disc_var, width=12, state="readonly").grid(row=3, column=1, sticky="w", pady=2, padx=5)
        
        def run_custom():
            try:
                t = int(sim_temp_var_sim.get())
                n = 0 if sim_disc_var.get() == "Sim" else int(sim_net_var_sim.get())
                d = int(sim_dur_var_sim.get())
                trigger_sim(t, n, d)
            except: pass
        ttk.Button(scroll_frame, text="Iniciar Simulação Customizada", command=run_custom).pack(anchor="w", pady=10)

        # ================= ABA 4: CORES =================
        tab_colors = ttk.Frame(notebook, padding=15)
        notebook.add(tab_colors, text="Estilo e Cores")
        
        def pick_color(key, btn):
            initial = temp_config.get(key, "#ffffff")
            _, code = colorchooser.askcolor(initialcolor=initial)
            if code:
                temp_config[key] = code
                btn.config(bg=code)

        row = 0
        for mode, bg_k, bd_k in [("Normal", "c_bg_norm", "c_bd_norm"),
                                 ("Aviso", "c_bg_warn", "c_bd_warn"),
                                 ("Crítico", "c_bg_crit", "c_bd_crit")]:
            ttk.Label(tab_colors, text=f"Modo {mode}").grid(row=row, column=0, sticky="w", pady=5)
            b1 = tk.Button(tab_colors, text="Fundo", bg=temp_config[bg_k], fg="white", width=12)
            b1.config(command=lambda k=bg_k, btn=b1: pick_color(k, btn))
            b1.grid(row=row, column=1, padx=5, pady=5)
            
            b2 = tk.Button(tab_colors, text="Borda", bg=temp_config[bd_k], fg="white" if mode!="Aviso" else "black", width=12)
            b2.config(command=lambda k=bd_k, btn=b2: pick_color(k, btn))
            b2.grid(row=row, column=2, padx=5, pady=5)
            row += 1

        ttk.Label(tab_colors, text="Desconectado").grid(row=row, column=0, sticky="w", pady=5)
        
        b_bg_disc = tk.Button(tab_colors, text="Fundo", bg=temp_config.get("c_bg_disc", "#0f2042"), fg="white", width=12)
        b_bg_disc.config(command=lambda k="c_bg_disc", btn=b_bg_disc: pick_color(k, btn))
        b_bg_disc.grid(row=row, column=1, padx=5, pady=5)
        
        b3 = tk.Button(tab_colors, text="Borda", bg=temp_config["c_bd_disc"], fg="white", width=12)
        b3.config(command=lambda k="c_bd_disc", btn=b3: pick_color(k, btn))
        b3.grid(row=row, column=2, padx=5, pady=5)

        # ================= BOTOES GLOBAIS =================
        btn_frame = ttk.Frame(options_win)
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)
        
        def save():
            temp_config["interface"] = cb_net.get()
            temp_config["sensor"] = cb_temp.get()
            temp_config["sound_file"] = cb_snd.get()
            temp_config["reconnect_sound"] = cb_rec.get()
            temp_config["silent_mode"] = chk_silent_var.get()
            temp_config["engine_mode"] = cb_engine.get()
            
            self.config.update(temp_config)
            save_config(self.config)
            
        def save_and_close():
            save()
            options_win.destroy()
            
        def save_and_restart():
            save()
            self.restart()
            
        ttk.Button(btn_frame, text="Cancelar", command=options_win.destroy).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="Salvar", command=save_and_close).pack(side="right")
        ttk.Button(btn_frame, text="Salvar e Reiniciar", command=save_and_restart).pack(side="right", padx=(0, 5))

    def apply_text_to_canvas(self, text, bg_color, text_color):
        if not hasattr(self, "last_applied_text"):
            self.last_applied_text = ""

        self.canvas.config(bg=bg_color)
        self.canvas.itemconfig(self.text_id, text=text, fill=text_color)
        
        bbox = self.canvas.bbox(self.text_id)
        if not bbox: return
        self.text_width = bbox[2] - bbox[0]
        
        if self.text_width > self.canvas_width:
            self.needs_scroll = True
            self.canvas.itemconfig(self.text_id, anchor="w")
            
            if text != self.last_applied_text:
                self.scroll_x = 10 
                self.canvas.coords(self.text_id, self.scroll_x, 18)
                self.last_applied_text = text 
        else:
            self.needs_scroll = False
            self.canvas.itemconfig(self.text_id, anchor="center")
            self.canvas.coords(self.text_id, self.canvas_width/2, self.banner_h/2)
            self.last_applied_text = text

    def animate_marquee(self):
        if not self.is_running: return
        if self.needs_scroll:
            self.scroll_x -= 1.5 
            if self.scroll_x < -self.text_width:
                self.scroll_x = self.canvas_width
            self.canvas.coords(self.text_id, self.scroll_x, self.banner_h/2)
        self.root.after(20, self.animate_marquee)

    def update_loop(self):
            if not self.is_running: return

            try:
                ensure_coretemp_running()

                if time.time() < self.sim_active_until:
                    speed, temp, load = self.sim_speed, self.sim_temp, self.sim_load
                else:
                    speed, temp, load = get_current_status(self.config)
                    log_telemetry(speed, temp, load)
                    
                if self.last_speed == 0 and speed >= 1000:
                    now = time.time()
                    if not self.config["silent_mode"] and now > self.muted_until:
                        r_path = os.path.join(MEDIA_DIR, self.config["reconnect_sound"])
                        if os.path.exists(r_path):
                            winsound.PlaySound(r_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                self.last_speed = speed

                is_temp_crit = temp >= 88
                is_temp_warn = 76 <= temp <= 87
                is_net_down = speed == 0
                is_net_slow = 0 < speed < 1000
                
                messages = []
                bg_color = self.config.get("c_bg_norm", "#0f2042")
                border_color = self.config.get("c_bd_norm", "#00cc44")
                text_color = self.config.get("c_tx_norm", "white")
                trigger_alarm = False
                
                if is_temp_crit and is_net_down:
                    state_id = "chaos"
                    bg_color, border_color, text_color = self.config["c_bg_crit"], self.config["c_bd_crit"], self.config["c_tx_crit"]
                    messages = [f"🚨 DESCONECTADO | TEMP CRÍTICA ({temp}°C)", f"🚨 LIGUE O AR CONDICIONADO ({temp}°C)", "🚨 DESLIGUE O PC POR 2 MIN", "🚨 RISCO DE DANO AO EQUIPAMENTO"]
                    trigger_alarm = True
                    
                elif is_temp_crit and is_net_slow:
                    state_id = "chaos_slow"
                    bg_color, border_color, text_color = self.config["c_bg_crit"], self.config["c_bd_crit"], self.config["c_tx_crit"]
                    messages = [f"🚨 REDE LENTA {speed}Mb", f"🚨 TEMPERATURA CRÍTICA {temp}°C", f"🚨 LIGUE O AR CONDICIONADO ({temp}°C)", "🚨 RISCO DE DANO AO EQUIPAMENTO", "🚨 DESLIGUE O PC POR 2 MIN"]
                    trigger_alarm = True
                    
                elif is_temp_crit:
                    state_id = "temp_crit"
                    bg_color, border_color, text_color = self.config["c_bg_crit"], self.config["c_bd_crit"], self.config["c_tx_crit"]
                    messages = [f"🚨 TEMPERATURA CRÍTICA ({temp}°C)", f"🚨 REDE OK 1Gbps - LENTIDAO {temp}°C", f"🚨 LIGUE O AR CONDICIONADO ({temp}°C)", "🚨 RISCO DE DANO AO EQUIPAMENTO"]
                    trigger_alarm = True
                    
                elif is_net_down:
                    state_id = "net_down"
                    bg_color, border_color, text_color = self.config.get("c_bg_disc", "#0f2042"), self.config["c_bd_disc"], self.config["c_tx_norm"]
                    messages = [f"⚠️ CABO DESCONECTADO | {temp}°C", "⚠️ RECONECTE O CABO DE REDE", "⚠️ SE PERSISTIR REINICIE"]
                    trigger_alarm = True

                elif is_temp_warn and is_net_slow:
                    state_id = "warn_mixed"
                    bg_color, border_color, text_color = self.config["c_bg_warn"], self.config["c_bd_warn"], self.config["c_tx_warn"]
                    messages = [f"⚠️ SALA AQUECIDA {temp}°C", f"⚠️ REDE LENTA {speed}Mb", f"⚠️ LIGUE O AR CONDICIONADO {temp}°C", "⚠️ RECONECTE O CABO DE REDE", "⚠️ SE PERSISTIR REINICIE"]
                    trigger_alarm = True
                    
                elif is_temp_warn:
                    state_id = "warn_temp"
                    bg_color, border_color, text_color = self.config["c_bg_warn"], self.config["c_bd_warn"], self.config["c_tx_warn"]
                    messages = [f"⚠️ Sala aquecida ({temp}°C) | REDE OK 1 Gbps", f"⚠️ Considere ligar o ar condicionado {temp}°C", f"⚠️ O CALOR DA SALA CAUSA LENTIDÃO NOS EXAMES ({temp}°C)", f"        ⚠️ EVITE FILAS: RESFRIE A SALA DO OCT ({temp}°C)"]
                    trigger_alarm = True
                    
                elif is_net_slow:
                    state_id = "warn_net_slow"
                    bg_color, border_color, text_color = self.config["c_bg_warn"], self.config["c_bd_warn"], self.config["c_tx_warn"]
                    messages = [f"⚠️ REDE LENTA {speed}Mb | Temp OK {temp}°C", "⚠️ RECONECTE O CABO DE REDE", "⚠️ SE PERSISTIR REINICIE"]
                    trigger_alarm = True
                    
                else:
                    state_id = "normal"
                    messages = [f"SISTEMA OK | 1 Gbps | {temp:.1f}°C | CPU: {load}%"]

                if state_id != self.current_state_id:
                    self.current_state_id = state_id
                    self.cycle_index = 0
                else:
                    self.cycle_index = (self.cycle_index + 1) % len(messages)
                    
                active_msg = messages[self.cycle_index]
                
                self.banner_frame.config(bg=border_color)
                self.apply_text_to_canvas(active_msg, bg_color, text_color)
                self.icon.icon = create_icon_image(temp, border_color)
                
                if getattr(self, "first_run", False):
                    self.apply_position(verbose=True, force=True)
                    self.first_run = False
                else:
                    self.apply_position(verbose=False)
                
                now = time.time()
                if trigger_alarm and not self.config["silent_mode"] and now > self.muted_until:
                    if now - self.last_sound_time > 30:
                        s_path = os.path.join(MEDIA_DIR, self.config["sound_file"])
                        if os.path.exists(s_path): 
                            winsound.PlaySound(s_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                        else: 
                            winsound.MessageBeep(winsound.MB_ICONICONPLAYBACK)
                        self.last_sound_time = now

            except Exception as e:
                pass

            if self.is_running:
                self.root.after(3000, self.update_loop)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

if __name__ == "__main__":
    import signal
    
    if not is_admin():
        print("[!] Requisitando privilégios de Administrador...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1)
        sys.exit()

    def handle_sigint(sig, frame):
        print("\n[!] Ctrl+C detectado no console! Forçando encerramento...")
        terminate_coretemp()
        os._exit(0)
        
    signal.signal(signal.SIGINT, handle_sigint)
    
    log("=== INICIANDO SERVIÇO DE MONITORAMENTO OCT ===")
    try:
        MonitorApp()
    except KeyboardInterrupt:
        handle_sigint(None, None)
