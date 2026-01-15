//==============================================================================
// telemetry_tx_4sensor.sv
//==============================================================================
// Periodic telemetry transmitter for CROC system
// Sends System Monitor data + ALL 4 aging sensor alarm registers
//
// Output Format (NMEA-style, parsed by PC application):
//   $SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX,AD,XXXXXXXX,AO,XXXXXXXX*CS\r\n
//
// Where:
//   FT = FPGA Temperature (°C, from sysmon raw value converted)
//   VI = VCCINT voltage (V, from sysmon raw value converted)
//   AF = ALARM_F (AM sensor, 32-bit hex)
//   AR = ALARM_RF (LF sensor, 32-bit hex)
//   AD = ALARM_DM (DM sensor, 32-bit hex)
//   AO = ALARM_OBI_DMX (OBI DMX sensor, 32-bit hex)
//   CS = XOR checksum of all characters between $ and *
//==============================================================================

module telemetry_tx_4sensor #(
  parameter int CLK_FREQ_HZ    = 20000000,
  parameter int BAUD_RATE      = 125000,
  parameter int TX_INTERVAL_MS = 500
) (
  input  logic        clk_i,
  input  logic        rst_ni,
  
  // Control
  input  logic        enable_i,
  
  // System Monitor inputs
  input  logic [15:0] fpga_temp_i,     // Temperature (raw or converted)
  input  logic [15:0] vccint_i,        // VCCINT (raw or converted)
  
  // ALL 4 Aging sensor inputs
  input  logic [31:0] alarm_f_i,       // AM sensor alarms
  input  logic [31:0] alarm_rf_i,      // LF sensor alarms
  input  logic [31:0] alarm_dm_i,      // DM sensor alarms
  input  logic [31:0] alarm_obi_dmx_i, // OBI DMX sensor alarms
  
  // UART TX interface
  output logic        tx_o,
  output logic        tx_busy_o,
  output logic        tx_start_o
);

  // =========================================================================
  // Local Parameters
  // =========================================================================
  
  localparam int CLKS_PER_BIT   = CLK_FREQ_HZ / BAUD_RATE;
  localparam int INTERVAL_CLKS  = (CLK_FREQ_HZ / 1000) * TX_INTERVAL_MS;
  
  // Message buffer size (max ~85 characters)
  localparam int MAX_MSG_LEN = 96;

  // =========================================================================
  // State Machine
  // =========================================================================
  
  typedef enum logic [3:0] {
    ST_IDLE,
    ST_CAPTURE,
    ST_BUILD_MSG,
    ST_CALC_CHECKSUM,
    ST_SEND_BYTE,
    ST_WAIT_BYTE,
    ST_NEXT_BYTE,
    ST_DONE
  } state_t;
  
  state_t state_q, state_d;
  
  // =========================================================================
  // Registers
  // =========================================================================
  
  logic [31:0] interval_cnt_q;
  logic [7:0]  msg_buf [0:MAX_MSG_LEN-1];
  logic [6:0]  msg_len_q;
  logic [6:0]  byte_idx_q;
  logic [7:0]  checksum_q;
  logic        tx_start_q;
  
  // Captured sensor values (atomic snapshot)
  logic [15:0] cap_temp_q;
  logic [15:0] cap_vccint_q;
  logic [31:0] cap_alarm_f_q;
  logic [31:0] cap_alarm_rf_q;
  logic [31:0] cap_alarm_dm_q;
  logic [31:0] cap_alarm_obi_q;
  
  // UART TX state
  logic [3:0]  tx_bit_idx_q;
  logic [15:0] tx_clk_cnt_q;
  logic [9:0]  tx_shift_q;    // Start + 8 data + Stop
  logic        tx_active_q;
  
  // =========================================================================
  // Helper Function: Nibble to ASCII hex
  // =========================================================================
  
  function automatic logic [7:0] nibble_to_hex(input logic [3:0] val);
    if (val < 10)
      return 8'h30 + {4'b0, val};  // '0' - '9'
    else
      return 8'h41 + {4'b0, val} - 8'd10;  // 'A' - 'F'
  endfunction
  
  // =========================================================================
  // Message Builder Task (builds message in msg_buf)
  // =========================================================================
  
  // Index for building
  logic [6:0] build_idx;
  
  // Build the message
  task automatic build_message();
    build_idx = 0;
    
    // "$SYS,"
    msg_buf[build_idx] = "$"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "S"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "Y"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "S"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    
    // "FT," + temperature (4 hex digits)
    msg_buf[build_idx] = "F"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "T"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[15:12]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[11:8]);  build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[7:4]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[3:0]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    
    // "VI," + vccint (4 hex digits)
    msg_buf[build_idx] = "V"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "I"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[15:12]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[11:8]);  build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[7:4]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[3:0]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    
    // "AF," + 8 hex digits (AM/F sensor)
    msg_buf[build_idx] = "A"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "F"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[31:28]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[27:24]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[23:20]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[19:16]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[15:12]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[11:8]);  build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[7:4]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[3:0]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    
    // "AR," + 8 hex digits (LF/RF sensor)
    msg_buf[build_idx] = "A"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "R"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[31:28]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[27:24]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[23:20]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[19:16]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[15:12]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[11:8]);  build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[7:4]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[3:0]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    
    // "AD," + 8 hex digits (DM sensor)
    msg_buf[build_idx] = "A"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "D"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[31:28]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[27:24]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[23:20]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[19:16]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[15:12]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[11:8]);  build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[7:4]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_dm_q[3:0]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    
    // "AO," + 8 hex digits (OBI DMX sensor)
    msg_buf[build_idx] = "A"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "O"; build_idx = build_idx + 1;
    msg_buf[build_idx] = ","; build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[31:28]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[27:24]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[23:20]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[19:16]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[15:12]); build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[11:8]);  build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[7:4]);   build_idx = build_idx + 1;
    msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[3:0]);   build_idx = build_idx + 1;
    
    // "*XX\r\n" (checksum placeholder + newline)
    msg_buf[build_idx] = "*"; build_idx = build_idx + 1;
    msg_buf[build_idx] = "0"; build_idx = build_idx + 1;  // Checksum high (placeholder)
    msg_buf[build_idx] = "0"; build_idx = build_idx + 1;  // Checksum low (placeholder)
    msg_buf[build_idx] = 8'h0D; build_idx = build_idx + 1;  // CR
    msg_buf[build_idx] = 8'h0A; build_idx = build_idx + 1;  // LF
    
    msg_len_q <= build_idx;
  endtask

  // =========================================================================
  // Main State Machine
  // =========================================================================
  
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q        <= ST_IDLE;
      interval_cnt_q <= '0;
      msg_len_q      <= '0;
      byte_idx_q     <= '0;
      checksum_q     <= '0;
      tx_start_q     <= 1'b0;
      tx_active_q    <= 1'b0;
      tx_bit_idx_q   <= '0;
      tx_clk_cnt_q   <= '0;
      tx_shift_q     <= 10'h3FF;  // Idle high
      
      cap_temp_q     <= '0;
      cap_vccint_q   <= '0;
      cap_alarm_f_q  <= '0;
      cap_alarm_rf_q <= '0;
      cap_alarm_dm_q <= '0;
      cap_alarm_obi_q<= '0;
      
      for (int i = 0; i < MAX_MSG_LEN; i++)
        msg_buf[i] <= 8'h00;
        
    end else begin
      tx_start_q <= 1'b0;
      
      case (state_q)
        // -----------------------------------------------------------------
        ST_IDLE: begin
          if (enable_i) begin
            if (interval_cnt_q >= INTERVAL_CLKS) begin
              interval_cnt_q <= '0;
              state_q <= ST_CAPTURE;
            end else begin
              interval_cnt_q <= interval_cnt_q + 1;
            end
          end
        end
        
        // -----------------------------------------------------------------
        ST_CAPTURE: begin
          // Capture current values (atomic snapshot)
          cap_temp_q     <= fpga_temp_i;
          cap_vccint_q   <= vccint_i;
          cap_alarm_f_q  <= alarm_f_i;
          cap_alarm_rf_q <= alarm_rf_i;
          cap_alarm_dm_q <= alarm_dm_i;
          cap_alarm_obi_q<= alarm_obi_dmx_i;
          state_q <= ST_BUILD_MSG;
        end
        
        // -----------------------------------------------------------------
        ST_BUILD_MSG: begin
          build_message();
          checksum_q <= 8'h00;
          byte_idx_q <= 7'd1;  // Start after '$'
          state_q    <= ST_CALC_CHECKSUM;
        end
        
        // -----------------------------------------------------------------
        ST_CALC_CHECKSUM: begin
          if (msg_buf[byte_idx_q] == "*") begin
            // Done calculating, insert checksum
            msg_buf[byte_idx_q + 1] <= nibble_to_hex(checksum_q[7:4]);
            msg_buf[byte_idx_q + 2] <= nibble_to_hex(checksum_q[3:0]);
            byte_idx_q <= 7'd0;  // Reset for transmission
            state_q    <= ST_SEND_BYTE;
          end else begin
            checksum_q <= checksum_q ^ msg_buf[byte_idx_q];
            byte_idx_q <= byte_idx_q + 1;
          end
        end
        
        // -----------------------------------------------------------------
        ST_SEND_BYTE: begin
          if (byte_idx_q < msg_len_q) begin
            tx_start_q   <= 1'b1;
            tx_active_q  <= 1'b1;
            tx_bit_idx_q <= 4'd0;
            tx_clk_cnt_q <= '0;
            // Build shift register: Start(0) + Data[7:0] + Stop(1)
            tx_shift_q   <= {1'b1, msg_buf[byte_idx_q], 1'b0};
            state_q      <= ST_WAIT_BYTE;
          end else begin
            state_q <= ST_DONE;
          end
        end
        
        // -----------------------------------------------------------------
        ST_WAIT_BYTE: begin
          if (tx_active_q) begin
            if (tx_clk_cnt_q >= CLKS_PER_BIT - 1) begin
              tx_clk_cnt_q <= '0;
              tx_shift_q   <= {1'b1, tx_shift_q[9:1]};  // Shift right (LSB first)
              tx_bit_idx_q <= tx_bit_idx_q + 1;
              
              if (tx_bit_idx_q >= 9) begin  // All 10 bits sent
                tx_active_q <= 1'b0;
                state_q     <= ST_NEXT_BYTE;
              end
            end else begin
              tx_clk_cnt_q <= tx_clk_cnt_q + 1;
            end
          end
        end
        
        // -----------------------------------------------------------------
        ST_NEXT_BYTE: begin
          byte_idx_q <= byte_idx_q + 1;
          state_q    <= ST_SEND_BYTE;
        end
        
        // -----------------------------------------------------------------
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
  
  assign tx_o       = tx_shift_q[0];  // LSB of shift register
  assign tx_busy_o  = (state_q != ST_IDLE);
  assign tx_start_o = tx_start_q;

endmodule
