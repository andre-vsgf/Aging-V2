//==============================================================================
// croc_xilinx.sv - SIMPLIFIED VERSION
//==============================================================================
// 4 Fixed Sensor Types:
// - F (AM sensors)
// - RF (LF sensors)
// - UART sensors
// - OBI_DMX sensors
//
// PROTOCOL: $SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*CS
//==============================================================================

`define TARGET_FPGA
`define TARGET_AUP15

// === SENSOR CONFIGURATION ===
// Enable the sensors that are actually instantiated in your croc_soc
`define WITH_SENSOR
`define WITH_SENSOR_LF        // RF sensors (LF type)
`define WITH_SENSOR_AM        // F sensors (AM type)
`define WITH_SENSOR_UART      // UART sensors
`define WITH_SENSOR_OBI_DMX   // OBI DMX sensors

`define TARGET_SYNTHESIS
`define TARGET_VIVADO
`define TARGET_XILINX
`define COMMON_CELLS_ASSERTS_OFF

// === Enable System Monitor and Telemetry ===
`define WITH_SYSTEM_MONITOR
`define WITH_TELEMETRY_TX


module croc_xilinx import croc_pkg::*; #(
  localparam int unsigned GpioCount = 4,
  parameter int CLK_FREQ  = 20000000,
  parameter int BAUD_RATE = 125000
) (
  input  logic  sys_clk_p,
  input  logic  sys_clk_n,

  // PC Interface (USB-UART Bridge)
  input  logic  fpga_uart_rx,
  output logic  fpga_uart_tx,

  // STM32 Interface
  output logic  mcu_usart1_rx,
  input  logic  mcu_usart1_tx
);

  ////////////////////////
  //  Clock Generation  //
  ////////////////////////
  
  wire soc_clk, catcher_clk_i, psclk_rf_i; 
  wire clk_locked;
  
  wire psclk_f_i, psclk_uart_i, psclk_obi_dmx_i;
  assign psclk_f_i       = psclk_rf_i;
  assign psclk_uart_i    = psclk_rf_i;
  assign psclk_obi_dmx_i = psclk_rf_i;

  clk_wiz i_clk_wiz (
    .clk_in1_p     ( sys_clk_p     ),
    .clk_in1_n     ( sys_clk_n     ),
    .reset         ( 1'b0          ),
    .locked        ( clk_locked    ),
    .soc_clk       ( soc_clk       ),
    .catcher_clk_i ( catcher_clk_i ),
    .psclk_rf_i    ( psclk_rf_i    )
  );

  /////////////////////
  //  System Signals //
  /////////////////////

  logic status_o;
  logic soc_rst;
  logic fetch_en;
  
  logic [GpioCount-1:0] gpio_i, gpio_o;
  
  // Fixed enable - no VIO needed
  assign fetch_en = 1'b1;
  assign gpio_i   = 4'b0;
  
  // Reset when clock not locked
  assign soc_rst = ~clk_locked;

  // =========================================================================
  // SENSOR ALARM REGISTERS (4 fixed types)
  // =========================================================================
  
  // F (AM) Sensors
`ifdef WITH_SENSOR_AM
  logic [31:0] alarm_f_o, ff1_f_o, ff2_f_o, xor_out_f_o;
`else
  wire [31:0] alarm_f_o = 32'h0;
`endif

  // RF (LF) Sensors
`ifdef WITH_SENSOR_LF
  logic [31:0] alarm_rf_o, ff1_rf_o, ff2_rf_o, xor_out_rf_o;
`else
  wire [31:0] alarm_rf_o = 32'h0;
`endif

  // UART Sensors
`ifdef WITH_SENSOR_UART
  logic [31:0] alarm_uart_o;
`else
  wire [31:0] alarm_uart_o = 32'h0;
`endif

  // OBI_DMX Sensors
`ifdef WITH_SENSOR_OBI_DMX
  logic [31:0] alarm_obi_dmx_o;
`else
  wire [31:0] alarm_obi_dmx_o = 32'h0;
`endif

  // =========================================================================
  // SYSTEM MONITOR
  // =========================================================================
  
`ifdef WITH_SYSTEM_MONITOR
  logic [15:0] fpga_temperature;  // °C * 100
  logic [15:0] fpga_vccint;       // mV
  logic        sysmon_temp_valid;
  logic        sysmon_vccint_valid;
  logic        sysmon_over_temp;
  
  system_monitor_usp #(
    .CLK_FREQ_HZ ( CLK_FREQ )
  ) u_system_monitor (
    .clk_i           ( soc_clk            ),
    .rst_ni          ( rst_n              ),
    .ready_o         (                    ),
    .eoc_o           (                    ),
    .eos_o           (                    ),
    .temperature_o   ( fpga_temperature   ),
    .temp_valid_o    ( sysmon_temp_valid  ),
    .vccint_o        ( fpga_vccint        ),
    .vccint_valid_o  ( sysmon_vccint_valid),
    .temp_raw_o      (                    ),
    .vccint_raw_o    (                    ),
    .over_temp_o     ( sysmon_over_temp   ),
    .vccint_alarm_o  (                    ),
    .dbg_state_o     (                    ),
    .dbg_read_count_o(                    )
  );
`else
  wire [15:0] fpga_temperature = 16'd4000;  // 40.00°C
  wire [15:0] fpga_vccint      = 16'd850;   // 0.850V
`endif

  // =========================================================================
  // TELEMETRY TX
  // =========================================================================
  
  logic telemetry_tx_line;
  logic telemetry_tx_busy;

`ifdef WITH_TELEMETRY_TX
  telemetry_tx_simple #(
    .CLK_FREQ_HZ    ( CLK_FREQ  ),
    .BAUD_RATE      ( BAUD_RATE ),
    .TX_INTERVAL_MS ( 1000      )  // Send every 1 second
  ) u_telemetry_tx (
    .clk_i          ( soc_clk            ),
    .rst_ni         ( rst_n              ),
    .enable_i       ( fetch_en           ),
    .croc_tx_i      ( croc_uart_tx       ),  // Arbitration
    .temperature_i  ( fpga_temperature   ),
    .vccint_i       ( fpga_vccint        ),
    .alarm_f_i      ( alarm_f_o          ),
    .alarm_rf_i     ( alarm_rf_o         ),
    .alarm_uart_i   ( alarm_uart_o       ),
    .alarm_obi_dmx_i( alarm_obi_dmx_o    ),
    .tx_o           ( telemetry_tx_line  ),
    .tx_busy_o      ( telemetry_tx_busy  )
  );
`else
  assign telemetry_tx_line = 1'b1;
  assign telemetry_tx_busy = 1'b0;
`endif

  // =========================================================================
  // RESET SYNCHRONIZER
  // =========================================================================

  wire rst_n;

  rstgen i_rstgen (
    .clk_i        ( soc_clk     ),
    .rst_ni       ( ~soc_rst    ),
    .test_mode_i  ( 1'b0        ),
    .rst_no       ( rst_n       ),
    .init_no      (             )
  );

  // =========================================================================
  // RTC CLOCK DIVIDER
  // =========================================================================

  logic rtc_clk_q;
  logic [15:0] rtc_counter_q;

  always_ff @(posedge soc_clk, negedge rst_n) begin
    if (~rst_n) begin
      rtc_counter_q <= '0;
      rtc_clk_q     <= 1'b0;
    end else begin
      if (rtc_counter_q == 610) begin
        rtc_counter_q <= '0;
        rtc_clk_q     <= ~rtc_clk_q;
      end else begin
        rtc_counter_q <= rtc_counter_q + 1;
      end
    end
  end

  // =========================================================================
  // JTAG (disabled)
  // =========================================================================
  
  logic jtag_tck_i, jtag_tms_i, jtag_tdi_i, jtag_tdo_o, jtag_trst_ni;
  assign jtag_tck_i   = 1'b0;  
  assign jtag_tdi_i   = 1'b0;   
  assign jtag_tms_i   = 1'b0;
  assign jtag_trst_ni = 1'b1;

  // =========================================================================
  // UART ROUTING
  // =========================================================================
  
  logic croc_uart_rx;
  logic croc_uart_tx;
  logic croc_tx_muxed;
  
  // Mux CROC TX with Telemetry TX
  assign croc_tx_muxed = croc_uart_tx & telemetry_tx_line;
  
  uart_router #(
    .CLK_FREQ   ( CLK_FREQ  ),
    .BAUD_RATE  ( BAUD_RATE ),
    .TIMEOUT_MS ( 1         )
  ) u_uart_router (
    .clk      ( soc_clk         ),
    .rst_n    ( rst_n           ),
    .pc_rx    ( fpga_uart_rx    ),
    .pc_tx    ( fpga_uart_tx    ),
    .croc_rx  ( croc_uart_rx    ),
    .croc_tx  ( croc_tx_muxed   ),
    .stm_rx   ( mcu_usart1_rx   ),
    .stm_tx   ( mcu_usart1_tx   )
  );

  // =========================================================================
  // CROC SOC
  // =========================================================================
  
  logic soc_gpio_out_en_o;

  croc_soc #(
    .GpioCount( GpioCount )
  )
  i_croc_soc (
    .clk_i           ( soc_clk        ),
    .rst_ni          ( rst_n          ),
    .ref_clk_i       ( rtc_clk_q      ),
    .testmode_i      ( 1'b0           ),
    .fetch_en_i      ( fetch_en       ),
    .status_o        ( status_o       ),

    .jtag_tck_i      ( jtag_tck_i     ),
    .jtag_tdi_i      ( jtag_tdi_i     ),
    .jtag_tdo_o      ( jtag_tdo_o     ),
    .jtag_tms_i      ( jtag_tms_i     ),
    .jtag_trst_ni    ( jtag_trst_ni   ),

    .uart_rx_i       ( croc_uart_rx   ),
    .uart_tx_o       ( croc_uart_tx   ),

    // F (AM) Sensors
`ifdef WITH_SENSOR_AM
    .psclk_f_i       ( psclk_f_i      ),
    .alarm_f_o       ( alarm_f_o      ),
    .ff1_f_o         ( ff1_f_o        ),
    .ff2_f_o         ( ff2_f_o        ), 
    .xor_out_f_o     ( xor_out_f_o    ),
`endif

    // RF (LF) Sensors
`ifdef WITH_SENSOR_LF
    .psclk_rf_i      ( psclk_rf_i     ),
    .alarm_rf_o      ( alarm_rf_o     ),
    .ff1_rf_o        ( ff1_rf_o       ),
    .ff2_rf_o        ( ff2_rf_o       ), 
    .xor_out_rf_o    ( xor_out_rf_o   ),
`endif

    // UART Sensors
`ifdef WITH_SENSOR_UART
    .psclk_uart_i    ( psclk_uart_i   ),
    .alarm_uart_or_o ( alarm_uart_o   ),
`endif

    // OBI_DMX Sensors
`ifdef WITH_SENSOR_OBI_DMX
    .psclk_obi_dmx_i     ( psclk_obi_dmx_i ),
    .alarm_obi_dmx_or_o  ( alarm_obi_dmx_o ),
`endif

    // Common sensor clock
`ifdef WITH_SENSOR
    .catcher_clk_i   ( catcher_clk_i  ),
`endif

    // GPIO
    .gpio_i          ( gpio_i            ),             
    .gpio_o          ( gpio_o            ),            
    .gpio_out_en_o   ( soc_gpio_out_en_o ) 
  );

endmodule