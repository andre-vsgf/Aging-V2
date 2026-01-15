//==============================================================================
// telemetry_tx_4sensor.sv - WIDTH-SAFE VERSION
//==============================================================================
// Periodic telemetry transmitter with PARAMETERIZED sensor widths
// Automatically handles variable-width OBI_DMX sensor
//
// Output Format (NMEA-style):
//   $SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX,AD,XXXXXXXX,AO,XXXXXXXX*CS\r\n
//==============================================================================

module telemetry_tx_4sensor 
  import croc_pkg::*;  // Import for width calculations
#(
  parameter int CLK_FREQ_HZ    = 20000000,
  parameter int BAUD_RATE      = 125000,
  parameter int TX_INTERVAL_MS = 500,
  
  // Sensor width parameters (auto-calculated from croc_pkg if not overridden)
  parameter int ALARM_F_WIDTH  = 32,
  parameter int ALARM_RF_WIDTH = 32,
  parameter int ALARM_UART_WIDTH = 32,
  parameter int ALARM_OBI_WIDTH = 32  // Default, can be overridden
) (
  input  logic        clk_i,
  input  logic        rst_ni,
  
  // Control
  input  logic        enable_i,
  
  // System Monitor inputs (always 16-bit)
  input  logic [15:0] fpga_temp_i,
  input  logic [15:0] vccint_i,
  
  // Aging sensor inputs - VARIABLE WIDTH
  input  logic [ALARM_F_WIDTH-1:0]   alarm_f_i,
  input  logic [ALARM_RF_WIDTH-1:0]  alarm_rf_i,
  input  logic [ALARM_UART_WIDTH-1:0]  alarm_uart_i,
  input  logic [ALARM_OBI_WIDTH-1:0] alarm_obi_dmx_i,
  
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
  localparam int MAX_MSG_LEN    = 96;

  // =========================================================================
  // Width Conversion Functions
  // =========================================================================
  // Convert variable-width inputs to 32-bit for transmission
  
  function automatic logic [31:0] extend_to_32(
    input logic [ALARM_F_WIDTH-1:0] val_f,
    input logic [ALARM_RF_WIDTH-1:0] val_rf,
    input logic [ALARM_UART_WIDTH-1:0] val_uart,
    input logic [ALARM_OBI_WIDTH-1:0] val_obi,
    input int selector  // 0=F, 1=RF, 2=UART, 3=OBI
  );
    logic [31:0] result;
    result = 32'h0;
    
    case (selector)
      0: begin  // ALARM_F
        if (ALARM_F_WIDTH <= 32)
          result[ALARM_F_WIDTH-1:0] = val_f;
        else
          result = val_f[31:0];  // Truncate if wider
      end
      
      1: begin  // ALARM_RF
        if (ALARM_RF_WIDTH <= 32)
          result[ALARM_RF_WIDTH-1:0] = val_rf;
        else
          result = val_rf[31:0];
      end
      
      2: begin  // ALARM_UART
        if (ALARM_UART_WIDTH <= 32)
          result[ALARM_UART_WIDTH-1:0] = val_uart;
        else
          result = val_uart[31:0];
      end
      
      3: begin  // ALARM_OBI
        if (ALARM_OBI_WIDTH <= 32)
          result[ALARM_OBI_WIDTH-1:0] = val_obi;
        else
          result = val_obi[31:0];
      end
      
      default: result = 32'h0;
    endcase
    
    return result;
  endfunction

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
  
  state_t state_q;
  
  // =========================================================================
  // Registers
  // =========================================================================
  
  logic [31:0] interval_cnt_q;
  logic [7:0]  msg_buf [0:MAX_MSG_LEN-1];
  logic [6:0]  msg_len_q;
  logic [6:0]  byte_idx_q;
  logic [7:0]  checksum_q;
  logic        tx_start_q;
  
  // Captured sensor values (32-bit normalized)
  logic [15:0] cap_temp_q;
  logic [15:0] cap_vccint_q;
  logic [31:0] cap_alarm_f_q;
  logic [31:0] cap_alarm_rf_q;
  logic [31:0] cap_alarm_uart_q;
  logic [31:0] cap_alarm_obi_q;
  
  // UART TX state
  logic [3:0]  tx_bit_idx_q;
  logic [15:0] tx_clk_cnt_q;
  logic [9:0]  tx_shift_q;
  logic        tx_active_q;
  
  // =========================================================================
  // Helper Functions
  // =========================================================================
  
  function automatic logic [7:0] nibble_to_hex(input logic [3:0] val);
    if (val < 10)
      return 8'h30 + {4'b0, val};  // '0'-'9'
    else
      return 8'h41 + {4'b0, val} - 8'd10;  // 'A'-'F'
  endfunction
  
  // =========================================================================
  // Message Builder
  // =========================================================================
  
  logic [6:0] build_idx;
  
  task automatic build_message();
    build_idx = 0;
    
    // "$SYS,"
    msg_buf[build_idx] = "$"; build_idx++;
    msg_buf[build_idx] = "S"; build_idx++;
    msg_buf[build_idx] = "Y"; build_idx++;
    msg_buf[build_idx] = "S"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    
    // "FT,XXXX,"
    msg_buf[build_idx] = "F"; build_idx++;
    msg_buf[build_idx] = "T"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[15:12]); build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[11:8]);  build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[7:4]);   build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_temp_q[3:0]);   build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    
    // "VI,XXXX,"
    msg_buf[build_idx] = "V"; build_idx++;
    msg_buf[build_idx] = "I"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[15:12]); build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[11:8]);  build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[7:4]);   build_idx++;
    msg_buf[build_idx] = nibble_to_hex(cap_vccint_q[3:0]);   build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    
    // "AF,XXXXXXXX," (AM/F sensor)
    msg_buf[build_idx] = "A"; build_idx++;
    msg_buf[build_idx] = "F"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    for (int i = 7; i >= 0; i--) begin
      msg_buf[build_idx] = nibble_to_hex(cap_alarm_f_q[i*4 +: 4]);
      build_idx++;
    end
    msg_buf[build_idx] = ","; build_idx++;
    
    // "AR,XXXXXXXX," (LF/RF sensor)
    msg_buf[build_idx] = "A"; build_idx++;
    msg_buf[build_idx] = "R"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    for (int i = 7; i >= 0; i--) begin
      msg_buf[build_idx] = nibble_to_hex(cap_alarm_rf_q[i*4 +: 4]);
      build_idx++;
    end
    msg_buf[build_idx] = ","; build_idx++;
    
    // "AD,XXXXXXXX," (UART sensor)
    msg_buf[build_idx] = "A"; build_idx++;
    msg_buf[build_idx] = "D"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    for (int i = 7; i >= 0; i--) begin
      msg_buf[build_idx] = nibble_to_hex(cap_alarm_uart_q[i*4 +: 4]);
      build_idx++;
    end
    msg_buf[build_idx] = ","; build_idx++;
    
    // "AO,XXXXXXXX" (OBI DMX sensor)
    msg_buf[build_idx] = "A"; build_idx++;
    msg_buf[build_idx] = "O"; build_idx++;
    msg_buf[build_idx] = ","; build_idx++;
    for (int i = 7; i >= 0; i--) begin
      msg_buf[build_idx] = nibble_to_hex(cap_alarm_obi_q[i*4 +: 4]);
      build_idx++;
    end
    
    // "*XX\r\n"
    msg_buf[build_idx] = "*"; build_idx++;
    msg_buf[build_idx] = "0"; build_idx++;  // Checksum high (placeholder)
    msg_buf[build_idx] = "0"; build_idx++;  // Checksum low (placeholder)
    msg_buf[build_idx] = 8'h0D; build_idx++;  // CR
    msg_buf[build_idx] = 8'h0A; build_idx++;  // LF
    
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
      tx_shift_q     <= 10'h3FF;
      
      cap_temp_q     <= '0;
      cap_vccint_q   <= '0;
      cap_alarm_f_q  <= '0;
      cap_alarm_rf_q <= '0;
      cap_alarm_uart_q <= '0;
      cap_alarm_obi_q<= '0;
      
      for (int i = 0; i < MAX_MSG_LEN; i++)
        msg_buf[i] <= 8'h00;
        
    end else begin
      tx_start_q <= 1'b0;
      
      case (state_q)
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
        
        ST_CAPTURE: begin
          // Capture and normalize to 32-bit
          cap_temp_q     <= fpga_temp_i;
          cap_vccint_q   <= vccint_i;
          cap_alarm_f_q  <= extend_to_32(alarm_f_i, alarm_rf_i, alarm_uart_i, alarm_obi_dmx_i, 0);
          cap_alarm_rf_q <= extend_to_32(alarm_f_i, alarm_rf_i, alarm_uart_i, alarm_obi_dmx_i, 1);
          cap_alarm_uart_q <= extend_to_32(alarm_f_i, alarm_rf_i, alarm_uart_i, alarm_obi_dmx_i, 2);
          cap_alarm_obi_q<= extend_to_32(alarm_f_i, alarm_rf_i, alarm_uart_i, alarm_obi_dmx_i, 3);
          state_q <= ST_BUILD_MSG;
        end
        
        ST_BUILD_MSG: begin
          build_message();
          checksum_q <= 8'h00;
          byte_idx_q <= 7'd1;  // Start after '$'
          state_q    <= ST_CALC_CHECKSUM;
        end
        
        ST_CALC_CHECKSUM: begin
          if (msg_buf[byte_idx_q] == "*") begin
            msg_buf[byte_idx_q + 1] <= nibble_to_hex(checksum_q[7:4]);
            msg_buf[byte_idx_q + 2] <= nibble_to_hex(checksum_q[3:0]);
            byte_idx_q <= 7'd0;
            state_q    <= ST_SEND_BYTE;
          end else begin
            checksum_q <= checksum_q ^ msg_buf[byte_idx_q];
            byte_idx_q <= byte_idx_q + 1;
          end
        end
        
        ST_SEND_BYTE: begin
          if (byte_idx_q < msg_len_q) begin
            tx_start_q   <= 1'b1;
            tx_active_q  <= 1'b1;
            tx_bit_idx_q <= 4'd0;
            tx_clk_cnt_q <= '0;
            tx_shift_q   <= {1'b1, msg_buf[byte_idx_q], 1'b0};
            state_q      <= ST_WAIT_BYTE;
          end else begin
            state_q <= ST_DONE;
          end
        end
        
        ST_WAIT_BYTE: begin
          if (tx_active_q) begin
            if (tx_clk_cnt_q >= CLKS_PER_BIT - 1) begin
              tx_clk_cnt_q <= '0;
              tx_shift_q   <= {1'b1, tx_shift_q[9:1]};
              tx_bit_idx_q <= tx_bit_idx_q + 1;
              
              if (tx_bit_idx_q >= 9) begin
                tx_active_q <= 1'b0;
                state_q     <= ST_NEXT_BYTE;
              end
            end else begin
              tx_clk_cnt_q <= tx_clk_cnt_q + 1;
            end
          end
        end
        
        ST_NEXT_BYTE: begin
          byte_idx_q <= byte_idx_q + 1;
          state_q    <= ST_SEND_BYTE;
        end
        
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
  
  assign tx_o       = tx_shift_q[0];
  assign tx_busy_o  = (state_q != ST_IDLE);
  assign tx_start_o = tx_start_q;

endmodule


//==============================================================================
// USAGE EXAMPLE in croc_xilinx_aging_sensors.sv
//==============================================================================
//
// telemetry_tx_4sensor #(
//   .CLK_FREQ_HZ     ( CLK_FREQ  ),
//   .BAUD_RATE       ( BAUD_RATE ),
//   .TX_INTERVAL_MS  ( 500       ),
//   .ALARM_F_WIDTH   ( 32        ),
//   .ALARM_RF_WIDTH  ( 32        ),
//   .ALARM_UART_WIDTH  ( 32        ),
//   .ALARM_OBI_WIDTH ( (cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers)
//                     + cf_math_pkg::idx_width(NumPeriphs) )  // Auto-calculated
// ) u_telemetry_tx (
//   .clk_i          ( soc_clk          ),
//   .rst_ni         ( rst_n            ),
//   .enable_i       ( telemetry_enable ),
//   .fpga_temp_i    ( fpga_temperature ),
//   .vccint_i       ( fpga_vccint      ),
//   .alarm_f_i      ( alarm_f_o        ),  // 32-bit
//   .alarm_rf_i     ( alarm_rf_o       ),  // 32-bit
//   .alarm_uart_i     ( alarm_uart_o       ),  // 32-bit
//   .alarm_obi_dmx_i( alarm_obi_dmx_o  ),  // Variable width (auto-handled)
//   .tx_o           ( telemetry_tx_line),
//   .tx_busy_o      ( telemetry_tx_busy),
//   .tx_start_o     (                  )
// );
//
//==============================================================================
