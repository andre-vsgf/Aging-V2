//==============================================================================
// telemetry_tx_simple.sv - SIMPLIFIED VERSION
//==============================================================================
// Periodic telemetry transmitter - 4 FIXED sensor types
//
// PROTOCOL (NMEA-style):
//   $SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*CS\r\n
//
// Fields:
//   FT = FPGA Temperature (hex, value*100, e.g. 0x0FA0 = 4000 = 40.00°C)
//   VI = VCCINT voltage (hex, mV, e.g. 0x0352 = 850 = 0.850V)
//   AF = ALARM_F (AM sensors, 32-bit hex)
//   AR = ALARM_RF (LF sensors, 32-bit hex)
//   AU = ALARM_UART (UART sensors, 32-bit hex)
//   AO = ALARM_OBI_DMX (OBI DMX sensors, 32-bit hex)
//   CS = XOR checksum
//
// ARBITRATION: Waits for CROC TX to be idle before transmitting
//==============================================================================

module telemetry_tx_simple #(
  parameter int CLK_FREQ_HZ    = 20000000,
  parameter int BAUD_RATE      = 125000,
  parameter int TX_INTERVAL_MS = 1000      // Send every 1 second
) (
  input  logic        clk_i,
  input  logic        rst_ni,
  
  // Control
  input  logic        enable_i,
  
  // CROC TX monitoring (for arbitration)
  input  logic        croc_tx_i,           // CROC UART TX (idle = 1)
  
  // System Monitor inputs (ALREADY CONVERTED)
  // temperature_i = °C * 100 (e.g., 4000 = 40.00°C)
  // vccint_i = mV (e.g., 850 = 0.850V)
  input  logic [15:0] temperature_i,
  input  logic [15:0] vccint_i,
  
  // 4 FIXED sensor alarm inputs
  input  logic [31:0] alarm_f_i,           // AM sensors
  input  logic [31:0] alarm_rf_i,          // LF sensors
  input  logic [31:0] alarm_uart_i,        // UART sensors
  input  logic [31:0] alarm_obi_dmx_i,     // OBI DMX sensors
  
  // UART TX output
  output logic        tx_o,
  output logic        tx_busy_o
);

  // =========================================================================
  // Parameters
  // =========================================================================
  
  localparam int CLKS_PER_BIT   = CLK_FREQ_HZ / BAUD_RATE;
  localparam int INTERVAL_CLKS  = (CLK_FREQ_HZ / 1000) * TX_INTERVAL_MS;
  
  // Wait for CROC to be idle for 30 bit-times before transmitting
  localparam int IDLE_GUARD_CLKS = CLKS_PER_BIT * 30;
  
  // Message: "$SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*XX\r\n"
  // Length:   1+3+1+2+1+4+1+2+1+4+1+2+1+8+1+2+1+8+1+2+1+8+1+2+1+8+1+2+2 = 73 chars
  localparam int MSG_LEN = 73;

  // =========================================================================
  // State Machine
  // =========================================================================
  
  typedef enum logic [2:0] {
    ST_IDLE,
    ST_WAIT_IDLE,
    ST_BUILD,
    ST_CHECKSUM,
    ST_TRANSMIT,
    ST_DONE
  } state_t;
  
  state_t state_q;
  
  // =========================================================================
  // Registers
  // =========================================================================
  
  logic [31:0] interval_cnt_q;
  logic [15:0] idle_cnt_q;
  
  // Message buffer
  logic [7:0]  msg_buf [0:MSG_LEN-1];
  logic [6:0]  msg_idx_q;
  logic [7:0]  checksum_q;
  
  // Captured values
  logic [15:0] cap_temp_q;
  logic [15:0] cap_vccint_q;
  logic [31:0] cap_f_q;
  logic [31:0] cap_rf_q;
  logic [31:0] cap_uart_q;
  logic [31:0] cap_obi_q;
  
  // UART TX
  logic [3:0]  bit_idx_q;
  logic [15:0] bit_cnt_q;
  logic [9:0]  shift_q;
  logic        tx_active_q;
  
  // =========================================================================
  // Helper: Nibble to hex ASCII
  // =========================================================================
  
  function automatic logic [7:0] hex(input logic [3:0] v);
    return (v < 10) ? (8'h30 + {4'b0, v}) : (8'h41 + {4'b0, v} - 8'd10);
  endfunction
  
  // =========================================================================
  // CROC Idle Detection
  // =========================================================================
  
  logic croc_idle;
  
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      idle_cnt_q <= '0;
    end else begin
      if (!croc_tx_i) begin
        idle_cnt_q <= '0;
      end else if (idle_cnt_q < IDLE_GUARD_CLKS) begin
        idle_cnt_q <= idle_cnt_q + 1;
      end
    end
  end
  
  assign croc_idle = (idle_cnt_q >= IDLE_GUARD_CLKS);
  
  // =========================================================================
  // Main FSM
  // =========================================================================
  
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q        <= ST_IDLE;
      interval_cnt_q <= '0;
      msg_idx_q      <= '0;
      checksum_q     <= '0;
      tx_active_q    <= 1'b0;
      bit_idx_q      <= '0;
      bit_cnt_q      <= '0;
      shift_q        <= 10'h3FF;
      
      cap_temp_q     <= '0;
      cap_vccint_q   <= '0;
      cap_f_q        <= '0;
      cap_rf_q       <= '0;
      cap_uart_q     <= '0;
      cap_obi_q      <= '0;
      
    end else begin
      
      case (state_q)
        // -------------------------------------------------------------------
        ST_IDLE: begin
          if (enable_i) begin
            if (interval_cnt_q >= INTERVAL_CLKS) begin
              interval_cnt_q <= '0;
              state_q <= ST_WAIT_IDLE;
            end else begin
              interval_cnt_q <= interval_cnt_q + 1;
            end
          end
        end
        
        // -------------------------------------------------------------------
        ST_WAIT_IDLE: begin
          if (croc_idle) begin
            // Capture values
            cap_temp_q   <= temperature_i;
            cap_vccint_q <= vccint_i;
            cap_f_q      <= alarm_f_i;
            cap_rf_q     <= alarm_rf_i;
            cap_uart_q   <= alarm_uart_i;
            cap_obi_q    <= alarm_obi_dmx_i;
            state_q <= ST_BUILD;
          end
        end
        
        // -------------------------------------------------------------------
        ST_BUILD: begin
          // Build message in one cycle (combinational)
          // "$SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*XX\r\n"
          
          // Header: "$SYS,"
          msg_buf[0]  <= "$";
          msg_buf[1]  <= "S";
          msg_buf[2]  <= "Y";
          msg_buf[3]  <= "S";
          msg_buf[4]  <= ",";
          
          // Temperature: "FT,XXXX,"
          msg_buf[5]  <= "F";
          msg_buf[6]  <= "T";
          msg_buf[7]  <= ",";
          msg_buf[8]  <= hex(cap_temp_q[15:12]);
          msg_buf[9]  <= hex(cap_temp_q[11:8]);
          msg_buf[10] <= hex(cap_temp_q[7:4]);
          msg_buf[11] <= hex(cap_temp_q[3:0]);
          msg_buf[12] <= ",";
          
          // VCCINT: "VI,XXXX,"
          msg_buf[13] <= "V";
          msg_buf[14] <= "I";
          msg_buf[15] <= ",";
          msg_buf[16] <= hex(cap_vccint_q[15:12]);
          msg_buf[17] <= hex(cap_vccint_q[11:8]);
          msg_buf[18] <= hex(cap_vccint_q[7:4]);
          msg_buf[19] <= hex(cap_vccint_q[3:0]);
          msg_buf[20] <= ",";
          
          // Alarm F: "AF,XXXXXXXX,"
          msg_buf[21] <= "A";
          msg_buf[22] <= "F";
          msg_buf[23] <= ",";
          msg_buf[24] <= hex(cap_f_q[31:28]);
          msg_buf[25] <= hex(cap_f_q[27:24]);
          msg_buf[26] <= hex(cap_f_q[23:20]);
          msg_buf[27] <= hex(cap_f_q[19:16]);
          msg_buf[28] <= hex(cap_f_q[15:12]);
          msg_buf[29] <= hex(cap_f_q[11:8]);
          msg_buf[30] <= hex(cap_f_q[7:4]);
          msg_buf[31] <= hex(cap_f_q[3:0]);
          msg_buf[32] <= ",";
          
          // Alarm RF: "AR,XXXXXXXX,"
          msg_buf[33] <= "A";
          msg_buf[34] <= "R";
          msg_buf[35] <= ",";
          msg_buf[36] <= hex(cap_rf_q[31:28]);
          msg_buf[37] <= hex(cap_rf_q[27:24]);
          msg_buf[38] <= hex(cap_rf_q[23:20]);
          msg_buf[39] <= hex(cap_rf_q[19:16]);
          msg_buf[40] <= hex(cap_rf_q[15:12]);
          msg_buf[41] <= hex(cap_rf_q[11:8]);
          msg_buf[42] <= hex(cap_rf_q[7:4]);
          msg_buf[43] <= hex(cap_rf_q[3:0]);
          msg_buf[44] <= ",";
          
          // Alarm UART: "AU,XXXXXXXX,"
          msg_buf[45] <= "A";
          msg_buf[46] <= "U";
          msg_buf[47] <= ",";
          msg_buf[48] <= hex(cap_uart_q[31:28]);
          msg_buf[49] <= hex(cap_uart_q[27:24]);
          msg_buf[50] <= hex(cap_uart_q[23:20]);
          msg_buf[51] <= hex(cap_uart_q[19:16]);
          msg_buf[52] <= hex(cap_uart_q[15:12]);
          msg_buf[53] <= hex(cap_uart_q[11:8]);
          msg_buf[54] <= hex(cap_uart_q[7:4]);
          msg_buf[55] <= hex(cap_uart_q[3:0]);
          msg_buf[56] <= ",";
          
          // Alarm OBI_DMX: "AO,XXXXXXXX"
          msg_buf[57] <= "A";
          msg_buf[58] <= "O";
          msg_buf[59] <= ",";
          msg_buf[60] <= hex(cap_obi_q[31:28]);
          msg_buf[61] <= hex(cap_obi_q[27:24]);
          msg_buf[62] <= hex(cap_obi_q[23:20]);
          msg_buf[63] <= hex(cap_obi_q[19:16]);
          msg_buf[64] <= hex(cap_obi_q[15:12]);
          msg_buf[65] <= hex(cap_obi_q[11:8]);
          msg_buf[66] <= hex(cap_obi_q[7:4]);
          msg_buf[67] <= hex(cap_obi_q[3:0]);
          
          // Checksum placeholder: "*XX\r\n"
          msg_buf[68] <= "*";
          msg_buf[69] <= "0";  // placeholder
          msg_buf[70] <= "0";  // placeholder
          msg_buf[71] <= 8'h0D; // CR
          msg_buf[72] <= 8'h0A; // LF
          
          checksum_q <= 8'h00;
          msg_idx_q  <= 7'd1;  // Start after '$'
          state_q <= ST_CHECKSUM;
        end
        
        // -------------------------------------------------------------------
        ST_CHECKSUM: begin
          if (msg_buf[msg_idx_q] == "*") begin
            // Insert checksum
            msg_buf[69] <= hex(checksum_q[7:4]);
            msg_buf[70] <= hex(checksum_q[3:0]);
            msg_idx_q <= 7'd0;
            state_q <= ST_TRANSMIT;
          end else begin
            checksum_q <= checksum_q ^ msg_buf[msg_idx_q];
            msg_idx_q <= msg_idx_q + 1;
          end
        end
        
        // -------------------------------------------------------------------
        ST_TRANSMIT: begin
          // Check if CROC started transmitting mid-message
          if (!croc_idle && msg_idx_q == 0) begin
            state_q <= ST_WAIT_IDLE;
          end
          else if (msg_idx_q < MSG_LEN) begin
            if (!tx_active_q) begin
              // Start new byte
              tx_active_q <= 1'b1;
              bit_idx_q   <= 4'd0;
              bit_cnt_q   <= '0;
              shift_q     <= {1'b1, msg_buf[msg_idx_q], 1'b0};  // Stop + Data + Start
            end else begin
              // Transmit current byte
              if (bit_cnt_q >= CLKS_PER_BIT - 1) begin
                bit_cnt_q <= '0;
                shift_q   <= {1'b1, shift_q[9:1]};
                bit_idx_q <= bit_idx_q + 1;
                
                if (bit_idx_q >= 9) begin
                  tx_active_q <= 1'b0;
                  msg_idx_q   <= msg_idx_q + 1;
                end
              end else begin
                bit_cnt_q <= bit_cnt_q + 1;
              end
            end
          end else begin
            state_q <= ST_DONE;
          end
        end
        
        // -------------------------------------------------------------------
        ST_DONE: begin
          state_q <= ST_IDLE;
        end
        
        default: state_q <= ST_IDLE;
      endcase
    end
  end

  // =========================================================================
  // Outputs
  // =========================================================================
  
  assign tx_o      = shift_q[0];
  assign tx_busy_o = (state_q != ST_IDLE);

endmodule