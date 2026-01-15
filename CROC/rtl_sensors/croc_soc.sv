//==============================================================================
// croc_soc.sv - SIGNAL CORRECTIONS FOR TELEMETRY
//==============================================================================
// This file shows the CORRECTED signal declarations and connections
// Replace the corresponding sections in your croc_soc.sv
//==============================================================================

module croc_soc import croc_pkg::*; #(
  parameter int unsigned GpioCount = 16
) (
  input  logic clk_i,
  input  logic rst_ni,
  input  logic ref_clk_i,
  input  logic testmode_i,
  input  logic fetch_en_i,
  output logic status_o,

  input  logic jtag_tck_i,
  input  logic jtag_tdi_i,
  output logic jtag_tdo_o,
  input  logic jtag_tms_i,
  input  logic jtag_trst_ni,

  // =========================================================================
  // Aging Sensors - CORRECTED OUTPUT TYPES
  // =========================================================================
  
`ifdef WITH_SENSOR_AM
  `define WITH_SENSOR
  input logic                  psclk_f_i,
  output logic [31:0]          alarm_f_o,      // Full 32-bit output
  output logic [31:0]          ff1_f_o,
  output logic [31:0]          ff2_f_o,
  output logic [31:0]          xor_out_f_o,
`endif

`ifdef WITH_SENSOR_LF
  `define WITH_SENSOR
  input logic                  psclk_rf_i,
  output logic [31:0]          alarm_rf_o,     // Full 32-bit output
  output logic [31:0]          ff1_rf_o,
  output logic [31:0]          ff2_rf_o,
  output logic [31:0]          xor_out_rf_o,
`endif

`ifdef WITH_SENSOR_DM
  `define WITH_SENSOR
  input logic                  psclk_dm_i,
  // CHANGE: Output full 32-bit value instead of single OR bit
  output logic [31:0]          alarm_dm_o,     // Full 32-bit output (was alarm_dm_or_o)
`endif

`ifdef WITH_SENSOR_OBI_DMX
  `define WITH_SENSOR
  input logic                  psclk_obi_dmx_i,
  // Keep variable width (will be handled by telemetry module parameters)
  output logic [(cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers)+cf_math_pkg::idx_width(NumPeriphs)-1:0] alarm_obi_dmx_o,
`endif

`ifdef WITH_SENSOR_UART
  `define WITH_SENSOR
  input logic                  psclk_uart_i,
  output logic [19-1:0]        alarm_uart_o,
`endif

`ifdef WITH_SENSOR
  input logic                  catcher_clk_i,
`endif

  input  logic uart_rx_i,
  output logic uart_tx_o,

  input  logic [GpioCount-1:0] gpio_i,
  output logic [GpioCount-1:0] gpio_o,
  output logic [GpioCount-1:0] gpio_out_en_o
);

  // =========================================================================
  // Internal Signal Handling for DM Sensors
  // =========================================================================
  
`ifdef WITH_SENSOR_DM
  // Internal signals from croc_domain (low and high parts)
  logic [31:0] alarm_dm_low, alarm_dm_high;
  
  // OPTION 1: Output the combined 64-bit as single 32-bit OR
  // assign alarm_dm_o = alarm_dm_high | alarm_dm_low;
  
  // OPTION 2: Output only the low 32 bits (most common sensors)
  assign alarm_dm_o = alarm_dm_low;
  
  // OPTION 3: Concatenate high and low, taking lower 32 bits
  // assign alarm_dm_o = {alarm_dm_high[15:0], alarm_dm_low[15:0]};
`endif

  // =========================================================================
  // Internal Signal Handling for OBI_DMX Sensors
  // =========================================================================
  
`ifdef WITH_SENSOR_OBI_DMX
  logic [(cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers)+cf_math_pkg::idx_width(NumPeriphs)-1:0] alarm_obi_dmx_internal;
  assign alarm_obi_dmx_o = alarm_obi_dmx_internal;
`endif

  // =========================================================================
  // Rest of module (unchanged)
  // =========================================================================
  
  logic synced_rst_n, synced_fetch_en;

  rstgen i_rstgen (
    .clk_i,
    .rst_ni,
    .test_mode_i ( testmode_i ),
    .rst_no      ( synced_rst_n ),
    .init_no ( )
  );

  sync #(
      .STAGES     (    2 ),
      .ResetValue ( 1'b0 )
    ) i_ext_intr_sync (
      .clk_i,
      .rst_ni   ( synced_rst_n    ),
      .serial_i ( fetch_en_i      ),
      .serial_o ( synced_fetch_en )
    );

  // Connection between Croc_domain and User_domain
  sbr_obi_req_t user_sbr_obi_req;
  sbr_obi_rsp_t user_sbr_obi_rsp;
  mgr_obi_req_t user_mgr_obi_req;
  mgr_obi_rsp_t user_mgr_obi_rsp;

  logic [NumExternalIrqs-1:0] interrupts;
  logic [GpioCount-1:0] gpio_in_sync;

  // =========================================================================
  // CROC Domain Instantiation - CORRECTED CONNECTIONS
  // =========================================================================
  
  croc_domain #(
    .GpioCount( GpioCount ) 
  ) i_croc (
    .clk_i,
    .rst_ni ( synced_rst_n ),
    .ref_clk_i,
    .testmode_i,
    .fetch_en_i ( synced_fetch_en ),

    .jtag_tck_i,
    .jtag_tdi_i,
    .jtag_tdo_o,
    .jtag_tms_i,
    .jtag_trst_ni,

    .uart_rx_i,
    .uart_tx_o,

    .gpio_i,             
    .gpio_o,            
    .gpio_out_en_o,

    .gpio_in_sync_o ( gpio_in_sync ),

    // Aging Sensors - CORRECTED OUTPUT CONNECTIONS
`ifdef WITH_SENSOR_AM
    .psclk_f_i      ( psclk_f_i  ),
    .alarm_f_o      ( alarm_f_o  ),   // Direct connection - already 32-bit
    .ff1_f_o        ( ff1_f_o    ),
    .ff2_f_o        ( ff2_f_o    ),
    .xor_out_f_o    ( xor_out_f_o),
`endif

`ifdef WITH_SENSOR_LF
    .psclk_rf_i     ( psclk_rf_i ),
    .alarm_rf_o     ( alarm_rf_o ),   // Direct connection - already 32-bit
    .ff1_rf_o,
    .ff2_rf_o, 
    .xor_out_rf_o,
`endif

`ifdef WITH_SENSOR_UART
    .psclk_uart_i   ( psclk_uart_i ),
    .alarm_uart_o   ( alarm_uart_o ),  // 19-bit output
`endif

`ifdef WITH_SENSOR_DM
    .psclk_dm_i     ( psclk_dm_i      ),
    .alarm_dm_low_o ( alarm_dm_low    ),  // Connect to internal signals
    .alarm_dm_high_o( alarm_dm_high   ),
`endif

`ifdef WITH_SENSOR_OBI_DMX
    .psclk_obi_dmx_i ( psclk_obi_dmx_i       ),
    .alarm_obi_dmx_o ( alarm_obi_dmx_internal),  // Variable width
`endif

`ifdef WITH_SENSOR
    .catcher_clk_i  ( catcher_clk_i ),
`endif

    .user_sbr_obi_req_o  ( user_sbr_obi_req ),
    .user_sbr_obi_rsp_i  ( user_sbr_obi_rsp ),

    .user_mgr_obi_req_i  ( user_mgr_obi_req ),
    .user_mgr_obi_rsp_o  ( user_mgr_obi_rsp ),

    .interrupts_i ( interrupts  ),
    .core_busy_o  ( status_o    )
  );

  // =========================================================================
  // USER Domain Instantiation - CORRECTED CONNECTIONS
  // =========================================================================
  
  user_domain #(
    .GpioCount( GpioCount ) 
  ) i_user (
    .clk_i,
    .rst_ni ( synced_rst_n ),
    .ref_clk_i,
    .testmode_i,

    .user_sbr_obi_req_i ( user_sbr_obi_req ),
    .user_sbr_obi_rsp_o ( user_sbr_obi_rsp ),

    .user_mgr_obi_req_o ( user_mgr_obi_req ),
    .user_mgr_obi_rsp_i ( user_mgr_obi_rsp ),

    // Pass all sensor signals to user domain
    .sensor_alarm_f_i      ( alarm_f_o              ),  // 32-bit
    .sensor_alarm_rf_i     ( alarm_rf_o             ),  // 32-bit
    
`ifdef WITH_SENSOR_OBI_DMX
    .sensor_alarm_obi_dmx_i( alarm_obi_dmx_o        ),  // 32-bit (mapped from DM)
`else
    .sensor_alarm_obi_dmx_i( 32'h0                  ),
`endif

`ifdef WITH_SENSOR_UART
    .sensor_alarm_uart_i   ( alarm_uart_o           ),  // 19-bit (mapped to OBI)
`else
    .sensor_alarm_uart_i   ( 19'h0                  ),
`endif

    .gpio_in_sync_i ( gpio_in_sync ),
    .interrupts_o   ( interrupts   )
  );

endmodule


//==============================================================================
// SUMMARY OF CHANGES
//==============================================================================
//
// 1. Changed `alarm_dm_or_o` → `alarm_dm_o` (single bit → 32-bit)
//    - Now outputs full 32-bit alarm value instead of just OR
//    - Options: OR both halves, use low half only, or concatenate
//
// 2. Added internal signals `alarm_dm_low` and `alarm_dm_high`
//    - croc_domain outputs these two 32-bit signals
//    - croc_soc combines them into single 32-bit output
//
// 3. alarm_obi_dmx_o remains variable width
//    - Telemetry module will handle width conversion via parameters
//
// 4. All signals now properly connected for telemetry transmission
//
//==============================================================================
