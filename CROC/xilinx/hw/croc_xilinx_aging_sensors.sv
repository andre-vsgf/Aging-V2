
`define TARGET_FPGA
`define TARGET_AUP15
// `define TARGET_RTL

`define WITH_SENSOR
`define WITH_SENSOR_LF
`define WITH_SENSOR_AM
// `define WITH_SENSOR_DM
// `define WITH_SENSOR_UART
// `define WITH_SENSOR_OBI_DMX
// `define WITH_SENSOR_CORE

`define TARGET_SYNTHESIS
`define TARGET_VIVADO
`define TARGET_XILINX

`define COMMON_CELLS_ASSERTS_OFF

`define WITH_SYSTEM_MONITOR
`define WITH_TELEMETRY_TX

`ifdef TARGET_AUP15
 // `define USE_RESETN
  //`define USE_JTAG_TRSTN
 // `define USE_STATUS
  //`define USE_SWITCHES
  //`define USE_LEDS
  //`define USE_FAN
  `define USE_VIO
`endif



module croc_xilinx import croc_pkg::*; #(
  localparam int unsigned GpioCount = 4,
  // UART parameters (must match config.h: TB_FREQUENCY=20MHz, TB_BAUDRATE=125000)
  parameter int CLK_FREQ  = 20000000,
  parameter int BAUD_RATE = 125000
) (
  input  logic  sys_clk_p,
  input  logic  sys_clk_n,

  // =========================================================================
  // PC Interface (USB-UART Bridge) - Direct connection
  // =========================================================================
  input  logic  fpga_uart_rx,      // PC TX → FPGA RX
  output logic  fpga_uart_tx,      // FPGA TX → PC RX

  // =========================================================================
  // STM32 Interface (External MCU)
  // =========================================================================
  output logic  mcu_usart1_rx,     // FPGA → STM32 RX
  input  logic  mcu_usart1_tx      // STM32 TX → FPGA
);

  ////////////////////////
  //  Clock Generation  //
  ////////////////////////
  
 

  wire sys_clk;
  wire soc_clk, catcher_clk_i, psclk_rf_i, psclk_f_i, psclk_obi_dmx_i, psclk_uart_i; 

  assign psclk_f_i = psclk_rf_i; // Tie AM sensor clock to LF sensor clock for testing
  assign psclk_obi_dmx_i = psclk_rf_i;
  assign psclk_uart_i = psclk_rf_i;

  clk_wiz i_clkwiz (
    .clk_in1_p   ( sys_clk_p     ),
    .clk_in1_n   ( sys_clk_n     ),
    .reset       ( 1'b0          ),
    .locked      (               ),
    .catcher_clk_i ( catcher_clk_i ),
    .psclk_rf_i  ( psclk_rf_i    ),
    .soc_clk     ( soc_clk       )
  );

  /////////////////////
  //  System Inputs  //
  /////////////////////

  logic status_o;

  ////////////
  //  VIOs  //
  ////////////
  logic       vio_reset, vio_fetch_en, vio_gpio;
  logic [GpioCount-1:0] vio_gpio_i, vio_gpio_o;
  logic [31:0] alarm_rf_o, ff1_rf_o, ff2_rf_o, xor_out_rf_o;
  logic [31:0] alarm_f_o, ff1_f_o, ff2_f_o, xor_out_f_o;

  // === System Monitor signals ===
`ifdef WITH_SYSTEM_MONITOR
  logic [15:0] fpga_temperature;   // °C * 100 (e.g., 4523 = 45.23°C)
  logic [15:0] fpga_vccint;        // mV (e.g., 850 = 0.850V)
  logic        sysmon_temp_valid;
  logic        sysmon_vccint_valid;
  logic        sysmon_over_temp;
  logic [15:0] sysmon_temp_raw;    // Raw ADC value
  logic [15:0] sysmon_vccint_raw;  // Raw ADC value
  // Debug signals
  logic [2:0]  sysmon_dbg_state;
  logic [15:0] sysmon_read_count;  // Contador de leituras bem-sucedidas
`endif

  // === Telemetry TX signals ===
`ifdef WITH_TELEMETRY_TX
  logic        telemetry_tx_line;
  logic        telemetry_tx_busy;
  logic        telemetry_enable;
`endif

`ifdef USE_VIO
 /* vio_0 i_vio (
    .clk        ( soc_clk      ),
    .probe_out0 ( vio_reset    ),
    .probe_out1 ( vio_fetch_en ),
    .probe_out2 ( vio_gpio     ),
    .probe_out3 ( vio_gpio_i[0] ),
    .probe_out4 ( vio_gpio_i[1] ),
    .probe_out5 ( vio_gpio_i[2] ),
    .probe_out6 ( vio_gpio_i[3] ),
    .probe_in0  ( status_o           ),
    .probe_in1  ( vio_gpio_o[0]     ),
    .probe_in2  ( vio_gpio_o[1]     ),
    .probe_in3  ( vio_gpio_o[2]     ),
    .probe_in4  ( vio_gpio_o[3]     ),
    //.probe_in5  ( alarm_rf_or_o )
    .probe_in5  ( alarm_rf_o ),
    .probe_in6  ( ff1_rf_o ),
    .probe_in7 ( ff1_f_o ),
    .probe_in8  ( alarm_f_o ),
    .probe_in9  ( ff2_rf_o ),
    .probe_in10  ( ff2_f_o ),
    .probe_in11  ( xor_out_f_o ),
    .probe_in12  ( xor_out_rf_o )
    
  );*/
  vio_2 i_vio(
    .clk        ( soc_clk      ),
    .probe_out0  ( vio_reset ),
    .probe_out1  ( vio_fetch_en ),
    .probe_out2  ( vio_gpio ),
    .probe_out3  ( vio_gpio_i ),
    .probe_in0  ( status_o     )
`ifdef WITH_SYSTEM_MONITOR
    // Optional: Add sysmon probes to VIO
    // .probe_in13 ( fpga_temperature ),
    // .probe_in14 ( fpga_vccint )
`endif
  );
`else 
  assign vio_reset    = '1;
  assign vio_fetch_en = '1;
  assign vio_gpio     = '0;
  assign vio_gpio_i  = '0;
`endif 

  assign soc_rst      = ~vio_reset;

  // === Telemetry enable (always on after reset, or controlled via VIO) ===
`ifdef WITH_TELEMETRY_TX
  assign telemetry_enable = vio_fetch_en;  // Reuse fetch_en or add dedicated VIO probe
`endif

  //////////////////
  //  Reset Sync  //
  //////////////////

  wire rst_n;

  rstgen i_rstgen (
    .clk_i        ( soc_clk     ),
    .rst_ni       ( ~soc_rst    ),
    .test_mode_i  ( '0          ),
    .rst_no       ( rst_n       ),
    .init_no      ( )
  );

  ////////////
  //  JTAG  //
  ////////////

 `ifdef USE_JTAG_VDDGND
  assign jtag_vdd_o = 1'b1;
  assign jtag_gnd_o = 1'b0;
`endif
`ifndef USE_JTAG_TRSTN
  logic jtag_trst_ni;
  assign jtag_trst_ni = 1'b1;
`endif
 

  /////////////////////////
  // "RTC" Clock Divider //
  /////////////////////////

  logic rtc_clk_d, rtc_clk_q;
  logic [15:0] counter_d, counter_q;

  // Divide soc_clk (20 MHz) by 610 => ~32.768kHz RTC Clock
  // TODO: does genesys 2 have a 32.768kHz reference clock?
  always_comb begin
    counter_d = counter_q + 1;
    rtc_clk_d = rtc_clk_q;

    if(counter_q == 610) begin
      counter_d = '0;
      rtc_clk_d = ~rtc_clk_q;
    end
  end

  always_ff @(posedge soc_clk, negedge rst_n) begin
    if(~rst_n) begin
      counter_q <= '0;
      rtc_clk_q <= 0;
    end else begin
      counter_q <= counter_d;
      rtc_clk_q <= rtc_clk_d;
    end
  end 


logic  jtag_tck_i;
logic  jtag_tms_i;
logic  jtag_tdi_i;
logic  jtag_tdo_o;
assign jtag_tck_i   = 1'b0;  
assign jtag_tdi_i   = 1'b0;   
assign jtag_tms_i   = 1'b0;  

  // =========================================================================
  // SYSTEM MONITOR (UltraScale+ SYSMONE4)
  // =========================================================================
  // Baseado em EOC (End of Conversion) - corrigido
  // =========================================================================

`ifdef WITH_SYSTEM_MONITOR
  system_monitor_usp #(
    .CLK_FREQ_HZ ( CLK_FREQ )
  ) u_system_monitor (
    .clk_i           ( soc_clk            ),
    .rst_ni          ( rst_n              ),
    
    // Status
    .ready_o         (                    ),
    .eoc_o           (                    ),
    .eos_o           (                    ),
    
    // Valores convertidos
    .temperature_o   ( fpga_temperature   ),
    .temp_valid_o    ( sysmon_temp_valid  ),
    .vccint_o        ( fpga_vccint        ),
    .vccint_valid_o  ( sysmon_vccint_valid),
    
    // Valores raw (para debug)
    .temp_raw_o      ( sysmon_temp_raw    ),
    .vccint_raw_o    ( sysmon_vccint_raw  ),
    
    // Alarmes
    .over_temp_o     ( sysmon_over_temp   ),
    .vccint_alarm_o  (                    ),
    
    // Debug
    .dbg_state_o     ( sysmon_dbg_state   ),
    .dbg_read_count_o( sysmon_read_count  )
  );
`else
  // Defaults when System Monitor is disabled
  assign fpga_temperature    = 16'd2500;   // 25.00°C
  assign fpga_vccint         = 16'd850;    // 0.850V
  assign sysmon_temp_valid   = 1'b0;
  assign sysmon_vccint_valid = 1'b0;
  assign sysmon_over_temp    = 1'b0;
  assign sysmon_temp_raw     = 16'd0;
  assign sysmon_vccint_raw   = 16'd0;
  assign sysmon_dbg_state    = 3'd0;
  assign sysmon_read_count   = 16'd0;
`endif


  // =========================================================================
  // UART ROUTING INFRASTRUCTURE
  // =========================================================================
  // Manages communication between PC, CROC, and STM32
  //
  // PC → Devices:
  //   Header 0x10 + data → CROC only
  //   Header 0x20 + data → STM32 only
  //   No header → CROC (default)
  //
  // Devices → PC:
  //   CROC output + Telemetry (muxed) + STM32 responses
  // =========================================================================

  // Internal UART signals
  logic croc_uart_rx;    // Router → CROC
  logic croc_uart_tx;    // CROC → Router
  
  // === NEW: Muxed TX line (CROC + Telemetry) ===
  logic croc_tx_to_router;
  
`ifdef WITH_TELEMETRY_TX
  // Telemetry TX module
  telemetry_tx #(
    .CLK_FREQ_HZ    ( CLK_FREQ  ),
    .BAUD_RATE      ( BAUD_RATE ),
    .TX_INTERVAL_MS ( 500       )  // Send every 500ms
  ) u_telemetry_tx (
    .clk_i        ( soc_clk          ),
    .rst_ni       ( rst_n            ),
    
    // Enable
    .enable_i     ( telemetry_enable ),
    
    // System Monitor inputs
    .fpga_temp_i  ( fpga_temperature ),
    .vccint_i     ( fpga_vccint      ),
    
    // Aging sensor inputs
    .alarm_f_i    ( alarm_f_o        ),
    .alarm_rf_i   ( alarm_rf_o       ),
    
    // UART TX
    .tx_o         ( telemetry_tx_line),
    .tx_busy_o    ( telemetry_tx_busy),
    .tx_start_o   (                  )
  );
  
  // Mux CROC TX with Telemetry TX
  // When telemetry is transmitting, it takes priority (AND gate for idle-high UART)
  // Both lines are idle-high, active-low during transmission
  assign croc_tx_to_router = croc_uart_tx & telemetry_tx_line;
  
`else
  // No telemetry, pass CROC TX directly
  assign croc_tx_to_router = croc_uart_tx;
`endif

  uart_router #(
    .CLK_FREQ   ( CLK_FREQ  ),
    .BAUD_RATE  ( BAUD_RATE ),
    .TIMEOUT_MS ( 1         )
  ) u_uart_router (
    .clk      ( soc_clk           ),
    .rst_n    ( rst_n             ),
    
    // PC Interface
    .pc_rx    ( fpga_uart_rx      ),
    .pc_tx    ( fpga_uart_tx      ),
    
    // CROC Interface (now includes telemetry)
    .croc_rx  ( croc_uart_rx      ),
    .croc_tx  ( croc_tx_to_router ),
    
    // STM32 Interface
    .stm_rx   ( mcu_usart1_rx     ),
    .stm_tx   ( mcu_usart1_tx     )
  );

  //////////////////
  // CROC SoC //
  //////////////////
  logic  soc_testmode_i;
  assign soc_testmode_i = '0;

  croc_soc #(
    .GpioCount( GpioCount )
  )
  i_croc_soc (
    .clk_i           ( soc_clk        ),
    .rst_ni          ( rst_n          ),
    .ref_clk_i       ( rtc_clk_q      ),
    .testmode_i      ( soc_testmode_i ),
    .fetch_en_i      ( vio_fetch_en   ), //soc_fetch_en //vio_fetch_en
    .status_o        ( status_o       ),

    .jtag_tck_i      (  jtag_tck_i   ), //jtag_tck_i
    .jtag_tdi_i      (  jtag_tdi_i   ), //jtag_tdi_i
    .jtag_tdo_o      (  jtag_tdo_o   ), //jtag_tdo_o
    .jtag_tms_i      (  jtag_tms_i   ), //jtag_tms_i
    .jtag_trst_ni    (  jtag_trst_ni ),

    .uart_rx_i       ( croc_uart_rx  ),
    .uart_tx_o       ( croc_uart_tx  ),

    `ifdef WITH_SENSOR_AM
    //aging sensors
        .psclk_f_i           ( psclk_f_i    ),
        .alarm_f_o           ( alarm_f_o    ),
        .ff1_f_o            (ff1_f_o),
        .ff2_f_o            (ff2_f_o), 
        .xor_out_f_o        (xor_out_f_o),
    `else
    `endif

    `ifdef WITH_SENSOR_LF
    //aging sensors
        .psclk_rf_i          (psclk_rf_i),
        .alarm_rf_o,
        .ff1_rf_o,
        .ff2_rf_o, 
        .xor_out_rf_o,
    `else
    `endif

    `ifdef WITH_SENSOR_DM
    //aging sensors
        .psclk_dm_i          (psclk_dm_i),
        .alarm_dm_or_o       (alarm_dm_or_o),
    `else
    `endif

    `ifdef WITH_SENSOR_UART
    //aging sensors
        .psclk_uart_i      (psclk_uart_i),
       // .alarm_uart_o      (alarm_uart_o),
    `else
    `endif

    `ifdef WITH_SENSOR_OBI_DMX
    //aging sensors
        .psclk_obi_dmx_i     (psclk_obi_dmx_i),
        //.alarm_obi_dmx_or_o  (alarm_obi_dmx_or_o),
    `else
    `endif

    // Common signal - only include once if either macro is defined
    `ifdef WITH_SENSOR
        .catcher_clk_i       (catcher_clk_i),
    `endif

    .gpio_i          ( vio_gpio_i        ),             
    .gpio_o          ( vio_gpio_o        ),            
    .gpio_out_en_o   ( soc_gpio_out_en_o ) 
  );

endmodule
