# 📖 Manual do Operador - Tela de Aging Analysis V2

Este manual explica como utilizar a aba **"📈 Aging Analysis"** para executar experimentos de envelhecimento com troca automática de bitstreams.

---

## 🎯 Objetivo

A tela de Aging Analysis automatiza o processo de:
1. Monitorar os sensores de envelhecimento (4 tipos: F, RF, UART, OBI)
2. Detectar quando um alarme acende (indicando degradação)
3. Trocar automaticamente para o próximo bitstream (com mais "folga")
4. Registrar todas as transições com detalhes de quais alarmes dispararam
5. Calcular dose de radiação acumulada

---

## 🖥️ Visão Geral da Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│  📈 Aging Analysis                                                  │
├──────────────────────────┬──────────────────────────────────────────┤
│                          │                                          │
│  📁 BITSTREAM QUEUE      │  📋 TRANSITION HISTORY                   │
│  ┌────────────────────┐  │  ┌──────────────────────────────────────┐│
│  │ [📂 Browse]        │  │  │ Time|Hours|Dose|From→To|Phase|Trig  ││
│  │ [🔄 Load Bitstreams]│  │  │-----|-----|----|----- -|-----|------││
│  │                    │  │  │12:30| 1.5 |0.45|m330→m325|-330→-325|F:2││
│  │ 1. m330.bit (-330°)│  │  │12:45| 1.7 |0.51|m325→m320|-325→-320|F:1││
│  │ 2. m325.bit (-325°)←  │  └──────────────────────────────────────┘│
│  │ 3. m320.bit (-320°)│  │                                          │
│  │ 4. m315.bit (-315°)│  │  [📁 Export CSV]                         │
│  └────────────────────┘  │                                          │
│                          │                                          │
│  🎛️ SENSOR FILTERS       │                                          │
│  ┌────────────────────┐  │                                          │
│  │ ☑ F (AM Sensors)   │  │                                          │
│  │ ☑ RF (LF Sensors)  │  │                                          │
│  │ ☑ UART Sensors     │  │                                          │
│  │ ☑ OBI (Demux)      │  │                                          │
│  │ [Enable All][Disable] │                                          │
│  └────────────────────┘  │                                          │
│                          │                                          │
│  ☢️ RADIATION CONFIG     │                                          │
│  ┌────────────────────┐  │                                          │
│  │ Dose Rate: 0.3krad/h │                                          │
│  │ Initial: 0.0 krad  │  │                                          │
│  │ Current: 1.25 krad │  │                                          │
│  └────────────────────┘  │                                          │
│                          │                                          │
│  ⚙️ EXPERIMENT CONTROL   │                                          │
│  ┌────────────────────┐  │                                          │
│  │ ☑ Auto-Program     │  │                                          │
│  │ Stabilization: 3s  │  │                                          │
│  │ Cooldown: 10s      │  │                                          │
│  │ State: RUNNING     │  │                                          │
│  │ [▶ Start][⏹ Stop] │  │                                          │
│  └────────────────────┘  │                                          │
│                          │                                          │
└──────────────────────────┴──────────────────────────────────────────┘
```

---

## 📋 Passo a Passo: Preparando o Experimento

### 1️⃣ Carregar os Bitstreams

1. Clique em **"📂 Browse"**
2. Navegue até a pasta com os arquivos `.bit` (ex: `~/out_bitstreams/`)
3. Selecione a pasta e clique OK
4. Clique em **"🔄 Load Bitstreams (Auto-detect phases)"**

> ✅ **O sistema detecta automaticamente as fases** a partir dos nomes dos arquivos:
> - `croc_aging_clkout3phase_m330.bit` → **-330°**
> - `croc_aging_clkout3phase_m325.bit` → **-325°**
> - `croc_aging_clkout3phase_m320.bit` → **-320°**
> - etc.

> ⚠️ **Ordenação**: Os bitstreams são ordenados automaticamente do **maior número** (330) para o **menor** (315), pois as fases são negativas e o experimento começa com menos folga (-330°) e avança para mais folga (-315°).

### 2️⃣ Configurar Filtros de Sensores (NOVO!)

A seção **"🎛️ Sensor Trigger Filters"** permite escolher quais sensores podem disparar transições:

| Checkbox | Sensor | Descrição |
|----------|--------|-----------|
| **F** | AM Sensors | Sensores de amplitude modulada |
| **RF** | LF Sensors | Sensores de baixa frequência |
| **UART** | UART Sensors | Sensores UART |
| **OBI** | Demux Sensors | Sensores OBI Demux |

**Quando usar:**
- Se um tipo de sensor está disparando muitas transições e você quer observar outros sensores
- Desabilite o sensor "problemático" para que apenas os outros possam causar transições
- **Todos os sensores continuam sendo monitorados**, apenas não causam auto-reprogram

**Exemplo prático:**
> Se os sensores F estão causando muitas transições e você quer ver quando RF ou UART disparam:
> 1. Desmarque **"☑ F (AM Sensors)"**
> 2. Mantenha os outros marcados
> 3. Agora apenas RF, UART e OBI podem causar transições

### 3️⃣ Configurar Radiação (NOVO!)

A seção **"☢️ Radiation Configuration"** permite rastrear a dose de radiação:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| **Dose Rate** | Taxa de radiação em krad/hora | `0.3 krad/h` |
| **Initial Dose** | Dose já acumulada antes do experimento | `10.5 krad` |
| **Current Dose** | Dose atual (calculada automaticamente) | `12.75 krad` |

> 💡 A dose é calculada como: `Current = Initial + (Hours × Rate)`

### 4️⃣ Configurar Tempos

| Campo | Descrição | Recomendado |
|-------|-----------|-------------|
| **Stabilization Time** | Espera após alarme | `3000 ms` (3s) |
| **Cooldown Time** | Espera após reprogram | `10000 ms` (10s) |

---

## ▶️ Executando o Experimento

### Iniciar

1. ✅ Marque **"🔄 Enable Auto-Program on Alarm"**
2. Clique em **"▶ Start"**

> ⚠️ **IMPORTANTE**: Ao iniciar, o sistema verifica se o primeiro bitstream da fila já está gravado na FPGA. Se não estiver, ele programa automaticamente antes de começar a monitorar.

### Lógica de Trigger

**Qualquer alarme aceso** após o período de cooldown é suficiente para disparar uma transição.

Isso significa que:
- Não precisa ser um "novo" alarme (bit que mudou de 0→1)
- Se após o cooldown ainda houver alarmes ativos, o sistema troca de bitstream
- Isso evita que o sistema fique "preso" com alarmes que não limpam

### Durante o Experimento

O sistema monitora continuamente os 4 tipos de sensores. Quando um alarme é detectado:

```
Estado: RUNNING (verde)
    ↓ Novo alarme detectado (sensor habilitado)
Estado: ALARM_DETECTED (amarelo)
    ↓ Aguarda 3 segundos (estabilização)
Estado: REPROGRAMMING (azul)
    ↓ Programa próximo bitstream
Estado: COOLDOWN (cinza)
    ↓ Aguarda 10 segundos
Estado: RUNNING (verde)
    ↓ Volta a monitorar
```

### Modificar Filtros em Tempo Real

Você pode **habilitar/desabilitar sensores a qualquer momento** durante o experimento:

1. Marque ou desmarque as caixas na seção "Sensor Trigger Filters"
2. A mudança é imediata
3. Sensores desabilitados continuam sendo monitorados mas não causam transições

---

## 📊 Histórico de Transições

Cada transição registra:

| Coluna | Descrição |
|--------|-----------|
| **Time** | Horário da transição |
| **Hours** | Horas de experimento |
| **Dose (krad)** | Dose de radiação acumulada |
| **From → To** | Bitstream anterior → novo |
| **Phase** | Fase anterior → nova (ex: -330° → -325°) |
| **Triggers** | Quais sensores dispararam (ex: F:2, RF:1) |
| **Alarms** | Total de alarmes ativos |

### Exportar Dados

1. Clique em **"📁 Export CSV"**
2. O arquivo pode ser aberto no Excel
3. Contém todas as colunas + bits específicos que dispararam

---

## 📈 Gráficos de Degradação

Abaixo do histórico de transições, há duas abas com gráficos:

### 📊 Slack vs Dose
Mostra como o slack (folga temporal) muda conforme a dose de radiação aumenta.
- **Pontos azuis**: Medições reais (cada transição)
- **Linha amarela**: Regressão linear dos dados
- **Linha laranja tracejada**: Projeção futura

### ⏱️ Slack vs Time
Mostra como o slack muda ao longo do tempo de experimento.
- **Pontos verdes**: Medições reais (cada transição)
- **Linha amarela**: Regressão linear dos dados
- **Linha laranja tracejada**: Projeção futura

### Informações de Regressão

Na parte inferior dos gráficos aparece:
- **Taxa de degradação**: Quanto o slack aumenta por unidade (krad ou hora)
- **R²**: Coeficiente de determinação (quanto mais próximo de 1, melhor o ajuste)

**Exemplo**: `Slack degradation rate: 0.0234 ns/krad | R² = 0.9856`

> 💡 A projeção mostra uma estimativa de como a curva continuará, baseada na tendência atual. Use com cautela - é apenas uma extrapolação linear.

---

## 📊 Entendendo os Estados

| Estado | Cor | Significado |
|--------|-----|-------------|
| **IDLE** | Cinza | Experimento não iniciado |
| **PROGRAMMING_INITIAL** | 🔵 Azul | Gravando primeiro bitstream |
| **RUNNING** | 🟢 Verde | Monitorando alarmes |
| **ALARM_DETECTED** | 🟡 Amarelo | Aguardando estabilização |
| **REPROGRAMMING** | 🔵 Azul | Reprogramando FPGA |
| **COOLDOWN** | ⚫ Cinza | Aguardando após reprogram |
| **FINISHED** | 🟣 Roxo | Fim da fila de bitstreams |

---

## ❓ Perguntas Frequentes

### "O sistema fica trocando muito rápido"
- Aumente o **Cooldown Time** para 15000-20000 ms
- Ou desabilite o sensor que está causando muitas transições

### "Quero observar apenas um tipo de sensor"
1. Clique em **"Disable All"**
2. Marque apenas o sensor que deseja observar
3. Apenas esse sensor poderá causar transições

### "Alarme acendeu mas não trocou"
- Verifique se o sensor está **habilitado** nos filtros
- Verifique se **Auto-Program** está marcado
- Verifique se o estado é **RUNNING** (não COOLDOWN)

### "O sistema troca mesmo quando o alarme já estava aceso"
Sim, esse é o comportamento esperado! Após o cooldown, **qualquer alarme aceso** (não apenas novos) dispara uma transição. Isso evita que o sistema fique preso com alarmes persistentes.

### "Como sei qual sensor disparou?"
- Olhe a coluna **"Triggers"** no histórico
- Ex: `F:2, RF:1` significa 2 bits de F e 1 de RF dispararam

### "Como configuro a radiação?"
1. **Dose Rate**: Taxa em krad/hora (fornecida pela fonte de radiação)
2. **Initial Dose**: Dose já acumulada (se estiver continuando experimento)

---

## 📝 Checklist Antes de Iniciar

- [ ] FPGA conectada (LED verde na barra de status)
- [ ] Bitstreams carregados (verificar lista)
- [ ] Filtros de sensores configurados
- [ ] Dose Rate configurado (se aplicável)
- [ ] Dose inicial configurada (se continuando experimento)
- [ ] Tempos de estabilização e cooldown OK
- [ ] **"Enable Auto-Program"** marcado

---

## 🔧 Resumo das Funcionalidades

| Funcionalidade | Descrição |
|----------------|-----------|
| **Auto-detecção de fase** | Extrai fase do nome do arquivo (m330 = -330°) |
| **Ordenação automática** | Maior para menor (330 → 315) |
| **Filtros de sensores** | Habilita/desabilita cada tipo em tempo real |
| **Programação inicial** | Garante primeiro bitstream ao iniciar |
| **Dose de radiação** | Calcula dose baseado em rate + tempo |
| **Trigger em qualquer alarme** | Não precisa ser "novo" - qualquer alarme aceso dispara |
| **Gráfico Slack vs Dose** | Mostra degradação em função da radiação |
| **Gráfico Slack vs Time** | Mostra degradação em função do tempo |
| **Projeção linear** | Estima tendência futura da degradação |

---

*Versão 2.1 - Janeiro 2026*
