# 📜 Histórico de alterações

> Voltar para o [README](../README.md). O projeto não tem números de versão; as entradas seguem as datas dos commits.

### 18/05/2026 — Core Temp no lugar do LibreHardwareMonitor

- A temperatura passa a vir do **Core Temp**, baixado sozinho em modo portátil e configurado para ficar invisível (`CoreTemp.ini` com memória compartilhada ligada).
- Leitura **direta da memória compartilhada** do Core Temp com `ctypes` e ponteiros de 64 bits, usando a maior temperatura entre os núcleos.
- Vigia que reabre o Core Temp se ele for fechado; **Encerrar** e Ctrl+C fecham o Core Temp junto.
- Relatório CSV passa a ser **um arquivo por semana** (`relatorio_oct_<ano>_Sem_<semana>.csv`, antes era um único `relatorio_oct.csv`), com condição, situação e ação recomendada.
- **Encerrar** fecha o Core Temp com `taskkill /f` (antes procurava o processo pelo nome).
- A autoelevação para administrador ao abrir pelo Python foi **comentada** para testes locais; o `.exe` compilado com `--uac-admin` continua pedindo.

### 17/05/2026 — primeira versão publicada

- Faixa presa à barra de tarefas (motor `Nativo`) com alternativa `Legado`, ícone da bandeja com a temperatura, mensagens cíclicas e texto rolante.
- Temperatura lida com o **LibreHardwareMonitor** (biblioteca .NET baixada sozinha).
- Janela de opções com ancoragem, pixels personalizados, posições salvas, sons, modo silencioso, simulador de falhas e cores.
- O arquivo foi renomeado de `oct-monitor-network-temp.py` para `oct-monitor-cpu-network-temp.py`.
