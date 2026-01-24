# 📖 Manual do Operador - Tela de Aging Analysis

Este manual explica como utilizar a aba **"📈 Aging Analysis"** para executar experimentos de envelhecimento com troca automática de bitstreams.

---

## 🎯 Objetivo

A tela de Aging Analysis automatiza o processo de:
1. Monitorar os sensores de envelhecimento
2. Detectar quando um alarme acende (indicando degradação)
3. Trocar automaticamente para o próximo bitstream (com mais "folga")
4. Registrar todas as transições para análise posterior

---

## 🖥️ Visão Geral da Interface

```
┌─────────────────────────────────────────────────────────────────┐
│  📈 Aging Analysis                                              │
├─────────────────────────┬───────────────────────────────────────┤
│                         │                                       │
│  📁 BITSTREAM QUEUE     │  📋 TRANSITION HISTORY                │
│  ┌───────────────────┐  │  ┌─────────────────────────────────┐  │
│  │ Diretório: [___]  │  │  │ Time | From → To | Triggers    │  │
│  │ Fase inicial: 0°  │  │  │------|-----------|-------------|  │
│  │ Passo: 5°         │  │  │ ...  │ ...       │ ...         │  │
│  │ [Load Bitstreams] │  │  └─────────────────────────────────┘  │
│  │                   │  │                                       │
│  │ 1. bit_0deg (0°)  │  │  [📁 Export CSV]                      │
│  │ 2. bit_5deg (5°) ←│  │                                       │
│  │ 3. bit_10deg (10°)│  │                                       │
│  └───────────────────┘  │                                       │
│                         │                                       │
│  ⚙️ EXPERIMENT CONTROL  │                                       │
│  ┌───────────────────┐  │                                       │
│  │ ☑ Auto-Program    │  │                                       │
│  │ Stabilization: 3s │  │                                       │
│  │ Cooldown: 10s     │  │                                       │
│  │                   │  │                                       │
│  │ State: RUNNING    │  │                                       │
│  │ Current: bit_5deg │  │                                       │
│  │ Next: bit_10deg   │  │                                       │
│  │                   │  │                                       │
│  │ [▶ Start] [⏹ Stop]│  │                                       │
│  └───────────────────┘  │                                       │
│                         │                                       │
└─────────────────────────┴───────────────────────────────────────┘
```

---

## 📋 Passo a Passo: Preparando o Experimento

### 1️⃣ Carregar os Bitstreams

1. Clique em **"📂 Browse"**
2. Navegue até a pasta onde estão os arquivos `.bit`
3. Selecione a pasta e clique OK

> ⚠️ **Importante**: Os bitstreams devem estar nomeados em ordem alfabética (ex: `phase_00.bit`, `phase_05.bit`, `phase_10.bit`...)

### 2️⃣ Configurar as Fases

| Campo | Descrição | Valor Típico |
|-------|-----------|--------------|
| **Start Phase** | Fase do primeiro bitstream | `0°` |
| **Step** | Incremento entre bitstreams | `5°` |

**Exemplo**: Se você tem 10 bitstreams com Start=0° e Step=5°:
- `phase_00.bit` → 0°
- `phase_05.bit` → 5°
- `phase_10.bit` → 10°
- ... e assim por diante

### 3️⃣ Carregar a Fila

1. Clique em **"Load Bitstreams"**
2. A lista será preenchida mostrando cada bitstream e sua fase
3. Verifique se a quantidade e ordem estão corretas

---

## ⚙️ Configurando os Tempos

### Stabilization Time (Tempo de Estabilização)
- **O que é**: Quanto tempo esperar após detectar um alarme antes de trocar o bitstream
- **Por que**: Evita trocas por alarmes espúrios ou transientes
- **Recomendado**: `3000 ms` (3 segundos)

### Cooldown Time (Tempo de Resfriamento)
- **O que é**: Quanto tempo esperar após reprogramar antes de voltar a monitorar
- **Por que**: Dá tempo para o FPGA estabilizar com o novo bitstream
- **Recomendado**: `10000 ms` (10 segundos)

> 💡 **Dica**: Se o sistema estiver trocando muito rápido (loop), aumente o Cooldown para 15-20 segundos.

---

## ▶️ Executando o Experimento

### Iniciar

1. ✅ Marque a caixa **"🔄 Enable Auto-Program on Alarm"**
2. Clique em **"▶ Start"**
3. O estado mudará para **RUNNING** (verde)

### Durante o Experimento

O sistema irá:
- Monitorar continuamente os 4 tipos de sensores (F, RF, UART, OBI)
- Quando detectar um **novo** alarme:
  1. Estado muda para **ALARM_DETECTED** (amarelo)
  2. Aguarda o tempo de estabilização
  3. Estado muda para **REPROGRAMMING** (azul)
  4. Reprograma o FPGA com o próximo bitstream
  5. Estado muda para **COOLDOWN** (cinza)
  6. Aguarda o tempo de resfriamento
  7. Estado volta para **RUNNING** (verde)

### Parar

- Clique em **"⏹ Stop"** para encerrar o experimento
- Confirme na caixa de diálogo

### Pular Manualmente

- Clique em **"⏭ Skip"** para ir ao próximo bitstream sem esperar alarme
- Útil para testes ou quando quiser avançar manualmente

---

## 📊 Entendendo os Estados

| Estado | Cor | Significado |
|--------|-----|-------------|
| **IDLE** | Cinza | Experimento não iniciado |
| **RUNNING** | 🟢 Verde | Monitorando alarmes normalmente |
| **ALARM_DETECTED** | 🟡 Amarelo | Alarme detectado, aguardando estabilização |
| **REPROGRAMMING** | 🔵 Azul | Reprogramando o FPGA |
| **COOLDOWN** | ⚫ Cinza | Aguardando após reprogram |
| **PAUSED** | 🟠 Laranja | Experimento pausado |
| **FINISHED** | 🟣 Roxo | Fim da fila de bitstreams |

---

## 📋 Histórico de Transições

Cada vez que o sistema troca de bitstream, uma linha é adicionada à tabela:

| Coluna | Descrição |
|--------|-----------|
| **Time** | Horário da transição |
| **Hours** | Horas de experimento decorridas |
| **From → To** | Bitstream anterior → novo |
| **Phase** | Fase anterior → nova (em graus) |
| **Triggers** | Quais sensores dispararam (ex: F:3, RF:1) |
| **Alarms** | Total de alarmes ativos |

### Exportar Dados

1. Clique em **"📁 Export CSV"**
2. Escolha onde salvar o arquivo
3. O arquivo CSV pode ser aberto no Excel para análise

---

## ❓ Perguntas Frequentes

### "O experimento não inicia"
- Verifique se há bitstreams na fila
- Verifique se "Enable Auto-Program" está marcado
- Verifique se o FPGA está conectado

### "O sistema fica trocando de bitstream sem parar"
- Aumente o **Cooldown Time** para 15000 ms ou mais
- Verifique se os bitstreams estão na ordem correta (fase crescente)

### "Alarme acendeu mas não trocou de bitstream"
- Verifique se "Enable Auto-Program" está marcado
- O sistema só troca quando detecta um **novo** alarme (bit que estava 0 e foi para 1)
- Se o alarme já estava aceso, não conta como "novo"

### "Quero pausar temporariamente"
- Use o botão **"⏭ Skip"** para avançar para um bitstream com mais folga
- Ou pare e reinicie o experimento

### "Acabaram os bitstreams"
- O estado mudará para **FINISHED**
- Adicione mais bitstreams à pasta e reinicie o experimento

---

## 📝 Checklist Antes de Iniciar

- [ ] FPGA conectado e funcionando
- [ ] Pasta de bitstreams selecionada
- [ ] Bitstreams carregados na fila (verificar quantidade)
- [ ] Fase inicial e passo configurados corretamente
- [ ] Tempos de estabilização e cooldown definidos
- [ ] "Enable Auto-Program" marcado
- [ ] Conexão serial estabelecida (LED verde na barra de status)

---

## 🆘 Em Caso de Problemas

1. **Pare o experimento** (botão Stop)
2. **Verifique o log** na aba "📋 Log"
3. **Exporte os dados** antes de fechar a aplicação
4. **Anote o estado** e última mensagem de erro

---

*Versão 2.0 - Janeiro 2026*
