`timescale 1ns / 1ps
//==============================================================================
// system_monitor_usp.sv (CORRIGIDO)
//==============================================================================
// FPGA System Monitor for Xilinx UltraScale+ (Artix UltraScale+)
// Usa o IP Xilinx System Management Wizard (sysmon_wiz_0)
//
// CORREÇÕES APLICADAS:
// 1. Adicionado timeout nos estados WAIT (evita travamento)
// 2. Pipeline de cálculo corrigido (só calcula quando dados válidos)
// 3. Sinais valid agora são pulsos, não níveis
// 4. Adicionado contador de leituras bem-sucedidas (debug)
//
// REQUISITOS DO IP NO VIVADO:
// 1. Nome: sysmon_wiz_0
// 2. Interface Type: DRP
// 3. Conversion Mode: Continuous Sequence
// 4. Canais: Temperature e VCCINT habilitados
//==============================================================================

module system_monitor_usp #(
    parameter CLK_FREQ_HZ = 20_000_000
)(
    input  logic        clk_i,
    input  logic        rst_ni,
    
    // Saídas de Status
    output logic        ready_o,
    output logic        eoc_o,
    output logic        eos_o,
    
    // Temperatura (Formato: 4523 = 45.23°C)
    output logic [15:0] temperature_o,
    output logic        temp_valid_o,
    
    // VCCINT (Formato: 850 = 0.850V em mV)
    output logic [15:0] vccint_o,
    output logic        vccint_valid_o,
    
    // Valores Raw (Debug)
    output logic [15:0] temp_raw_o,
    output logic [15:0] vccint_raw_o,
    
    // Alarmes
    output logic        over_temp_o,
    output logic        vccint_alarm_o,
    
    // Debug
    output logic [2:0]  dbg_state_o,
    output logic [15:0] dbg_read_count_o  // Contador de leituras bem-sucedidas
);

    //==========================================================================
    // Endereços DRP (Fixos do Hardware SYSMON)
    //==========================================================================
    localparam [7:0] ADDR_TEMP   = 8'h00;
    localparam [7:0] ADDR_VCCINT = 8'h01;
    
    // Timeout: ~2.5ms @ 20MHz = 50000 ciclos
    localparam [15:0] TIMEOUT_CYCLES = 16'd50000;
    
    //==========================================================================
    // Sinais Internos
    //==========================================================================
    logic        reset_ip;
    logic        den;
    logic        dwe;
    logic [7:0]  daddr;
    logic [15:0] di;
    logic [15:0] do_drp;
    logic        drdy;
    logic        busy;
    logic        eoc;
    logic        eos;
    logic        alarm;

    assign reset_ip = ~rst_ni;
    assign di       = 16'h0000;
    assign dwe      = 1'b0;

    //==========================================================================
    // Máquina de Estados
    //==========================================================================
    typedef enum logic [2:0] {
        ST_IDLE       = 3'd0,
        ST_READ_TEMP  = 3'd1,
        ST_WAIT_TEMP  = 3'd2,
        ST_READ_VCCINT= 3'd3,
        ST_WAIT_VCCINT= 3'd4,
        ST_DONE       = 3'd5
    } state_t;
    
    state_t state;
    
    logic [15:0] temp_raw_reg;
    logic [15:0] vccint_raw_reg;
    logic [15:0] timeout_cnt;
    logic [15:0] read_count;
    logic        data_captured;  // Pulso quando novos dados capturados
    
    // Kickstart timer
    logic [19:0] startup_timer;
    logic        force_start;

    //==========================================================================
    // Kickstart Logic - garante início mesmo se perder primeiro EOC
    //==========================================================================
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            startup_timer <= '0;
            force_start   <= 1'b0;
        end else begin
            if (state == ST_IDLE) begin
                if (startup_timer < 20'd100_000)  // ~5ms @ 20MHz
                    startup_timer <= startup_timer + 1;
                else 
                    force_start <= 1'b1;
            end else begin
                startup_timer <= '0;
                force_start   <= 1'b0;
            end
        end
    end

    //==========================================================================
    // FSM Principal (Single Process - mais claro)
    //==========================================================================
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state          <= ST_IDLE;
            den            <= 1'b0;
            daddr          <= 8'h00;
            temp_raw_reg   <= 16'h0000;
            vccint_raw_reg <= 16'h0000;
            timeout_cnt    <= 16'd0;
            read_count     <= 16'd0;
            data_captured  <= 1'b0;
        end else begin
            // Defaults
            den           <= 1'b0;
            data_captured <= 1'b0;
            
            case (state)
                //--------------------------------------------------------------
                ST_IDLE: begin
                    timeout_cnt <= 16'd0;
                    // Inicia leitura em EOC, EOS ou force_start
                    if (eoc || eos || force_start) begin
                        daddr <= ADDR_TEMP;
                        den   <= 1'b1;
                        state <= ST_READ_TEMP;
                    end
                end
                
                //--------------------------------------------------------------
                ST_READ_TEMP: begin
                    // DEN já foi pulsado, aguarda próximo estado
                    state <= ST_WAIT_TEMP;
                end
                
                //--------------------------------------------------------------
                ST_WAIT_TEMP: begin
                    if (drdy) begin
                        temp_raw_reg <= do_drp;
                        timeout_cnt  <= 16'd0;
                        daddr        <= ADDR_VCCINT;
                        den          <= 1'b1;
                        state        <= ST_READ_VCCINT;
                    end else if (timeout_cnt >= TIMEOUT_CYCLES) begin
                        // Timeout - volta ao IDLE
                        state <= ST_IDLE;
                    end else begin
                        timeout_cnt <= timeout_cnt + 1;
                    end
                end
                
                //--------------------------------------------------------------
                ST_READ_VCCINT: begin
                    state <= ST_WAIT_VCCINT;
                end
                
                //--------------------------------------------------------------
                ST_WAIT_VCCINT: begin
                    if (drdy) begin
                        vccint_raw_reg <= do_drp;
                        data_captured  <= 1'b1;
                        read_count     <= read_count + 1;
                        state          <= ST_DONE;
                    end else if (timeout_cnt >= TIMEOUT_CYCLES) begin
                        state <= ST_IDLE;
                    end else begin
                        timeout_cnt <= timeout_cnt + 1;
                    end
                end
                
                //--------------------------------------------------------------
                ST_DONE: begin
                    state <= ST_IDLE;
                end
                
                //--------------------------------------------------------------
                default: state <= ST_IDLE;
            endcase
        end
    end

    //==========================================================================
    // Pipeline de Cálculo de Temperatura (UltraScale+)
    // T(°C) = (ADC * 509.3140064 / 65536) - 280.23087870
    // T*100 = (ADC * 50931) >> 16 - 28023
    //==========================================================================
    logic [31:0] temp_mult;
    logic [15:0] temp_shifted;
    logic signed [16:0] temp_sub;
    logic [15:0] temp_final;
    logic [2:0]  temp_pipe_valid;  // Shift register para valid
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            temp_mult       <= 32'd0;
            temp_shifted    <= 16'd0;
            temp_sub        <= 17'sd2500;
            temp_final      <= 16'd2500;
            temp_pipe_valid <= 3'b000;
        end else begin
            // Stage 0: Captura e multiplica
            temp_mult <= temp_raw_reg * 32'd50931;
            
            // Stage 1: Shift
            temp_shifted <= temp_mult[31:16];
            
            // Stage 2: Subtrai offset
            temp_sub <= $signed({1'b0, temp_shifted}) - 17'sd28023;
            
            // Stage 3: Clamp negativo
            temp_final <= (temp_sub > 0) ? temp_sub[15:0] : 16'd0;
            
            // Pipeline de valid (delay de 3 ciclos)
            temp_pipe_valid <= {temp_pipe_valid[1:0], data_captured};
        end
    end

    //==========================================================================
    // Pipeline de Cálculo de VCCINT (UltraScale+)
    // V = (ADC / 65536) * 3.0V
    // V_mV = (ADC * 3000) >> 16
    //==========================================================================
    logic [31:0] vccint_mult;
    logic [15:0] vccint_final;
    logic [1:0]  vccint_pipe_valid;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            vccint_mult       <= 32'd0;
            vccint_final      <= 16'd850;
            vccint_pipe_valid <= 2'b00;
        end else begin
            // Stage 0: Multiplica
            vccint_mult <= vccint_raw_reg * 32'd3000;
            
            // Stage 1: Shift
            vccint_final <= vccint_mult[31:16];
            
            // Pipeline de valid
            vccint_pipe_valid <= {vccint_pipe_valid[0], data_captured};
        end
    end

    //==========================================================================
    // Atribuição de Saídas
    //==========================================================================
    assign ready_o        = (state == ST_IDLE);
    assign eoc_o          = eoc;
    assign eos_o          = eos;
    assign temperature_o  = temp_final;
    assign temp_valid_o   = temp_pipe_valid[2];  // Valid após pipeline
    assign vccint_o       = vccint_final;
    assign vccint_valid_o = vccint_pipe_valid[1];
    assign temp_raw_o     = temp_raw_reg;
    assign vccint_raw_o   = vccint_raw_reg;
    assign over_temp_o    = alarm;
    assign vccint_alarm_o = 1'b0;
    
    // Debug
    assign dbg_state_o      = state;
    assign dbg_read_count_o = read_count;

    //==========================================================================
    // Instância do IP Xilinx
    //==========================================================================
    sysmon_wiz_0 u_sysmon_inst (
        // Interface DRP
        .daddr_in       (daddr),
        .dclk_in        (clk_i),
        .den_in         (den),
        .di_in          (di),
        .dwe_in         (dwe),
        .reset_in       (reset_ip),
        .do_out         (do_drp),
        .drdy_out       (drdy),
        
        // Status
        .busy_out       (busy),
        .channel_out    (),
        .eoc_out        (eoc),
        .eos_out        (eos),
        .alarm_out      (alarm),
        
        // Entradas Analógicas
        // NOTA: 1'b0 funcionou no projeto anterior!
        .vp             (1'b0),
        .vn             (1'b0)
    );

endmodule