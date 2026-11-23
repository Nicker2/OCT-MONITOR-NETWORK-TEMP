# 🛠️ Detalhes técnicos e manutenção

> Voltar para o [README](../README.md). Aqui fica o que interessa a quem mantém o monitor: como a temperatura é lida, como a faixa se prende à barra de tarefas, o que vai no `config.json` e no CSV, o simulador e a compilação.

## Sumário

- [Stack](#stack)
- [Core Temp: download, .ini e vigia](#core-temp-download-ini-e-vigia)
- [Leitura direta da memória do Core Temp](#leitura-direta-da-memória-do-core-temp)
- [Motores de exibição: Nativo e Legado](#motores-de-exibição-nativo-e-legado)
- [Regras dos estados](#regras-dos-estados)
- [config.json](#configjson)
- [Relatório CSV](#relatório-csv)
- [Simulador de falhas](#simulador-de-falhas)
- [Administrador (UAC)](#administrador-uac)
- [Compilação com PyInstaller](#compilação-com-pyinstaller)
- [Capturas da faixa real](#capturas-da-faixa-real)
- [Arquivos do repositório](#arquivos-do-repositório)

---

## Stack

| Peça | Papel |
| :--- | :--- |
| **Python 3** | Lógica e orquestração (`oct-monitor-cpu-network-temp.py`, arquivo único). |
| **Core Temp** | Motor térmico em segundo plano que lê os registradores de temperatura da CPU (Intel/AMD) e publica os valores em memória compartilhada. |
| **`ctypes` + `kernel32`** | `OpenFileMappingW` / `MapViewOfFile` para ler essa memória, com ponteiros de 64 bits. |
| **pywin32** (`win32gui`, `win32con`, `win32api`) | Acha a barra de tarefas (`Shell_TrayWnd`), a bandeja (`TrayNotifyWnd`) e o relógio (`TrayClockWClass`) e posiciona a faixa. |
| **psutil** | Velocidade negociada da placa de rede (`net_if_stats`) e vigia do processo do Core Temp. |
| **Tkinter + Pillow** | Faixa (canvas com texto rolante) e ícone da bandeja desenhado com a temperatura. |
| **pystray** | Ícone e menu da bandeja. |
| **winsound** | Sons `.wav` de `C:\Windows\Media`. |

---

## Core Temp: download, .ini e vigia

- `ensure_coretemp()` cria `lib_coretemp\` na pasta do programa (`pasta_do_programa()`: a do script ou, no `.exe`, a do executável). Se não houver `Core Temp.exe` nem `CoreTemp64.exe`, baixa `https://www.alcpu.com/CoreTemp/CoreTemp64.zip`, extrai e apaga o zip.
- Sempre regrava o `CoreTemp.ini` com a janela minimizada, sem botão na barra de tarefas, sem checagem de atualização, sem log, **memória compartilhada ligada** (`SnmpSharedMemory=1`), leitura a cada 1000 ms e instância única.
- `ensure_coretemp_running()` roda a cada ciclo: se não houver processo com "core temp"/"coretemp" no nome, abre o executável de novo.
- **Encerrar** (menu da bandeja) ou **Ctrl+C** no console encerram o Core Temp com `taskkill /f`.

---

## Leitura direta da memória do Core Temp

A estrutura `CoreTempSharedDataEx` (em `ctypes`) espelha o bloco publicado pelo Core Temp: carga por núcleo, TjMax, número de núcleos e CPUs, temperatura por núcleo, VID, frequência, nome da CPU, flags e TDP/potência.

A cada ciclo o monitor:

1. Configura `restype`/`argtypes` de `OpenFileMappingW`, `MapViewOfFile`, `UnmapViewOfFile` e `CloseHandle` para 64 bits (sem isso o Python trunca o ponteiro e o processo cai).
2. Tenta, nesta ordem, os mapeamentos `CoreTempMappingObjectEx`, `Global\CoreTempMappingObjectEx`, `CoreTempMappingObject` e `Global\CoreTempMappingObject`.
3. Lê `uiCoreCnt` e usa **a maior** temperatura e **a maior** carga entre os núcleos.
4. Imprime um "raio-x" no console (mapa usado, CPU, núcleos, temperatura e uso) e libera a memória.

Se o mapeamento não existir (Core Temp ainda abrindo ou sem permissão), a temperatura fica `0` naquele ciclo.

---

## Motores de exibição: Nativo e Legado

| Motor | Como funciona | Quando usar |
| :--- | :--- | :--- |
| **Nativo** (padrão) | A janela recebe `WS_EX_TOOLWINDOW`, `WS_EX_NOACTIVATE`, `WS_EX_LAYERED` e `WS_EX_TRANSPARENT` e passa a ter a barra de tarefas como dona (`SetWindowLongPtrW(..., -8, Shell_TrayWnd)`). Não pega foco, não aparece no Alt+Tab e o clique atravessa. A posição vertical é sempre o topo da barra. | Uso normal. |
| **Legado** | Janela comum sem borda, `WS_EX_TOOLWINDOW` e sempre por cima (`HWND_TOPMOST`). Aceita deslocamento vertical. | Se a barra de tarefas não for encontrada ou a faixa não aparecer no modo Nativo. |

A altura da faixa acompanha a altura da barra de tarefas (verificada a cada ciclo). A largura é fixa em 320 px; texto maior que a faixa rola da direita para a esquerda.

**Posicionamento:**

- **Âncora Inteligente:** alvo `Bandeja do Sistema (Systray)`, `Relógio`, `Botão Iniciar` ou `Barra de Tarefas (Centro)`; lado `À Esquerda`, `À Direita`, `Acima` ou `Sobrepor`; mais `offset_x`/`offset_y`.
- **Pixels Personalizados:** `abs_x`/`abs_y` a partir da origem escolhida (`Esquerda`/`Direita`, `Topo`/`Base`).
- **Presets:** cada posição salva guarda modo, alvo, lado, origens, offsets e coordenadas.

---

## Regras dos estados

Verificação a cada 3 s (`update_loop`), na ordem abaixo (a primeira que bate vence):

| `state_id` | Condição | Cores | Som |
| :--- | :--- | :--- | :---: |
| `chaos` | temp ≥ 88 e velocidade = 0 | crítico | sim |
| `chaos_slow` | temp ≥ 88 e 0 < velocidade < 1000 | crítico | sim |
| `temp_crit` | temp ≥ 88 | crítico | sim |
| `net_down` | velocidade = 0 | desconectado | sim |
| `warn_mixed` | 76 ≤ temp < 88 e 0 < velocidade < 1000 | aviso | sim |
| `warn_temp` | 76 ≤ temp < 88 | aviso | sim |
| `warn_net_slow` | 0 < velocidade < 1000 | aviso | sim |
| `normal` | qualquer outro caso | normal | não |

- As faixas vêm de `classificar_temperatura()` com as constantes `TEMP_AVISO_C = 76.0` e `TEMP_CRITICA_C = 88.0`. As comparações são contínuas (`>=`/`<`), então não há buraco entre aviso e crítico (antes da v1.1, 87,5 °C caía em "normal").
- Cada estado tem uma lista de mensagens; a cada ciclo passa para a próxima. Ao mudar de estado, volta para a primeira.
- O som de alerta toca no máximo uma vez a cada 30 s, se o modo silencioso estiver desligado e fora do "Mutar 5 min". Se o arquivo de som não existir, toca o bipe padrão.
- O som de reconexão toca quando a velocidade passa de 0 para 1000 Mbps ou mais.

---

## config.json

Gravado na pasta de trabalho atual (de onde o monitor foi aberto). Está no `.gitignore`.

| Chave | Padrão | O que faz |
| :--- | :--- | :--- |
| `interface` | primeira placa encontrada | Nome da placa de rede monitorada. |
| `sensor` | `Core Temp (Win32 API)` | Único sensor disponível hoje. |
| `sound_file` | `Windows Battery Critical.wav` | Som de alerta (de `C:\Windows\Media`). |
| `reconnect_sound` | `Windows Hardware Insert.wav` | Som quando o cabo volta. |
| `silent_mode` | `false` | Só avisos visuais. |
| `engine_mode` | `Nativo` | `Nativo` ou `Legado`. |
| `pos_mode` | `Âncora Inteligente` | Ou `Pixels Personalizados`. |
| `anchor_target` | `Bandeja do Sistema (Systray)` | Alvo da âncora. |
| `anchor_side` | `À Esquerda` | Lado da âncora. |
| `offset_x`, `offset_y` | `0` | Ajuste fino da âncora. |
| `origin_x`, `origin_y` | `Esquerda`, `Topo` | Origem dos pixels personalizados. |
| `abs_x`, `abs_y` | `0` | Posição em pixels. |
| `saved_positions` | `{}` | Posições salvas por nome. |
| `c_bg_norm`, `c_bd_norm`, `c_tx_norm` | `#0f2042`, `#00cc44`, `white` | Fundo, borda e texto do estado normal. |
| `c_bg_warn`, `c_bd_warn`, `c_tx_warn` | `#0f2042`, `#ffcc00`, `white` | Aviso. |
| `c_bg_crit`, `c_bd_crit`, `c_tx_crit` | `#cc0000`, `#ff3333`, `white` | Crítico. |
| `c_bg_disc`, `c_bd_disc` | `#0f2042`, `#888888` | Desconectado. |

---

## Relatório CSV

- Arquivo: `relatorio_oct_<ano>_Sem_<semana ISO>.csv`, na pasta do programa (a do script ou, no `.exe`, a do executável), `utf-8-sig`, separador `;`.
- Colunas: `Data`, `Hora`, `Temp. Max (C)`, `Velocidade (Mbps)`, `Uso CPU (%)`, `Condicao`, `Situacao`, `Acao Recomendada`.
- Uma linha por ciclo com leitura real (simulações não são gravadas).
- A classificação do CSV é própria e usa **75 °C** como corte:

| Condição | Regra | Ação gravada |
| :--- | :--- | :--- |
| `VERDE` | ≥ 1000 Mbps e < 75 °C | Nenhuma ação. Fluxo normal. |
| `AMARELO` | < 1000 Mbps e < 75 °C | Máquina fria. Verificar o cabo. |
| `LARANJA` | ≥ 1000 Mbps e ≥ 75 °C | Concluir exame. Avaliar ar-condicionado. |
| `VERMELHO` | < 1000 Mbps e ≥ 75 °C | Interromper exames. Desligar equipamento. |

> [!NOTE]
> Desde a v1.1, no `.exe` de arquivo único a "pasta do programa" é a pasta do `MonitorOCT.exe` (`sys.executable`), e não a temporária do PyInstaller (`sys._MEIPASS`). O CSV e o `lib_coretemp\` sobrevivem ao fechamento e o Core Temp não é baixado de novo a cada abertura. O `config.json` continua na pasta de trabalho atual.

---

## Simulador de falhas

Aba **Simulação e Testes**. Cada botão força os valores por 15 s (o som é liberado na hora):

| # | Cenário | Temperatura | Rede |
| :---: | :--- | :---: | :---: |
| 1 | Caos total | 92 °C | 0 Mbps |
| 2 | Caos moderado | 92 °C | 100 Mbps |
| 3 | Temperatura crítica | 92 °C | 1000 Mbps |
| 4 | Desconexão absoluta | 55 °C | 0 Mbps |
| 5 | Alerta misto | 82 °C | 100 Mbps |
| 6 | Sala aquecida | 82 °C | 1000 Mbps |
| 7 | Rede limitada | 55 °C | 100 Mbps |
| 8 | Sistema normal | 55 °C | 1000 Mbps |

A **Simulação Customizada** aceita temperatura, velocidade, duração e "Forçar Desconexão".

---

## Administrador (UAC)

O script tem um bloco de autoelevação (`IsUserAnAdmin` + `ShellExecuteW(..., "runas", ...)`), mas ele está **comentado** no código atual para testes locais. Por isso:

- **Pelo Python:** abra o console como administrador antes de rodar.
- **Pelo `.exe`:** compile com `--uac-admin`; o Windows pede a permissão ao abrir.

---

## Compilação com PyInstaller

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name "MonitorOCT" --uac-admin oct-monitor-cpu-network-temp.py
```

Saída em `dist\MonitorOCT.exe`. Coloque o `.exe` numa pasta própria com permissão de escrita (ex.: `C:\MonitorOCT\`): o CSV e o `lib_coretemp\` são criados ali.

---

## Capturas da faixa real

Capturas tiradas do PC do OCT, publicadas no README anterior:

<img width="499" height="41" alt="Faixa: sistema OK" src="https://github.com/user-attachments/assets/439899c7-566b-4ac0-81f6-03fce8ab19e9" />
<img width="499" height="41" alt="Faixa: sala aquecida" src="https://github.com/user-attachments/assets/b3568bf5-74ab-4ea8-b6d8-ec818068065b" />
<img width="498" height="41" alt="Faixa: reconecte o cabo" src="https://github.com/user-attachments/assets/7adfd76f-b262-4c73-bfdc-da20297cb2b0" />
<img width="498" height="41" alt="Faixa: reinicie" src="https://github.com/user-attachments/assets/db12a35d-cdf1-41c7-9470-8d7d646bd696" />
<img width="499" height="41" alt="Faixa: temperatura crítica" src="https://github.com/user-attachments/assets/f0c4a8ca-0c14-4001-9d7d-1749e21a6a4d" />
<img width="499" height="41" alt="Faixa: ligue o ar" src="https://github.com/user-attachments/assets/cc45eef7-7f94-4f16-ae45-a1cc17ea34d5" />

---

## Arquivos do repositório

| Arquivo | Para que serve |
| :--- | :--- |
| `oct-monitor-cpu-network-temp.py` | O monitor inteiro. |
| `README.md`, `docs/`, `assets/` | Documentação e ilustrações. |
| `tests/test_regras.py` | Testes das faixas de temperatura e da pasta do programa (`python -m unittest discover -s tests`), sem abrir janelas nem precisar do hardware. |
| `LICENSE` | Licença MIT. |
| `.gitignore` | Ignora, entre outros, `config.json`, `build/` e `dist/`. |

Criados ao rodar (fora do Git): `config.json`, `lib_coretemp\` e `relatorio_oct_*.csv`.
