//==============================================================================
// croc_xilinx.sv - COMPLETE VERSION
//==============================================================================
// Full integration with:
// - VIO for soft reset (with proper INIT values + startup protection)
// - UART Router (PC ↔ CROC ↔ STM32)
// - System Monitor (FPGA temperature, VCCINT)
// - Telemetry TX (sends System Monitor + ALL 4 sensor types to PC)
// - All 4 aging sensor types (AM/LF/DM/OBI_DMX)
//==============================================================================

`define TARGET_FPGA
`define TARGET_AUP15

// === ENABLE ALL SENSORS ===
`define WITH_SENSOR
`define WITH_SENSOR_LF
`define WITH_SENSOR_AM
// Uncomment if your croc_soc has these sensors:
`define WITH_SENSOR_DM
`define WITH_SENSOR_OBI_DMX

`define TARGET_SYNTHESIS
`define TARGET_VIVADO
`define TARGET_XILINX

`define COMMON_CELLS_ASSERTS_OFF

// === Enable System Monitor and Telemetry ===
`define WITH_SYSTEM_MONITOR
`define WITH_TELEMETRY_TX

// === VIO ENABLED with proper handling ===
`define USE_VIO



module croc_xilinx import croc_pkg::*; #(
  localparam int unsigned GpioCount = 4,
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
  // STM32 Interface (External MCU) - For voltage/current/temperature
  // =========================================================================
  output logic  mcu_usart1_rx,     // FPGA → STM32 RX
  input  logic  mcu_usart1_tx      // STM32 TX → FPGA
);

  ////////////////////////
  //  Clock Generation  //
  ////////////////////////
  
  wire soc_clk, catcher_clk_i, psclk_rf_i, psclk_f_i; 
  wire clk_locked;
  
  // Additional clocks for all sensor types
  wire psclk_dm_i, psclk_obi_dmx_i, psclk_uart_i;

  // Tie all sensor clocks to the same source
  assign psclk_f_i       = psclk_rf_i;
  assign psclk_dm_i      = psclk_rf_i;
  assign psclk_obi_dmx_i = psclk_rf_i;
  assign psclk_uart_i    = psclk_rf_i;

  // Clock Wizard Instance
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

  // VIO control signals
  logic       vio_reset_raw;
  logic       vio_fetch_en_raw;
  logic [3:0] vio_gpio;
  logic [GpioCount-1:0] vio_gpio_i, vio_gpio_o;
  
  // Processed control signals with startup protection
  logic       vio_reset;
  logic       vio_fetch_en;
  
  // AM (F) Sensor outputs
  logic [31:0] alarm_f_o, ff1_f_o, ff2_f_o, xor_out_f_o;
  
  // LF (RF) Sensor outputs  
  logic [31:0] alarm_rf_o, ff1_rf_o, ff2_rf_o, xor_out_rf_o;
  
  // DM and OBI_DMX Sensor outputs
`ifdef WITH_SENSOR_DM
  logic [31:0] alarm_dm_o;
`else
  wire [31:0] alarm_dm_o = 32'h0;
`endif

`ifdef WITH_SENSOR_OBI_DMX
  logic [31:0] alarm_obi_dmx_o;
`else
  wire [31:0] alarm_obi_dmx_o = 32'h0;
`endif

  // === System Monitor signals ===
`ifdef WITH_SYSTEM_MONITOR
  logic [15:0] fpga_temperature;   // °C * 100 (e.g., 4523 = 45.23°C)
  logic [15:0] fpga_vccint;        // mV (e.g., 850 = 0.850V)
  logic        sysmon_temp_valid;
  logic        sysmon_vccint_valid;
  logic        sysmon_over_temp;
  logic [15:0] sysmon_temp_raw;
  logic [15:0] sysmon_vccint_raw;
  logic [2:0]  sysmon_dbg_state;
  logic [15:0] sysmon_read_count;
`endif

  // === Telemetry TX signals ===
`ifdef WITH_TELEMETRY_TX
  logic        telemetry_tx_line;
  logic        telemetry_tx_busy;
  logic        telemetry_enable;
`endif

  //==========================================================================
  // VIO INSTANTIATION WITH STARTUP PROTECTION
  //==========================================================================

`ifdef USE_VIO

  // Startup counter - ensures system starts even if VIO not connected
  logic [23:0] startup_cnt_q;
  logic        startup_done_q;
  
  localparam STARTUP_CYCLES = 24'd10_000_000;  // 0.5 sec at 20MHz
  
  always_ff @(posedge soc_clk or negedge clk_locked) begin
    if (!clk_locked) begin
      startup_cnt_q  <= 24'd0;
      startup_done_q <= 1'b0;
    end else begin
      if (!startup_done_q) begin
        if (startup_cnt_q >= STARTUP_CYCLES) begin
          startup_done_q <= 1'b1;
        end else begin
          startup_cnt_q <= startup_cnt_q + 1;
        end
      end
    end
  end

  // VIO Instance - MUST match IP configuration!
  vio_0 i_vio (
    .clk         ( soc_clk          ),
    .probe_out0  ( vio_reset_raw    ),   // 1-bit: Reset (1=run, 0=reset)
    .probe_out1  ( vio_fetch_en_raw ),   // 1-bit: CPU fetch enable
    .probe_out2  ( vio_gpio         ),   // 4-bit: GPIO control
    .probe_out3  ( vio_gpio_i       ),   // 4-bit: GPIO input override
    .probe_in0   ( status_o         )    // 1-bit: System status
  );
  
  // Startup protection: force system to run during startup period
  always_comb begin
    if (!startup_done_q) begin
      vio_reset    = 1'b1;   // Not in reset
      vio_fetch_en = 1'b1;   // CPU enabled
    end else begin
      vio_reset    = vio_reset_raw;
      vio_fetch_en = vio_fetch_en_raw;
    end
  end

`else 
  // VIO disabled - fixed values
  assign vio_reset    = 1'b1;
  assign vio_fetch_en = 1'b1;
  assign vio_gpio     = 4'b0;
  assign vio_gpio_i   = 4'b0;
`endif 

  // System reset generation
  assign soc_rst = ~clk_locked | ~vio_reset;

  // Telemetry enable (controlled by VIO fetch_en or always on)
`ifdef WITH_TELEMETRY_TX
  assign telemetry_enable = vio_fetch_en;
`endif


  //////////////////
  //  Reset Sync  //
  //////////////////

  wire rst_n;

  rstgen i_rstgen (
    .clk_i        ( soc_clk     ),
    .rst_ni       ( ~soc_rst    ),
    .test_mode_i  ( 1'b0        ),
    .rst_no       ( rst_n       ),
    .init_no      (             )
  );

  ////////////
  //  JTAG  //
  ////////////

`ifndef USE_JTAG_TRSTN
  logic jtag_trst_ni;
  assign jtag_trst_ni = 1'b1;
`endif

  /////////////////////////
  // "RTC" Clock Divider //
  /////////////////////////

  logic rtc_clk_d, rtc_clk_q;
  logic [15:0] counter_d, counter_q;

  always_comb begin
    counter_d = counter_q + 1;
    rtc_clk_d = rtc_clk_q;

    if (counter_q == 610) begin
      counter_d = '0;
      rtc_clk_d = ~rtc_clk_q;
    end
  end

  always_ff @(posedge soc_clk, negedge rst_n) begin
    if (~rst_n) begin
      counter_q <= '0;
      rtc_clk_q <= 1'b0;
    end else begin
      counter_q <= counter_d;
      rtc_clk_q <= rtc_clk_d;
    end
  end 

  // JTAG disabled
  logic jtag_tck_i, jtag_tms_i, jtag_tdi_i, jtag_tdo_o;
  assign jtag_tck_i = 1'b0;  
  assign jtag_tdi_i = 1'b0;   
  assign jtag_tms_i = 1'b0;  


  // =========================================================================
  // SYSTEM MONITOR (UltraScale+ SYSMONE4)
  // =========================================================================
  // Reads FPGA die temperature and VCCINT voltage
  // Data is sent to PC via telemetry_tx module

`ifdef WITH_SYSTEM_MONITOR
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
    .temp_raw_o      ( sysmon_temp_raw    ),
    .vccint_raw_o    ( sysmon_vccint_raw  ),
    .over_temp_o     ( sysmon_over_temp   ),
    .vccint_alarm_o  (                    ),
    .dbg_state_o     ( sysmon_dbg_state   ),
    .dbg_read_count_o( sysmon_read_count  )
  );
`else
  assign fpga_temperature    = 16'd2500;   // 25.00°C default
  assign fpga_vccint         = 16'd850;    // 0.850V default
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
  // Data Flow:
  //   PC → FPGA:
  //     Header 0x10 + data → Routes to CROC
  //     Header 0x20 + data → Routes to STM32
  //     No header → Routes to CROC (default)
  //
  //   FPGA → PC:
  //     CROC UART output (firmware prints)
  //     + Telemetry TX (System Monitor + aging sensors)
  //     + STM32 responses (voltage, current, temperature)
  //
  // STM32 sends: $TEL,Vc,X.XXX,Vi,X.XXX,Io,X.XXX,Et,XX.X,Mt,XX.X*CS
  // FPGA sends:  $SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX,...*CS
  // =========================================================================

  // Internal UART signals
  logic croc_uart_rx;    // Router → CROC
  logic croc_uart_tx;    // CROC → Router
  
  // Muxed TX line (CROC output + Telemetry)
  logic croc_tx_to_router;
  
// =========================================================================
// TELEMETRY TX - System Monitor + ALL 4 Aging Sensor Types
// =========================================================================
// Sends periodic telemetry to PC via UART with format:
//   $SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX,AD,XXXXXXXX,AO,XXXXXXXX*CS
//
// Where:
//   FT = FPGA Temperature (from System Monitor)
//   VI = VCCINT voltage (from System Monitor)
//   AF = ALARM_F (AM sensors, 32-bit)
//   AR = ALARM_RF (LF sensors, 32-bit)
//   AD = ALARM_DM (DM sensors, 32-bit)
//   AO = ALARM_OBI_DMX (OBI DMX sensors, variable width → 32-bit)
// =========================================================================

`ifdef WITH_TELEMETRY_TX
  // Telemetry TX module - sends FPGA data to PC
  telemetry_tx_4sensor #(
    .CLK_FREQ_HZ    ( CLK_FREQ  ),
    .BAUD_RATE      ( BAUD_RATE ),
    .TX_INTERVAL_MS ( 500       )  // Send every 500ms
  ) u_telemetry_tx (
    .clk_i          ( soc_clk          ),
    .rst_ni         ( rst_n            ),
    
    // Enable control (controlled by VIO fetch_en)
    .enable_i       ( telemetry_enable ),
    
    // =====================================================================
    // System Monitor inputs (FPGA temperature and voltage)
    // =====================================================================
    .fpga_temp_i    ( fpga_temperature ),  // [15:0] from system_monitor
    .vccint_i       ( fpga_vccint      ),  // [15:0] from system_monitor
    
    // =====================================================================
    // ALL 4 Aging sensor inputs - CORRECT CONNECTIONS
    // =====================================================================
    // These signals come from croc_soc outputs (declared at top level)
    
    .alarm_f_i      ( alarm_f_o        ),  // [31:0] AM sensors (F type)
    .alarm_rf_i     ( alarm_rf_o       ),  // [31:0] LF sensors (RF type)
    
    // DM sensors: alarm_dm_or_o is the OR of low and high parts
    // If you want the full 32-bit value, you need to use alarm_dm_low/high
    // But since telemetry expects 32 bits, we need to construct it:
`ifdef WITH_SENSOR_DM
    .alarm_dm_i     ( alarm_dm_or_o    ),  // [31:0] DM sensors (ORed)
`else
    .alarm_dm_i     ( 32'h0            ),  // Tie to 0 if sensor not present
`endif
    
    // OBI_DMX sensors: Variable width signal
    // The telemetry module will handle the width conversion internally
`ifdef WITH_SENSOR_OBI_DMX
    .alarm_obi_dmx_i( alarm_obi_dmx_o  ),  // [calculated width] OBI DMX
`else
    .alarm_obi_dmx_i( 32'h0            ),  // Tie to 0 if sensor not present
`endif
    
    // =====================================================================
    // UART TX output (multiplexed with CROC UART in router)
    // =====================================================================
    .tx_o           ( telemetry_tx_line),
    .tx_busy_o      ( telemetry_tx_busy),
    .tx_start_o     (                  )
  );
  
  // Mux CROC TX with Telemetry TX
  // Both lines are idle-high, active-low during transmission
  // AND gate ensures only one transmits at a time
  assign croc_tx_to_router = croc_uart_tx & telemetry_tx_line;
  
`else
  // No telemetry, pass CROC TX directly to router
  assign croc_tx_to_router = croc_uart_tx;
`endif

  // UART Router - manages PC ↔ CROC ↔ STM32 communication
  uart_router #(
    .CLK_FREQ   ( CLK_FREQ  ),
    .BAUD_RATE  ( BAUD_RATE ),
    .TIMEOUT_MS ( 1         )
  ) u_uart_router (
    .clk      ( soc_clk           ),
    .rst_n    ( rst_n             ),
    
    // PC Interface (directly connected to FPGA pins)
    .pc_rx    ( fpga_uart_rx      ),
    .pc_tx    ( fpga_uart_tx      ),
    
    // CROC Interface (includes telemetry on TX)
    .croc_rx  ( croc_uart_rx      ),
    .croc_tx  ( croc_tx_to_router ),
    
    // STM32 Interface (for voltage/current/temperature monitoring)
    .stm_rx   ( mcu_usart1_rx     ),
    .stm_tx   ( mcu_usart1_tx     )
  );


  //////////////////
  // CROC SoC     //
  //////////////////
  
  logic soc_testmode_i;
  logic soc_gpio_out_en_o;
  
  assign soc_testmode_i = 1'b0;

  croc_soc #(
    .GpioCount( GpioCount )
  )
  i_croc_soc (
    .clk_i           ( soc_clk        ),
    .rst_ni          ( rst_n          ),
    .ref_clk_i       ( rtc_clk_q      ),
    .testmode_i      ( soc_testmode_i ),
    .fetch_en_i      ( vio_fetch_en   ),
    .status_o        ( status_o       ),

    .jtag_tck_i      ( jtag_tck_i     ),
    .jtag_tdi_i      ( jtag_tdi_i     ),
    .jtag_tdo_o      ( jtag_tdo_o     ),
    .jtag_tms_i      ( jtag_tms_i     ),
    .jtag_trst_ni    ( jtag_trst_ni   ),

    // UART: Routed through uart_router
    .uart_rx_i       ( croc_uart_rx   ),
    .uart_tx_o       ( croc_uart_tx   ),

    // ===== AGING SENSORS =====
    
`ifdef WITH_SENSOR_AM
    // AM (Accelerated Metal) Sensors - "F" type
    .psclk_f_i       ( psclk_f_i      ),
    .alarm_f_o       ( alarm_f_o      ),
    .ff1_f_o         ( ff1_f_o        ),
    .ff2_f_o         ( ff2_f_o        ), 
    .xor_out_f_o     ( xor_out_f_o    ),
`endif

`ifdef WITH_SENSOR_LF
    // LF (Low Frequency) Sensors - "RF" type
    .psclk_rf_i      ( psclk_rf_i     ),
    .alarm_rf_o      ( alarm_rf_o     ),
    .ff1_rf_o        ( ff1_rf_o       ),
    .ff2_rf_o        ( ff2_rf_o       ), 
    .xor_out_rf_o    ( xor_out_rf_o   ),
`endif

`ifdef WITH_SENSOR_DM
    // DM Sensors (from colleague's work)
    .psclk_dm_i      ( psclk_dm_i     ),
    .alarm_dm_or_o   ( alarm_dm_o     ),
`endif

`ifdef WITH_SENSOR_OBI_DMX
    // OBI DMX Sensors (from colleague's work)
    .psclk_obi_dmx_i     ( psclk_obi_dmx_i ),
    .alarm_obi_dmx_or_o  ( alarm_obi_dmx_o ),
`endif

`ifdef WITH_SENSOR
    // Common sensor clock
    .catcher_clk_i   ( catcher_clk_i  ),
`endif

    // GPIO
    .gpio_i          ( vio_gpio_i        ),             
    .gpio_o          ( vio_gpio_o        ),            
    .gpio_out_en_o   ( soc_gpio_out_en_o ) 
  );

endmodule
