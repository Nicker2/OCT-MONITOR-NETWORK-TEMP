# 👁️ Monitor Térmico de CPU e Velocidade de Rede 👁️

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Tkinter-4B8BBE?style=for-the-badge&logo=python&logoColor=white" alt="Tkinter" />
  <img src="https://img.shields.io/badge/.NET_Core-512BD4?style=for-the-badge&logo=dotnet&logoColor=white" alt=".NET Core" />
  <img src="https://img.shields.io/badge/PyInstaller-1F425F?style=for-the-badge&logo=python&logoColor=white" alt="PyInstaller" />
</div>

<br>

Um sistema de telemetria em tempo real projetado para monitorar a **temperatura da CPU** e a **velocidade do link de rede** em ambientes clínicos, focado especificamente no equipamento **DRI OCT Triton Plus**. 

Através de um display não-intrusivo ancorado nativamente na Barra de Tarefas do Windows, o sistema alerta operadores instantaneamente sobre degradações físicas ou térmicas que possam impactar o fluxo de atendimento aos pacientes.

<img width="499" height="41" alt="ok" src="https://github.com/user-attachments/assets/439899c7-566b-4ac0-81f6-03fce8ab19e9" />
<img width="499" height="41" alt="aquecida" src="https://github.com/user-attachments/assets/b3568bf5-74ab-4ea8-b6d8-ec818068065b" />
<img width="498" height="41" alt="reconecte" src="https://github.com/user-attachments/assets/7adfd76f-b262-4c73-bfdc-da20297cb2b0" />
<img width="498" height="41" alt="reinicie" src="https://github.com/user-attachments/assets/db12a35d-cdf1-41c7-9470-8d7d646bd696" />
<img width="499" height="41" alt="critica" src="https://github.com/user-attachments/assets/f0c4a8ca-0c14-4001-9d7d-1749e21a6a4d" />
<img width="499" height="41" alt="ligaoar" src="https://github.com/user-attachments/assets/cc45eef7-7f94-4f16-ae45-a1cc17ea34d5" />

---

## 🏥 O Problema Operacional

Na rotina oftalmológica, a dinâmica do exame depende da rapidez com que cada captura de alta resolução é transferida do OCT para o computador via cabo de rede crossover. Entre uma captura e outra, o paciente precisa ser reposicionado.

* 🟢 **Cenário Ideal (Link 1 Gbps):** Cada imagem leva em média **15 segundos** para ser transferida. O exame flui rapidamente.
* 🔴 **Cenário Crítico (Link 100 Mbps):** Devido ao superaquecimento do hardware ou mau contato (fios dilatados pelo calor da sala), a placa de rede faz um downgrade forçado. A transferência salta para **mais de 1 minuto por imagem**. Isso atrasa severamente o exame, gera filas e causa desconforto ao paciente.

## 💡 A Solução

O monitor atua como uma barreira de prevenção operando em segundo plano. Ele cruza os dados de infraestrutura física (temperatura do processador) e lógica (largura de banda Ethernet) para identificar a degradação de performance em tempo real.

Em vez de exibir logs complexos, o sistema traduz a falha em **instruções operacionais curtas e cíclicas** (Ex: *"🚨 LIGUE O AR CONDICIONADO"* ou *"⚠️ VERIFIQUE O CABO"*), permitindo que qualquer operador atue na causa raiz imediatamente.

---

## 🚀 Funcionalidades Principais

* **🎯 Holograma Nativo (Win32 API):** O banner de status não atua como uma janela solta. Ele injeta sua interface nativamente na `Shell_TrayWnd` (Bandeja do Sistema do Windows). Ele não sobrepõe os exames e não rouba o foco do mouse.

* **🔄 Exibição Estática Cíclica:** Mensagens de emergência são fatiadas em blocos curtos que rotacionam na tela. Isso garante leitura imediata pelo técnico, sem precisar esperar o texto rolar horizontalmente.

* **🧠 Auto-Bootstrap de Dependências:** O script detecta ausência de bibliotecas essenciais e conecta-se automaticamente à API do NuGet para baixar e extrair dependências (DLLs), garantindo inicialização sem erros em ambientes limpos.

* **🔥 Leitura em Nível de Kernel:** Abandona o WMI impreciso do Windows para utilizar a `LibreHardwareMonitorLib` via `pythonnet`, buscando as temperaturas reais (`Tctl`, `Core Max`) diretamente no silício da CPU.

* **🛡️ Elevação Automática (UAC):** Solicita privilégios de administrador autonomamente caso iniciado sem as devidas permissões para acesso aos sensores de hardware.

* **🕹️ Simulador de Crise Embutido:** Interface de desenvolvimento (Aba de Testes) para forçar falhas térmicas e gargalos de rede virtualmente, ideal para validar reações e treinar equipes.

---

## 📊 Matriz de Status e Diagnóstico

O algoritmo reage de forma autônoma às seguintes combinações térmicas e de rede:

| Status | Cor | Condição Física | Ação Orientada ao Operador |
| :---: | :---: | :--- | :--- |
| **Normal** | 🟢 Verde | `1 Gbps` & `Temp < 60°C` | Operação normal (~15s por imagem). |
| **Aviso** | 🟡 Amarelo | `100 Mbps` OU `Temp > 61°C` | Cabo frouxo ou sala aquecendo. Ligar refrigeração preventiva. |
| **Crítico** | 🔴 Vermelho| `Temp > 73°C` | Superaquecimento (Thermal Throttling). Risco grave de lentidão. |
| **Queda** | 🔘 Cinza | `0 Mbps` (Desconectado) | Perda de link entre OCT e PC. Checar pluge e switch. |

---

## ⚙️ Stack Tecnológica

O projeto foi construído utilizando bibliotecas nativas e pontes de interoperabilidade para máxima precisão no ecossistema Windows:

* **Python 3.x:** Lógica central e orquestração.
* **Pythonnet & clr-loader:** Ponte de comunicação permitindo que o Python execute bibliotecas C# (.NET Core).
* **LibreHardwareMonitorLib:** Biblioteca open-source em C# com acesso Ring 0 aos sensores da placa-mãe.
* **PyWin32 (`win32gui`, `win32con`):** Manipulação profunda da API do Windows para injeção de interface na barra de tarefas.
* **PSUtil:** Monitoramento em tempo real dos adaptadores de rede.
* **Tkinter & Pillow (PIL):** Renderização da interface holográfica e ícones dinâmicos do Systray.
* **Pystray:** Gerenciamento silencioso na bandeja do sistema.

---

## 🛠️ Como Executar e Compilar

### Opção 1: Executando do Código Fonte
1. **Baixe os arquivos deste repositório.**
2. **Instale o Python e as dependências via PIP:**
   ```bash
   pip install psutil pywin32 pillow pystray pythonnet clr-loader
```

3. **Inicie o monitor localmente:**
*(O script baixará a pasta `lib` via NuGet e pedirá elevação UAC automaticamente)*
```bash
   python oct-monitor-network-temp.py
```


```
### Opção 2: Compilando para um Único `.exe` (Portátil)
Para instalar na máquina da clínica sem precisar de Python instalado, você pode compilar o projeto em um executável autossuficiente que embute as DLLs baixadas.

1. **Instale o PyInstaller:**
   ```bash
   pip install pyinstaller
```

2. **Certifique-se de que a pasta `lib` foi baixada** rodando o script `.py` pelo menos uma vez.
3. **Execute o comando de compilação empacotando a pasta `lib`:**
```bash
   python -m PyInstaller --onefile --noconsole --name "MonitorOCT" --add-data "lib;lib" --uac-admin oct-monitor-network-temp.py
```


O seu executável portátil estará pronto dentro da pasta `dist/`.

---
> **Disclaimer:** Desenvolvido para otimização de infraestrutura clínica. Este software não substitui a manutenção preventiva e periódica do equipamento DRI OCT Triton Plus.
```
