//==============================================================================
// telemetry_tx.sv
//==============================================================================
// Simple telemetry transmitter for CROC FPGA
//
// Periodically sends system data in text format:
// "$SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX*CS\r\n"
//
// The output can be muxed with existing UART or sent on a separate line.
//==============================================================================

module telemetry_tx #(
    parameter CLK_FREQ_HZ    = 20_000_000,
    parameter BAUD_RATE      = 115200,
    parameter TX_INTERVAL_MS = 500
)(
    input  logic        clk_i,
    input  logic        rst_ni,
    
    // Enable control
    input  logic        enable_i,
    
    // System Monitor inputs (from system_monitor_usp.sv)
    input  logic [15:0] fpga_temp_i,      // Temperature in 0.01°C units
    input  logic [15:0] vccint_i,         // VCCINT in mV
    
    // Aging sensor inputs
    input  logic [31:0] alarm_f_i,
    input  logic [31:0] alarm_rf_i,
    
    // UART TX output
    output logic        tx_o,
    output logic        tx_busy_o,
    
    // Trigger output (pulses when starting transmission)
    output logic        tx_start_o
);

    //==========================================================================
    // Parameters
    //==========================================================================
    localparam CLKS_PER_BIT = CLK_FREQ_HZ / BAUD_RATE;
    localparam TX_INTERVAL_CLKS = (CLK_FREQ_HZ / 1000) * TX_INTERVAL_MS;
    
    // Message template: "$SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX*XX\r\n"
    // Max length: 52 characters
    localparam MSG_LEN = 52;
    
    //==========================================================================
    // Interval timer
    //==========================================================================
    logic [31:0] interval_cnt;
    logic        interval_tick;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            interval_cnt <= '0;
            interval_tick <= 1'b0;
        end else begin
            interval_tick <= 1'b0;
            if (enable_i) begin
                if (interval_cnt >= TX_INTERVAL_CLKS - 1) begin
                    interval_cnt <= '0;
                    interval_tick <= 1'b1;
                end else begin
                    interval_cnt <= interval_cnt + 1;
                end
            end else begin
                interval_cnt <= '0;
            end
        end
    end
    
    //==========================================================================
    // Message buffer and state machine
    //==========================================================================
    logic [7:0]  msg_buffer [0:MSG_LEN-1];
    logic [5:0]  msg_idx;
    logic [5:0]  msg_len_reg;
    logic        building;
    logic        transmitting;
    
    // Latched values
    logic [15:0] temp_lat;
    logic [15:0] vccint_lat;
    logic [31:0] alarm_f_lat;
    logic [31:0] alarm_rf_lat;
    
    // Checksum
    logic [7:0]  checksum;
    
    // UART TX signals
    logic        uart_start;
    logic [7:0]  uart_data;
    logic        uart_done;
    logic        uart_busy;
    
    // ASCII conversion functions
    function automatic [7:0] digit_to_ascii(input [3:0] digit);
        return 8'h30 + digit;  // '0' = 0x30
    endfunction
    
    function automatic [7:0] hex_to_ascii(input [3:0] nibble);
        if (nibble < 10)
            return 8'h30 + nibble;  // '0'-'9'
        else
            return 8'h41 + nibble - 10;  // 'A'-'F'
    endfunction
    
    //==========================================================================
    // Main state machine
    //==========================================================================
    typedef enum logic [2:0] {
        ST_IDLE,
        ST_LATCH,
        ST_BUILD,
        ST_CHECKSUM,
        ST_TRANSMIT,
        ST_WAIT_TX
    } state_t;
    
    state_t state;
    logic [3:0] build_step;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state <= ST_IDLE;
            msg_idx <= '0;
            msg_len_reg <= '0;
            building <= 1'b0;
            transmitting <= 1'b0;
            uart_start <= 1'b0;
            uart_data <= '0;
            checksum <= '0;
            build_step <= '0;
            tx_start_o <= 1'b0;
            
            temp_lat <= '0;
            vccint_lat <= '0;
            alarm_f_lat <= '0;
            alarm_rf_lat <= '0;
        end else begin
            uart_start <= 1'b0;
            tx_start_o <= 1'b0;
            
            case (state)
                ST_IDLE: begin
                    if (interval_tick && enable_i) begin
                        state <= ST_LATCH;
                        tx_start_o <= 1'b1;
                    end
                end
                
                ST_LATCH: begin
                    // Latch current values
                    temp_lat <= fpga_temp_i;
                    vccint_lat <= vccint_i;
                    alarm_f_lat <= alarm_f_i;
                    alarm_rf_lat <= alarm_rf_i;
                    
                    checksum <= '0;
                    msg_idx <= '0;
                    build_step <= '0;
                    state <= ST_BUILD;
                end
                
                ST_BUILD: begin
                    // Build message character by character
                    // "$SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX"
                    // 0123456789...
                    
                    case (msg_idx)
                        // Header: "$SYS,FT,"
                        0:  msg_buffer[0]  <= 8'h24;  // $
                        1:  msg_buffer[1]  <= 8'h53;  // S
                        2:  msg_buffer[2]  <= 8'h59;  // Y
                        3:  msg_buffer[3]  <= 8'h53;  // S
                        4:  msg_buffer[4]  <= 8'h2C;  // ,
                        5:  msg_buffer[5]  <= 8'h46;  // F
                        6:  msg_buffer[6]  <= 8'h54;  // T
                        7:  msg_buffer[7]  <= 8'h2C;  // ,
                        
                        // Temperature: XX.XX (temp_lat in 0.01°C)
                        8:  msg_buffer[8]  <= digit_to_ascii((temp_lat / 1000) % 10);
                        9:  msg_buffer[9]  <= digit_to_ascii((temp_lat / 100) % 10);
                        10: msg_buffer[10] <= 8'h2E;  // .
                        11: msg_buffer[11] <= digit_to_ascii((temp_lat / 10) % 10);
                        12: msg_buffer[12] <= digit_to_ascii(temp_lat % 10);
                        
                        // ",VI,"
                        13: msg_buffer[13] <= 8'h2C;  // ,
                        14: msg_buffer[14] <= 8'h56;  // V
                        15: msg_buffer[15] <= 8'h49;  // I
                        16: msg_buffer[16] <= 8'h2C;  // ,
                        
                        // VCCINT: X.XXX (vccint_lat in mV)
                        17: msg_buffer[17] <= digit_to_ascii((vccint_lat / 1000) % 10);
                        18: msg_buffer[18] <= 8'h2E;  // .
                        19: msg_buffer[19] <= digit_to_ascii((vccint_lat / 100) % 10);
                        20: msg_buffer[20] <= digit_to_ascii((vccint_lat / 10) % 10);
                        21: msg_buffer[21] <= digit_to_ascii(vccint_lat % 10);
                        
                        // ",AF,"
                        22: msg_buffer[22] <= 8'h2C;  // ,
                        23: msg_buffer[23] <= 8'h41;  // A
                        24: msg_buffer[24] <= 8'h46;  // F
                        25: msg_buffer[25] <= 8'h2C;  // ,
                        
                        // alarm_f: 8 hex digits
                        26: msg_buffer[26] <= hex_to_ascii(alarm_f_lat[31:28]);
                        27: msg_buffer[27] <= hex_to_ascii(alarm_f_lat[27:24]);
                        28: msg_buffer[28] <= hex_to_ascii(alarm_f_lat[23:20]);
                        29: msg_buffer[29] <= hex_to_ascii(alarm_f_lat[19:16]);
                        30: msg_buffer[30] <= hex_to_ascii(alarm_f_lat[15:12]);
                        31: msg_buffer[31] <= hex_to_ascii(alarm_f_lat[11:8]);
                        32: msg_buffer[32] <= hex_to_ascii(alarm_f_lat[7:4]);
                        33: msg_buffer[33] <= hex_to_ascii(alarm_f_lat[3:0]);
                        
                        // ",AR,"
                        34: msg_buffer[34] <= 8'h2C;  // ,
                        35: msg_buffer[35] <= 8'h41;  // A
                        36: msg_buffer[36] <= 8'h52;  // R
                        37: msg_buffer[37] <= 8'h2C;  // ,
                        
                        // alarm_rf: 8 hex digits
                        38: msg_buffer[38] <= hex_to_ascii(alarm_rf_lat[31:28]);
                        39: msg_buffer[39] <= hex_to_ascii(alarm_rf_lat[27:24]);
                        40: msg_buffer[40] <= hex_to_ascii(alarm_rf_lat[23:20]);
                        41: msg_buffer[41] <= hex_to_ascii(alarm_rf_lat[19:16]);
                        42: msg_buffer[42] <= hex_to_ascii(alarm_rf_lat[15:12]);
                        43: msg_buffer[43] <= hex_to_ascii(alarm_rf_lat[11:8]);
                        44: msg_buffer[44] <= hex_to_ascii(alarm_rf_lat[7:4]);
                        45: msg_buffer[45] <= hex_to_ascii(alarm_rf_lat[3:0]);
                        
                        default: ;
                    endcase
                    
                    if (msg_idx < 46) begin
                        msg_idx <= msg_idx + 1;
                    end else begin
                        msg_idx <= 1;  // Start checksum from index 1 (skip $)
                        state <= ST_CHECKSUM;
                    end
                end
                
                ST_CHECKSUM: begin
                    // Calculate XOR checksum of bytes 1-45
                    if (msg_idx < 46) begin
                        checksum <= checksum ^ msg_buffer[msg_idx];
                        msg_idx <= msg_idx + 1;
                    end else begin
                        // Add *XX\r\n
                        msg_buffer[46] <= 8'h2A;  // *
                        msg_buffer[47] <= hex_to_ascii(checksum[7:4]);
                        msg_buffer[48] <= hex_to_ascii(checksum[3:0]);
                        msg_buffer[49] <= 8'h0D;  // \r
                        msg_buffer[50] <= 8'h0A;  // \n
                        
                        msg_len_reg <= 6'd51;
                        msg_idx <= '0;
                        state <= ST_TRANSMIT;
                    end
                end
                
                ST_TRANSMIT: begin
                    if (!uart_busy) begin
                        if (msg_idx < msg_len_reg) begin
                            uart_data <= msg_buffer[msg_idx];
                            uart_start <= 1'b1;
                            msg_idx <= msg_idx + 1;
                            state <= ST_WAIT_TX;
                        end else begin
                            state <= ST_IDLE;
                        end
                    end
                end
                
                ST_WAIT_TX: begin
                    if (uart_done) begin
                        state <= ST_TRANSMIT;
                    end
                end
                
                default: state <= ST_IDLE;
            endcase
        end
    end
    
    //==========================================================================
    // Simple UART TX
    //==========================================================================
    logic [15:0] baud_cnt;
    logic [3:0]  bit_idx;
    logic [9:0]  tx_shift;  // Start bit + 8 data + stop bit
    logic        tx_active;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            baud_cnt <= '0;
            bit_idx <= '0;
            tx_shift <= 10'h3FF;  // Idle high
            tx_active <= 1'b0;
            uart_done <= 1'b0;
            uart_busy <= 1'b0;
        end else begin
            uart_done <= 1'b0;
            
            if (uart_start && !tx_active) begin
                // Load shift register: Start(0) + Data + Stop(1)
                tx_shift <= {1'b1, uart_data, 1'b0};
                tx_active <= 1'b1;
                uart_busy <= 1'b1;
                baud_cnt <= '0;
                bit_idx <= '0;
            end else if (tx_active) begin
                if (baud_cnt >= CLKS_PER_BIT - 1) begin
                    baud_cnt <= '0;
                    tx_shift <= {1'b1, tx_shift[9:1]};  // Shift right
                    bit_idx <= bit_idx + 1;
                    
                    if (bit_idx >= 9) begin
                        tx_active <= 1'b0;
                        uart_busy <= 1'b0;
                        uart_done <= 1'b1;
                    end
                end else begin
                    baud_cnt <= baud_cnt + 1;
                end
            end
        end
    end
    
    assign tx_o = tx_shift[0];
    assign tx_busy_o = uart_busy || (state != ST_IDLE);

endmodule