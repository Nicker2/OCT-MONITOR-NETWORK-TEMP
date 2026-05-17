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

# Importações para o Auto-Downloader
import urllib.request
import zipfile
import shutil
import ssl

# =====================================================================
# AUTO-BOOTSTRAP: BAIXADOR DE DEPENDÊNCIAS VIA NUGET
# =====================================================================
def ensure_dependencies():
    _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    _lib_dir = os.path.join(_base, "lib")
    _lhm_dll = os.path.join(_lib_dir, "LibreHardwareMonitorLib.dll")
    
    # Se a DLL já existe, segue o jogo imediatamente
    if os.path.exists(_lhm_dll):
        return _lib_dir
        
    # Se for um executável compilado (.exe) e a DLL não estiver lá, a compilação falhou
    if getattr(sys, "frozen", False):
        print("[INIT] ERRO CRÍTICO: Executável compilado sem as DLLs necessárias.")
        return _lib_dir

    print("\n[INIT] ⚠️ Dependências ausentes detectadas!")
    print("[INIT] Conectando ao NuGet para baixar os pacotes oficiais...\n")
    
    PACKAGES = [
        ("LibreHardwareMonitorLib", "0.9.4", ("lib/net8.0/LibreHardwareMonitorLib.dll",)),
        ("HidSharp", "2.1.0", ("lib/netstandard2.0/HidSharp.dll",)),
        ("System.Management", "9.0.0", ("lib/net8.0/System.Management.dll",)),
        ("System.IO.Ports", "9.0.0", ("lib/net8.0/System.IO.Ports.dll",)),
        ("Microsoft.Win32.Registry", "5.0.0", ("lib/netstandard2.0/Microsoft.Win32.Registry.dll",)),
        ("System.IO.FileSystem.AccessControl", "5.0.0", ("lib/netstandard2.0/System.IO.FileSystem.AccessControl.dll",)),
        ("Mono.Posix.NETStandard", "1.0.0", ("runtimes/win-x64/lib/netstandard2.0/Mono.Posix.NETStandard.dll",)),
    ]
    
    if not os.path.exists(_lib_dir):
        os.makedirs(_lib_dir)
        
    package_path = os.path.join(_base, "temp_pkg.nupkg")
    
    # Ignora certificados SSL problemáticos
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        for package_name, version, members in PACKAGES:
            url = f"https://www.nuget.org/api/v2/package/{package_name}/{version}"
            print(f"[INIT] Baixando pacote: {package_name} v{version}...")
            
            with urllib.request.urlopen(url, context=ctx) as response, open(package_path, 'wb') as out_file:
                out_file.write(response.read())
                
            with zipfile.ZipFile(package_path) as archive:
                for member in members:
                    target = os.path.join(_lib_dir, os.path.basename(member))
                    with open(target, "wb") as output_file:
                        output_file.write(archive.read(member))
                        
        print("\n[INIT] ✅ Download e extração concluídos com sucesso via NuGet!\n")
    except Exception as e:
        print(f"[INIT] ❌ Erro ao baixar pacotes da Microsoft: {e}")
    finally:
        if os.path.exists(package_path):
            os.remove(package_path)
            
    return _lib_dir

# =====================================================================
# INICIALIZAÇÃO DA PONTE COM O HARDWARE (LIBRE HARDWARE MONITOR)
# =====================================================================
LHM_AVAILABLE = False
_lhm_computer = None

# Garante que as dependências existem ANTES de tentar importar o C#
lib_dir_path = ensure_dependencies()

try:
    from clr_loader import get_coreclr
    import pythonnet
    pythonnet.set_runtime(get_coreclr())
    import clr

    if os.path.isdir(lib_dir_path):
        sys.path.insert(0, lib_dir_path)
        for _asm in (
            "System.Management",
            "System.IO.Ports",
            "Microsoft.Win32.Registry",
            "System.IO.FileSystem.AccessControl",
            "Mono.Posix.NETStandard",
        ):
            try: clr.AddReference(_asm)
            except: pass
            
        clr.AddReference("LibreHardwareMonitorLib")
        from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType
        
        _lhm_computer = Computer()
        _lhm_computer.IsCpuEnabled = True
        _lhm_computer.IsMotherboardEnabled = True
        _lhm_computer.Open()
        LHM_AVAILABLE = True
        print("[INIT] LibreHardwareMonitor carregado com sucesso (Modo CoreCLR).")
    else:
        print(f"[INIT] ERRO: Pasta 'lib' não encontrada em: {lib_dir_path}")
except Exception as e:
    print(f"[INIT] Aviso: LibreHardwareMonitor falhou. Erro: {e}")

# Funções auxiliares para varredura de hardware
def _walk_hardware(hw):
    yield hw
    for sub_hw in hw.SubHardware:
        yield from _walk_hardware(sub_hw)

def _collect_sensors(hw):
    sensors = []
    for node in _walk_hardware(hw):
        try: node.Update()
        except: pass
        sensors.extend(node.Sensors)
    return sensors

# =====================================================================
# CONSTANTES E CONFIGURAÇÕES
# =====================================================================
# (O SEU SCRIPT CONTINUA NORMALMENTE A PARTIR DAQUI)
CONFIG_FILE = "config.json"
MEDIA_DIR = r"C:\Windows\Media"

DEFAULT_CONFIG = {
    "interface": "",
    "sensor": "Automático - Núcleo Real (LHM)",
    "sound_file": "Windows Foreground.wav",
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

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

def load_config():
    log("Carregando arquivo de configuração...")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = {**DEFAULT_CONFIG, **json.load(f)}
                return config
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
    try:
        return list(psutil.net_if_stats().keys())
    except:
        return []

def get_temp_sensors():
    return ["Automático - Núcleo Real (LHM)"]

def get_available_sounds():
    if os.path.exists(MEDIA_DIR):
        return [f for f in os.listdir(MEDIA_DIR) if f.lower().endswith(".wav")]
    return []

def get_current_status(config):
    speed = 0 
    if config["interface"]:
        try:
            stats = psutil.net_if_stats()
            if config["interface"] in stats and stats[config["interface"]].isup:
                speed = stats[config["interface"]].speed
        except Exception as e:
            log(f"Erro ao ler velocidade de rede: {e}")

    temp = 45
    
    # === LEITURA REAL DIRETO DO HARDWARE (VARREDURA PROFUNDA) ===
    if LHM_AVAILABLE and _lhm_computer:
        try:
            all_sensors = []
            for hw in _lhm_computer.Hardware:
                all_sensors.extend(_collect_sensors(hw))
            
            ranked = []
            fallback = []
            
            # Ordem de precisão de nomes de sensores de CPU
            preferred = ("cpu package", "cpu", "package", "tctl", "tdie", "core max", "core average")
            fallback_names = ("ccd", "core")
            # Ignora componentes que não são o processador principal
            reject = ("distance to tjmax", "gpu", "hot spot", "pch", "chipset", "ambient", "motherboard", "vrm", "memory", "junction")

            for s in all_sensors:
                if s.SensorType == SensorType.Temperature and s.Value is not None:
                    lname = str(s.Name).lower()
                    
                    if any(r in lname for r in reject): 
                        continue
                    
                    for rank, pref in enumerate(preferred):
                        if pref in lname:
                            ranked.append((rank, int(s.Value)))
                            break
                    else:
                        if any(f in lname for f in fallback_names):
                            fallback.append(int(s.Value))
            
            if ranked:
                temp = min(ranked)[1]
            elif fallback:
                temp = max(fallback)

        except Exception as e:
            log(f"Erro na leitura térmica profunda LHM: {e}")
            
    if temp < 0 or temp > 120: 
        temp = 45
        
    return speed, temp

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

    text = f"{temp}"
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

        self.print_super_logs()
        
        hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
        if hwnd_tb:
            tb_rect = win32gui.GetWindowRect(hwnd_tb)
            self.banner_h = tb_rect[3] - tb_rect[1]
            log(f"Altura dinâmica da barra capturada: {self.banner_h}px")

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
                    log("Motor Nativo Ativo: Ancorado na Barra de Tarefas (Holograma).")
                else:
                    raise Exception("Barra de tarefas não encontrada.")
            else:
                raise Exception("Modo Legado forçado pelo usuário nas opções.")
                
        except Exception as e:
            log(f"Fallback para Motor Legado ativado: {e}")
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
        self.text_id = self.canvas.create_text(self.canvas_width/2, self.banner_h/2, text="Aguardando Bandeja do Sistema...", font=self.font, fill="white", anchor="center")
        
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

    def print_super_logs(self):
        log("=== SUPER LOGS DE DIAGNÓSTICO (RAIO-X) ===")
        try:
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            log(f"[RAIO-X] Resolução da Tela Principal: {screen_w}x{screen_h}")
            
            hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
            if hwnd_tb:
                rect = win32gui.GetWindowRect(hwnd_tb)
                log(f"[RAIO-X] Barra de Tarefas (Shell_TrayWnd): L:{rect[0]}, T:{rect[1]}, R:{rect[2]}, B:{rect[3]}")
                
                hwnd_tray = win32gui.FindWindowEx(hwnd_tb, 0, "TrayNotifyWnd", None)
                if hwnd_tray:
                    t_rect = win32gui.GetWindowRect(hwnd_tray)
                    log(f"[RAIO-X] Bandeja do Sistema (TrayNotifyWnd): L:{t_rect[0]}, T:{t_rect[1]}, R:{t_rect[2]}, B:{t_rect[3]}")
                    
                    hwnd_clock = win32gui.FindWindowEx(hwnd_tray, 0, "TrayClockWClass", None)
                    if hwnd_clock:
                        c_rect = win32gui.GetWindowRect(hwnd_clock)
                        log(f"[RAIO-X] Relógio (TrayClockWClass): L:{c_rect[0]}, T:{c_rect[1]}, R:{c_rect[2]}, B:{c_rect[3]}")
                    else:
                        log("[RAIO-X] Relógio (TrayClockWClass) não encontrado.")
                else:
                    log("[RAIO-X] Bandeja do Sistema (TrayNotifyWnd) não encontrada.")
            else:
                log("[RAIO-X] Barra de Tarefas (Shell_TrayWnd) não encontrada.")
        except Exception as e:
            log(f"[RAIO-X] Erro ao extrair logs: {e}")
        log("==========================================")

    def get_absolute_target_position(self, verbose=False):
        hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
        if not hwnd_tb: 
            if verbose: log("[LOG-POS] FALHA: Barra de tarefas principal (Shell_TrayWnd) não encontrada.")
            return 0, 0
            
        tb_rect = win32gui.GetWindowRect(hwnd_tb)
        mode = self.config.get("pos_mode", "Âncora Inteligente")
        
        if verbose: log(f"[LOG-POS] Calculando coordenadas absolutas. Modo selecionado: {mode}")
        
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
                if verbose: log(f"[LOG-POS] Modo Nativo: Eixo Y forçado a 0. Resultado Absoluto X: {final_x}, Y: 0")
            else:
                if verbose: log(f"[LOG-POS] Modo Pixels -> Origem X: {orig_x}, Origem Y: {orig_y}. Resultado Absoluto X: {final_x}, Y: {final_y}")
                
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
        
        if verbose: log(f"[LOG-POS] Alvo: {target_name}. Retângulo do Alvo: L:{L}, T:{T}, R:{R}, B:{B}")
        
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
            
        if verbose: log(f"[LOG-POS] Posição Relativa '{side}' aplicada com offsets (+{off_x}, +{off_y}) -> X: {base_x + off_x}, Y: {base_y + off_y}")
        return base_x + off_x, base_y + off_y

    def apply_position(self, verbose=False, force=False):
            try:
                if verbose: log("--- INICIANDO APLICAÇÃO DE POSIÇÃO ---")
                
                # 1. Checagem e Atualização da Altura (Para NATIVO e LEGADO)
                hwnd_tb = win32gui.FindWindow("Shell_TrayWnd", None)
                if hwnd_tb:
                    tb_rect = win32gui.GetWindowRect(hwnd_tb)
                    new_h = tb_rect[3] - tb_rect[1]
                    if new_h != self.banner_h and new_h > 0:
                        self.banner_h = new_h
                        self.canvas.config(height=self.banner_h)
                        self.canvas.coords(self.text_id, self.canvas_width/2, self.banner_h/2)
                        if verbose: log(f"[LOG-POS] Altura da barra atualizada para: {self.banner_h}px")

                # 2. Captura do Alvo
                abs_x, abs_y = self.get_absolute_target_position(verbose)
                
                # 3. Atualização Interna do Tkinter
                new_geo = f"{self.banner_w}x{self.banner_h}+{abs_x}+{abs_y}"
                geo_changed = (self.root.geometry() != new_geo)
                
                # Atualiza o Tkinter e FORÇA ele a registrar a posição na mesma hora
                if geo_changed:
                    self.root.geometry(new_geo)
                    self.root.update_idletasks() # Impede o Tkinter de usar cache antigo
                    
                # 4. Motor de Posicionamento Final
                if not self.use_legacy:
                    # === MODO NATIVO ===
                    if verbose: log(f"[LOG-POS] Modo Nativo. Aplicando coordenadas absolutas (Y forçado a 0) -> X:{abs_x}, Y:0")
                    
                    # O deiconify vem ANTES da marretada do Win32 para evitar pulos
                    if self.root.state() == "withdrawn":
                        self.root.deiconify()
                    
                    if verbose: log(f"[LOG-POS] Disparando SetWindowPos com X:{abs_x}, Y:0")
                    try: 
                        win32gui.SetWindowPos(self.hwnd, 0, abs_x, 0, self.banner_w, self.banner_h, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
                    except Exception as e: 
                        log(f"[LOG-POS] Erro SetWindowPos: {e}")
                    
                else:
                    # === MODO LEGADO ===
                    if verbose: log(f"[LOG-POS] Modo Legado ativo. Aplicando coordenadas absolutas -> X:{abs_x}, Y:{abs_y}")
                    
                    if self.root.state() == "withdrawn":
                        self.root.deiconify()
                        
                    self.root.lift()
                    self.root.attributes("-topmost", True)
                    
                    # No Legado, mantemos a trava do geo_changed pra não fazer a tela piscar à toa
                    if geo_changed or force or verbose:
                        try: 
                            win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, abs_x, abs_y, self.banner_w, self.banner_h, win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE)
                        except: 
                            pass
                            
                if verbose: log("----------------------------------------")
            except Exception as e:
                log(f"Erro ao aplicar posição: {e}")

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
        try: self.icon.stop()
        except: pass
        
        if _lhm_computer:
            try: _lhm_computer.Close()
            except: pass
            
        try:
            self.root.quit()
            self.root.destroy()
        except: pass
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def terminate(self):
        self.is_running = False
        try: self.icon.stop()
        except: pass
        
        if _lhm_computer:
            try: _lhm_computer.Close()
            except: pass
            
        try:
            self.root.quit()
            self.root.destroy()
        except: pass
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
        
        # --- Frame Anchor ---
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

        # --- Frame Pixels Main (Campos, Ajuste Fino, Presets) ---
        
        # Subframe: Origens
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
        
        # Subframe: Inputs Manuais
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

        # Subframe: Ajuste Fino
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

        # Subframe: Presets
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

        # Lógica de Ocultar/Mostrar
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

        # Botão Aplicar Manual (Força Log)
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
        
        # ================= ABA 3: TESTES (ORGANIZAÇÃO VERTICAL DE PRIORIDADES) =================
        tab_tests = ttk.Frame(notebook, padding=15)
        notebook.add(tab_tests, text="Simulação e Testes")
        
        # Container com rolagem para os cenários não espremerem a janela
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
        
        # CONFIGURAÇÃO DE LINHA VERTICAL EMPILHADA: EXPLICAÇÃO + BOTÃO ABAIXO
        
        # 1. Caos Extremo
        f_c1 = ttk.Frame(scroll_frame, padding=2)
        f_c1.pack(fill="x", pady=5)
        ttk.Label(f_c1, text="1. CAOS TOTAL: Temperatura em nível de queima de hardware e falta de rede simultânea.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c1, text="Disparar Caos Extremo (80°C + 0 Mbps)", command=lambda: trigger_sim(80, 0), width=50).pack(anchor="w", pady=2)
        
        # 2. Caos Moderado
        f_c2 = ttk.Frame(scroll_frame, padding=2)
        f_c2.pack(fill="x", pady=5)
        ttk.Label(f_c2, text="2. CAOS MODERADO: Chip de rede fritando acima do limite, reduzindo tráfego para 100M.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c2, text="Disparar Caos Moderado (80°C + 100 Mbps)", command=lambda: trigger_sim(80, 100), width=50).pack(anchor="w", pady=2)
        
        # 3. Temperatura Crítica Isolada
        f_c3 = ttk.Frame(scroll_frame, padding=2)
        f_c3.pack(fill="x", pady=5)
        ttk.Label(f_c3, text="3. TEMPERATURA CRÍTICA: Sala totalmente sem refrigeração. Risco térmico puro.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c3, text="Disparar Temp Crítica (80°C + 1000 Mbps)", command=lambda: trigger_sim(80, 1000), width=50).pack(anchor="w", pady=2)
        
        # 4. Queda de Conectividade Isolada
        f_c4 = ttk.Frame(scroll_frame, padding=2)
        f_c4.pack(fill="x", pady=5)
        ttk.Label(f_c4, text="4. DESCONEXÃO ABSOLUTA: Rompimento total de fiação ou switch desligado na clínica.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c4, text="Disparar Queda de Rede (45°C + 0 Mbps)", command=lambda: trigger_sim(45, 0), width=50).pack(anchor="w", pady=2)
        
        # 5. Alerta Combinado Moderado
        f_c5 = ttk.Frame(scroll_frame, padding=2)
        f_c5.pack(fill="x", pady=5)
        ttk.Label(f_c5, text="5. ALERTA MISTO: Dilatação dos pinos por sala aquecida gerando mau contato de 100M.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c5, text="Disparar Alerta Misto (65°C + 100 Mbps)", command=lambda: trigger_sim(65, 100), width=50).pack(anchor="w", pady=2)
        
        # 6. Alerta de Temperatura Isolado
        f_c6 = ttk.Frame(scroll_frame, padding=2)
        f_c6.pack(fill="x", pady=5)
        ttk.Label(f_c6, text="6. SALA AQUECIDA: Ar condicionado desligado, mas o cabo preserva a negociação de 1G.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c6, text="Disparar Sala Aquecida (65°C + 1000 Mbps)", command=lambda: trigger_sim(65, 1000), width=50).pack(anchor="w", pady=2)
        
        # 7. Alerta de Link Preso Isolado
        f_c7 = ttk.Frame(scroll_frame, padding=2)
        f_c7.pack(fill="x", pady=5)
        ttk.Label(f_c7, text="7. REDE LIMITADA: Mau contato puramente físico/mecânico no conector. Aparelho frio.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c7, text="Disparar Rede Limitada (45°C + 100 Mbps)", command=lambda: trigger_sim(45, 100), width=50).pack(anchor="w", pady=2)
        
        # 8. Reset para Normalidade
        f_c8 = ttk.Frame(scroll_frame, padding=2)
        f_c8.pack(fill="x", pady=5)
        ttk.Label(f_c8, text="8. SISTEMA NORMAL: Força o retorno imediato ao estado estável padrão de produção.", font=("Segoe UI", 8, "italic"), foreground="gray").pack(anchor="w")
        ttk.Button(f_c8, text="Forçar Estado Normalizado (45°C + 1000 Mbps)", command=lambda: trigger_sim(45, 1000), width=50).pack(anchor="w", pady=2)
        
        ttk.Separator(scroll_frame, orient="horizontal").pack(fill="x", pady=15)
        
        # Bloco Customizado Mantido no Fundo para Ajustes Finos Extras
        ttk.Label(scroll_frame, text="Simulação Customizada Direta:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        f_cust = ttk.Frame(scroll_frame)
        f_cust.pack(fill="x", pady=5)
        
        ttk.Label(f_cust, text="Temp (°C):").grid(row=0, column=0, sticky="w", pady=2)
        sim_temp_var_sim = tk.StringVar(value="75")
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
                if time.time() < self.sim_active_until:
                    speed, temp = self.sim_speed, self.sim_temp
                else:
                    speed, temp = get_current_status(self.config)
                    
                if self.last_speed == 0 and speed >= 1000:
                    now = time.time()
                    if not self.config["silent_mode"] and now > self.muted_until:
                        r_path = os.path.join(MEDIA_DIR, self.config["reconnect_sound"])
                        if os.path.exists(r_path):
                            winsound.PlaySound(r_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                self.last_speed = speed

                is_temp_crit = temp >= 73
                is_temp_warn = 61 <= temp <= 72
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
                    messages = [f"🚨 DESCONECTADO | TEMP CRÍTICA ({temp}°C)", "🚨 LIGUE O AR CONDICIONADO", "🚨 DESLIGUE O PC POR 2 MIN", "🚨 RISCO DE DANO AO EQUIPAMENTO"]
                    trigger_alarm = True
                    
                elif is_temp_crit and is_net_slow:
                    state_id = "chaos_slow"
                    bg_color, border_color, text_color = self.config["c_bg_crit"], self.config["c_bd_crit"], self.config["c_tx_crit"]
                    messages = [f"🚨 REDE LENTA {speed}Mb", f"🚨 TEMPERATURA CRÍTICA {temp}°C", "🚨 LIGUE O AR CONDICIONADO", "🚨 RISCO DE DANO AO EQUIPAMENTO", "🚨 DESLIGUE O PC POR 2 MIN"]
                    trigger_alarm = True
                    
                elif is_temp_crit:
                    state_id = "temp_crit"
                    bg_color, border_color, text_color = self.config["c_bg_crit"], self.config["c_bd_crit"], self.config["c_tx_crit"]
                    messages = [f"🚨 TEMPERATURA CRÍTICA ({temp}°C)", f"🚨 REDE OK 1Gbps - LENTIDAO NO PC ({temp}°C)", "🚨 LIGUE O AR CONDICIONADO", "🚨 RISCO DE DANO AO EQUIPAMENTO"]
                    trigger_alarm = True
                    
                elif is_net_down:
                    state_id = "net_down"
                    bg_color, border_color, text_color = self.config.get("c_bg_disc", "#0f2042"), self.config["c_bd_disc"], self.config["c_tx_norm"]
                    messages = [f"⚠️ CABO DESCONECTADO | {temp}°C", "⚠️ RECONECTE O CABO DE REDE", "⚠️ SE PERSISTIR REINICIE"]
                    trigger_alarm = True

                elif is_temp_warn and is_net_slow:
                    state_id = "warn_mixed"
                    bg_color, border_color, text_color = self.config["c_bg_warn"], self.config["c_bd_warn"], self.config["c_tx_warn"]
                    messages = [f"⚠️ SALA AQUECIDA {temp}°C", f"⚠️ REDE LENTA {speed}Mb", "⚠️ LIGUE O AR CONDICIONADO", "⚠️ RECONECTE O CABO DE REDE", "⚠️ SE PERSISTIR REINICIE"]
                    trigger_alarm = True
                    
                elif is_temp_warn:
                    state_id = "warn_temp"
                    bg_color, border_color, text_color = self.config["c_bg_warn"], self.config["c_bd_warn"], self.config["c_tx_warn"]
                    messages = [f"⚠️ Sala Aquecida ({temp}°C) | Rede OK 1 Gbps", "⚠️ Considere ligar o Ar Condicionado"]
                    trigger_alarm = True
                    
                elif is_net_slow:
                    state_id = "warn_net_slow"
                    bg_color, border_color, text_color = self.config["c_bg_warn"], self.config["c_bd_warn"], self.config["c_tx_warn"]
                    messages = [f"⚠️ REDE LENTA {speed}Mb | Temp OK {temp}°C", "⚠️ RECONECTE O CABO DE REDE", "⚠️ SE PERSISTIR REINICIE"]
                    trigger_alarm = True
                    
                else:
                    state_id = "normal"
                    messages = [f"SISTEMA OK | 1 Gbps | {temp}°C"]

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
                log(f"Erro no loop principal: {e}")

            if self.is_running:
                self.root.after(3000, self.update_loop)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

if __name__ == "__main__":
    if not is_admin():
        print("Requisitando privilégios de Administrador...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1)
        sys.exit()
        
    log("=== INICIANDO SERVIÇO DE MONITORAMENTO OCT ===")
    MonitorApp()
