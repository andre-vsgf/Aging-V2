//==============================================================================
// user_sensor_monitor.sv
//==============================================================================
// OBI Peripheral for reading aging sensor data from firmware
// 
// Register Map (Base: 0x20000000):
//   0x00 - ALARM_F    (RO) - AM sensor alarm bitmap (32-bit)
//   0x04 - ALARM_RF   (RO) - LF sensor alarm bitmap (32-bit)
//   0x08 - ALARM_OBI  (RO) - OBI_DMX sensor alarm bitmap (32-bit, truncated/padded)
//   0x0C - ALARM_UART (RO) - UART sensor alarm bitmap (32-bit, truncated/padded)
//   0x10 - STATUS     (RO) - Status register
//   0x14 - CONTROL    (RW) - Control register (future use)
//
// Used by helloworld.c to read sensor values via memory-mapped I/O
//==============================================================================

module user_sensor_monitor 
  import croc_pkg::*;
#(
  parameter int unsigned AddrWidth = 32,
  parameter int unsigned DataWidth = 32,
  
  // Larguras dos sinais de sensor (calculadas automaticamente do croc_pkg)
  parameter int unsigned ObiDmxWidth = (cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers) + 
                                        cf_math_pkg::idx_width(NumPeriphs),
  parameter int unsigned UartWidth   = 19
) (
  input  logic                  clk_i,
  input  logic                  rst_ni,
  
  // OBI Slave Interface
  input  logic                      obi_req_i,
  output logic                      obi_gnt_o,
  input  logic [AddrWidth-1:0]      obi_addr_i,
  input  logic                      obi_we_i,
  input  logic [DataWidth/8-1:0]    obi_be_i,
  input  logic [DataWidth-1:0]      obi_wdata_i,
  output logic                      obi_rvalid_o,
  output logic [DataWidth-1:0]      obi_rdata_o,
  
  // Sensor Inputs (larguras variáveis)
  input  logic [31:0]               alarm_f_i,      // AM sensors (sempre 32 bits)
  input  logic [31:0]               alarm_rf_i,     // LF sensors (sempre 32 bits)
  input  logic [ObiDmxWidth-1:0]    alarm_obi_i,    // OBI_DMX sensors (largura calculada)
  input  logic [UartWidth-1:0]      alarm_uart_i,   // UART sensors (19 bits)
  
  // Debug outputs
  output logic [31:0]               status_o
);

  // =========================================================================
  // Register Offsets
  // =========================================================================
  localparam logic [7:0] REG_ALARM_F    = 8'h00;
  localparam logic [7:0] REG_ALARM_RF   = 8'h04;
  localparam logic [7:0] REG_ALARM_OBI  = 8'h08;
  localparam logic [7:0] REG_ALARM_UART = 8'h0C;
  localparam logic [7:0] REG_STATUS     = 8'h10;
  localparam logic [7:0] REG_CONTROL    = 8'h14;

  // =========================================================================
  // Internal Registers
  // =========================================================================
  logic [31:0] control_reg;
  logic [31:0] rdata_q;

  // =========================================================================
  // Função para expandir/truncar sinais para 32 bits
  // =========================================================================
  function automatic logic [31:0] expand_to_32(input logic [ObiDmxWidth-1:0] val);
    logic [31:0] result;
    result = 32'h0;
    if (ObiDmxWidth <= 32) begin
      result[ObiDmxWidth-1:0] = val;
    end else begin
      result = val[31:0];  // Trunca se maior que 32 bits
    end
    return result;
  endfunction

  function automatic logic [31:0] expand_uart_to_32(input logic [UartWidth-1:0] val);
    logic [31:0] result;
    result = 32'h0;
    result[UartWidth-1:0] = val;
    return result;
  endfunction

  // =========================================================================
  // Conversão dos sinais para 32 bits
  // =========================================================================
  wire [31:0] alarm_obi_32  = expand_to_32(alarm_obi_i);
  wire [31:0] alarm_uart_32 = expand_uart_to_32(alarm_uart_i);

  // =========================================================================
  // Status Register
  // =========================================================================
  // Bit 0: Valid (always 1)
  // Bit 1: AM sensors active (any alarm set)
  // Bit 2: LF sensors active  
  // Bit 3: OBI sensors active
  // Bit 4: UART sensors active
  // Bits 15:8: Count of active AM alarms
  // Bits 23:16: Count of active LF alarms
  
  function automatic [4:0] popcount32(input [31:0] val);
    logic [4:0] count;
    count = 0;
    for (int i = 0; i < 32; i++) begin
      count = count + {4'b0, val[i]};
    end
    return count;
  endfunction

  wire [4:0] f_count  = popcount32(alarm_f_i);
  wire [4:0] rf_count = popcount32(alarm_rf_i);
  
  assign status_o = {
    8'd0,                            // [31:24] Reserved
    3'd0, rf_count,                  // [23:16] RF alarm count
    3'd0, f_count,                   // [15:8]  F alarm count
    4'd0,                            // [7:4]   Reserved
    |alarm_uart_i,                   // [4] UART sensors have alarms
    |alarm_obi_i,                    // [3] OBI sensors have alarms
    |alarm_rf_i,                     // [2] LF sensors have alarms
    |alarm_f_i,                      // [1] AM sensors have alarms
    1'b1                             // [0] Always valid
  };

  // =========================================================================
  // OBI Response Logic
  // =========================================================================
  
  // Always grant immediately (single-cycle access)
  assign obi_gnt_o = obi_req_i;
  
  // Read data mux
  always_comb begin
    case (obi_addr_i[7:0])
      REG_ALARM_F:    rdata_q = alarm_f_i;
      REG_ALARM_RF:   rdata_q = alarm_rf_i;
      REG_ALARM_OBI:  rdata_q = alarm_obi_32;   // Convertido para 32 bits
      REG_ALARM_UART: rdata_q = alarm_uart_32;  // Convertido para 32 bits
      REG_STATUS:     rdata_q = status_o;
      REG_CONTROL:    rdata_q = control_reg;
      default:        rdata_q = 32'hDEADBEEF;
    endcase
  end
  
  // Register for valid signal (1 cycle delay)
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      obi_rvalid_o <= 1'b0;
      obi_rdata_o  <= 32'd0;
      control_reg  <= 32'd0;
    end else begin
      obi_rvalid_o <= obi_req_i & obi_gnt_o;
      obi_rdata_o  <= rdata_q;
      
      // Handle writes to control register
      if (obi_req_i && obi_we_i && (obi_addr_i[7:0] == REG_CONTROL)) begin
        control_reg <= obi_wdata_i;
      end
    end
  end

endmodule