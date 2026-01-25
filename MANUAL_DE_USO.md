# 📖 Manual de Uso - CROC FPGA Aging Monitor

**Sistema de Monitoramento de Envelhecimento de FPGAs sob Radiação**

---

## 📋 Índice

1. [Requisitos](#requisitos)
2. [Instalação](#instalação)
3. [Primeiro Uso](#primeiro-uso)
4. [Executando o Experimento](#executando-o-experimento)
5. [Interface do Usuário](#interface-do-usuário)
6. [Manipulação em Tempo Real](#manipulação-em-tempo-real)
7. [Interpretando os Resultados](#interpretando-os-resultados)
8. [Conceito de DONE](#conceito-de-done)
9. [Exportação de Dados](#exportação-de-dados)
10. [Solução de Problemas](#solução-de-problemas)

---

## Requisitos

### Hardware
- FPGA Xilinx (família 7-series ou superior)
- Placa STM32 para controle de tensão
- Cabo USB para comunicação serial
- Cabo JTAG para programação da FPGA

### Software
- **Windows 10/11** ou **Linux (Ubuntu 20.04+)**
- **Python 3.10+**
- **Xilinx Vivado 2020.1+** (para programação da FPGA)
- Driver USB-Serial instalado

---

## Instalação

### Passo 1: Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/Aging-V2.git
cd Aging-V2
```

### Passo 2: Executar o Sistema

#### Windows
Basta executar o script `run.bat`:
```cmd
run.bat
```

O script automaticamente:
1. Verifica se existe um ambiente virtual (`.venv`)
2. Cria o ambiente se não existir
3. Instala as dependências do `requirements.txt`
4. Inicia a aplicação

#### Linux
Execute o script `run.sh`:
```bash
chmod +x run.sh
./run.sh
```

### Passo 3: Configuração Inicial

Na primeira execução, configure:

1. **Porta Serial**: Selecione a porta COM conectada ao STM32
2. **Vivado Path**: Aponte para o executável do Vivado
3. **Bitstream Directory**: Já configurado para `out_bitstreams/`
4. Clique em **"Save Settings"**

---

## Primeiro Uso

### Verificando a Conexão

1. Conecte o hardware (STM32 + FPGA)
2. Na aba **"Settings"**, selecione a porta serial correta
3. Clique em **"Connect"**
4. O indicador deve mudar para **"● Connected"** (verde)

### Testando a Programação

1. Na aba **"FPGA Programming"**, verifique se os bitstreams aparecem na lista
2. Selecione um bitstream (ex: `croc_aging_clkout3phase_m330.bit`)
3. Clique em **"▶ PROGRAM (SRAM)"**
4. Aguarde a mensagem de sucesso

---

## Executando o Experimento

### Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│  1. PREPARAÇÃO                                              │
│     ├─ Conectar hardware                                    │
│     ├─ Verificar conexão serial                             │
│     └─ Ir para aba "Aging Analysis"                         │
├─────────────────────────────────────────────────────────────┤
│  2. CONFIGURAÇÃO                                            │
│     ├─ Carregar bitstreams (Browse → Load)                  │
│     ├─ Configurar filtros de sensores                       │
│     ├─ Configurar radiação (dose rate + inicial)            │
│     └─ Ajustar tempos (stabilization + cooldown)            │
├─────────────────────────────────────────────────────────────┤
│  3. EXECUÇÃO                                                │
│     ├─ Marcar "Enable Auto-Program on Alarm"                │
│     ├─ Clicar "▶ Start"                                     │
│     └─ Monitorar o experimento                              │
├─────────────────────────────────────────────────────────────┤
│  4. CONCLUSÃO                                               │
│     ├─ Estado "FINISHED" ou clicar "Stop"                   │
│     ├─ Exportar dados (CSV)                                 │
│     └─ Analisar gráficos de degradação                      │
└─────────────────────────────────────────────────────────────┘
```

### Passo a Passo Detalhado

#### 1. Carregar Bitstreams

1. Clique em **"📂 Browse"**
2. Navegue até `Aging-V2/out_bitstreams/`
3. Clique em **"🔄 Load Bitstreams"**
4. Confirme que os bitstreams foram carregados (ex: 4 bitstreams, -330° a -315°)

#### 2. Configurar Filtros de Sensores

Selecione quais sensores podem disparar transições:

| Sensor | Descrição | Recomendação |
|--------|-----------|--------------|
| **F (AM)** | Sensores de amplitude modulada | ✅ Habilitado |
| **RF (LF)** | Sensores de baixa frequência | ✅ Habilitado |
| **UART** | Sensores UART | ✅ Habilitado |
| **OBI** | Sensores OBI Demux | ✅ Habilitado |

> 💡 **Dica**: Se um sensor específico estiver causando muitas transições e você quiser observar outros, desabilite-o temporariamente.

#### 3. Configurar Radiação

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| **Dose Rate** | Taxa de radiação da fonte | `0.300 krad/h` |
| **Initial Dose** | Dose já acumulada | `0.00 krad` |

#### 4. Configurar Tempos

| Parâmetro | Descrição | Valor Padrão |
|-----------|-----------|--------------|
| **Stabilization** | Espera após alarme | `3000 ms` |
| **Cooldown** | Espera após reprogram | `10000 ms` |

#### 5. Iniciar Experimento

1. ✅ Marque **"🔄 Enable Auto-Program on Alarm"**
2. Clique em **"▶ Start"**
3. O sistema irá:
   - Programar o primeiro bitstream (se necessário)
   - Iniciar monitoramento de alarmes
   - Transicionar automaticamente quando detectar alarmes

---

## Interface do Usuário

### Aba "Sensors & Control"

```
┌─────────────────────────────────────────────────────────────┐
│  SENSOR VISUALIZATION                                       │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │  F Sensors  │ RF Sensors  │UART Sensors │ OBI Sensors │  │
│  │  [32 bits]  │  [32 bits]  │  [32 bits]  │  [32 bits]  │  │
│  │  ██░░██░░   │  ░░░░░░░░   │  ░░░░░░░░   │  ░░░░░░░░   │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
│                                                             │
│  ██ = Alarme ativo    ░░ = Normal                          │
└─────────────────────────────────────────────────────────────┘
```

### Aba "Aging Analysis"

```
┌─────────────────────────┬───────────────────────────────────┐
│  BITSTREAM QUEUE        │  TRANSITION HISTORY               │
│  ┌───────────────────┐  │  ┌─────────────────────────────┐  │
│  │ 1. m330 (-330°)   │  │  │ Time | Dose | Phase Change │  │
│  │ 2. m325 (-325°) ← │  │  │ 12:30| 0.45 | -330→-325    │  │
│  │ 3. m320 (-320°)   │  │  │ 12:45| 0.52 | -325→-320    │  │
│  └───────────────────┘  │  └─────────────────────────────┘  │
│                         │                                   │
│  SENSOR FILTERS         │  GRAPHS                           │
│  ☑ F  ☑ RF              │  [Slack vs Dose] [Slack vs Time]  │
│  ☑ UART  ☑ OBI          │  ┌─────────────────────────────┐  │
│                         │  │     ●                       │  │
│  RADIATION              │  │   ●  ────────────           │  │
│  Rate: 0.3 krad/h       │  │ ●─────────────···(projeção) │  │
│  Current: 1.25 krad     │  └─────────────────────────────┘  │
│                         │                                   │
│  CONTROL                │  Rate: 0.023 ns/krad | R²=0.98   │
│  State: RUNNING         │                                   │
│  [Start] [Stop] [Skip]  │                                   │
└─────────────────────────┴───────────────────────────────────┘
```

### Significado dos Estados

| Estado | Cor | Significado |
|--------|-----|-------------|
| **IDLE** | ⚫ Cinza | Experimento não iniciado |
| **PROGRAMMING_INITIAL** | 🔵 Azul | Programando primeiro bitstream |
| **RUNNING** | 🟢 Verde | Monitorando alarmes ativamente |
| **ALARM_DETECTED** | 🟡 Amarelo | Alarme detectado, aguardando estabilização |
| **REPROGRAMMING** | 🔵 Azul | Reprogramando FPGA |
| **COOLDOWN** | ⚫ Cinza | Aguardando após reprogramação |
| **FINISHED** | 🟣 Roxo | Fim da fila de bitstreams |

---

## Manipulação em Tempo Real

### Ações Disponíveis Durante o Experimento

| Ação | Como Fazer | Efeito |
|------|------------|--------|
| **Pausar/Retomar** | Botão Stop/Start | Interrompe monitoramento |
| **Pular Bitstream** | Botão "⏭ Skip" | Avança para próximo sem alarme |
| **Filtrar Sensores** | Checkboxes | Habilita/desabilita triggers |
| **Ajustar Tempos** | Spinboxes | Modifica stabilization/cooldown |

### Modificando Filtros de Sensores

Você pode **habilitar/desabilitar sensores a qualquer momento**:

1. Desmarque o sensor que não quer como trigger
2. A mudança é **imediata**
3. O sensor continua sendo **monitorado**, apenas não causa transições

**Caso de uso típico:**
> Os sensores F estão causando muitas transições. Você quer ver quando RF ou UART disparam.
> → Desabilite F, mantenha os outros habilitados.

---

## Interpretando os Resultados

### Histórico de Transições

Cada linha representa uma transição:

| Coluna | Significado |
|--------|-------------|
| **Time** | Horário da transição |
| **Hours** | Tempo de experimento |
| **Dose** | Dose de radiação acumulada |
| **From → To** | Bitstream anterior → novo |
| **Phase** | Fase anterior → nova (graus) |
| **Triggers** | Sensores que dispararam (F:2, RF:1) |
| **Alarms** | Total de alarmes ativos |

### Gráficos de Degradação

#### Slack vs Dose
- **Eixo X**: Dose de radiação (krad)
- **Eixo Y**: Slack temporal (ns)
- **Interpretação**: Quanto mais inclinada a curva, mais rápida a degradação

#### Slack vs Time
- **Eixo X**: Tempo de experimento (horas)
- **Eixo Y**: Slack temporal (ns)
- **Interpretação**: Taxa de degradação temporal

#### Elementos do Gráfico
- **Pontos coloridos**: Medições reais
- **Linha amarela contínua**: Regressão linear
- **Linha laranja tracejada**: Projeção futura

#### Informações de Regressão
```
Slack degradation rate: 0.0234 ns/krad | R² = 0.9856
```
- **Rate**: Taxa de degradação
- **R²**: Qualidade do ajuste (1.0 = perfeito)

---

## Conceito de DONE

### Quando o Experimento Termina?

O experimento é considerado **DONE** quando:

1. **Fim da Fila**: Todos os bitstreams foram utilizados
   - Estado muda para **FINISHED** (roxo)
   - Mensagem: "Experiment completed!"

2. **Parada Manual**: Usuário clica em **"⏹ Stop"**
   - Dados são salvos automaticamente
   - Pode ser retomado posteriormente

3. **Erro Fatal**: Falha de hardware ou comunicação
   - Dados parciais são preservados

### O que Acontece ao Terminar?

```
┌─────────────────────────────────────────────┐
│  🏁 EXPERIMENT FINISHED                     │
│                                             │
│  Total transitions: 4                       │
│  Duration: 12.45 hours                      │
│  Final dose: 3.74 krad                      │
│                                             │
│  [OK]                                       │
└─────────────────────────────────────────────┘
```

### Dados Salvos Automaticamente

| Arquivo | Conteúdo |
|---------|----------|
| `experiment_transitions.json` | Todas as transições com detalhes |
| `experiment_logs/*.csv` | Logs de sensores (SmartLogger) |
| `experiment_logs/*.json` | Eventos do experimento |

---

## Exportação de Dados

### Exportar Transições

1. Na aba "Aging Analysis", clique em **"📁 Export CSV"**
2. Escolha o local e nome do arquivo
3. O CSV contém todas as colunas do histórico

### Formato do CSV Exportado

```csv
timestamp,experiment_hours,radiation_dose_krad,from_bitstream,from_phase,to_bitstream,to_phase,total_alarms,trigger_f,trigger_rf,trigger_uart,trigger_obi,fpga_temp,vccint
2026-01-24T12:30:15,1.5,0.45,m330.bit,-330,m325.bit,-325,3,[0,14,28],[],[],[],45.2,0.852
```

### Salvamento Automático

O sistema salva automaticamente:
- A cada transição
- Ao parar o experimento
- Ao fechar a aplicação

---

## Solução de Problemas

### "Não consigo conectar na porta serial"
1. Verifique se o driver USB está instalado
2. Verifique se a porta está correta
3. Tente desconectar e reconectar o cabo

### "Bitstreams não aparecem na lista"
1. Verifique se a pasta `out_bitstreams/` contém arquivos `.bit`
2. Clique em "🔄 Load Bitstreams" novamente
3. Verifique o log para mensagens de erro

### "Programação da FPGA falha"
1. Verifique se o Vivado path está correto
2. Verifique se o cabo JTAG está conectado
3. Verifique se a FPGA está energizada

### "Sistema troca de bitstream muito rápido"
1. Aumente o **Cooldown Time** (ex: 15000 ms)
2. Desabilite sensores que estão causando muitos triggers

### "Alarme não dispara transição"
1. Verifique se o sensor está **habilitado** nos filtros
2. Verifique se **Auto-Program** está marcado
3. Verifique se o estado é **RUNNING**

---

## Suporte

Em caso de problemas não resolvidos:

1. Verifique o log na aba **"📋 Log"**
2. Exporte os dados antes de fechar
3. Consulte a documentação no repositório
4. Abra uma issue no GitHub com:
   - Descrição do problema
   - Mensagens de erro do log
   - Versão do sistema operacional
   - Versão do Vivado

---

*CROC FPGA Aging Monitor - Versão 2.1*
*Janeiro 2026*
