// Copyright 2024 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51
//
// Authors:
// - Philippe Sauter <phsauter@iis.ee.ethz.ch>

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

// Aging sensors
`ifdef WITH_SENSOR_AM
  `define WITH_SENSOR
  input logic                  psclk_f_i,
  //output logic                 alarm_f_or_o,
  output logic [31:0]          alarm_f_o,
  output logic [31:0]          ff1_f_o,
  output logic [31:0]          ff2_f_o,
  output logic [31:0]          xor_out_f_o,
`else
 `endif

`ifdef WITH_SENSOR_LF
  `define WITH_SENSOR
  input logic  psclk_rf_i,
  //output logic alarm_rf_or_o,
  output logic [31:0] alarm_rf_o,
  output logic [31:0] ff1_rf_o,
  output logic [31:0] ff2_rf_o,
  output logic [31:0] xor_out_rf_o,
`else
`endif

`ifdef WITH_SENSOR_DM   // Debug module
  `define WITH_SENSOR
  input logic psclk_dm_i,
  output logic alarm_dm_or_o,
`else
`endif

`ifdef WITH_SENSOR_OBI_DMX  // OBI Demux
`define WITH_SENSOR
  input logic psclk_obi_dmx_i,
  output logic [(cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers)+cf_math_pkg::idx_width(NumPeriphs)-1:0] alarm_obi_dmx_o,
`else
`endif

`ifdef WITH_SENSOR_UART
`define WITH_SENSOR
  input logic psclk_uart_i,
  output logic [19-1:0] alarm_uart_o,
`else
`endif

// Common signal
`ifdef WITH_SENSOR
  input logic catcher_clk_i,
`else
`endif

  input  logic uart_rx_i,
  output logic uart_tx_o,

  input  logic [GpioCount-1:0] gpio_i,       // Input from GPIO pins
  output logic [GpioCount-1:0] gpio_o,       // Output to GPIO pins
  output logic [GpioCount-1:0] gpio_out_en_o // Output enable signal; 0 -> input, 1 -> output
);

  // Sensor alarm single signal output
`ifdef WITH_SENSOR_LF
 // logic [31:0] alarm_rf;
  //assign alarm_rf_or_o = |alarm_rf;
  
`endif

`ifdef WITH_SENSOR_AM
  //logic [31:0] alarm_f;
  //assign alarm_f_or_o = |alarm_f;
`endif

`ifdef WITH_SENSOR_DM
  logic [31:0] alarm_dm_low, alarm_dm_high;
  assign alarm_dm_or_o = |{alarm_dm_high, alarm_dm_low};
`else
`endif

`ifdef WITH_SENSOR_OBI_DMX
  logic [(cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers)+cf_math_pkg::idx_width(NumPeriphs)-1:0] alarm_obi_dmx;
  assign alarm_obi_dmx_o = alarm_obi_dmx;
`else
`endif

`ifdef WITH_SENSOR_UART
   logic [19-1:0] alarm_uart;
   assign alarm_uart_o = alarm_uart;
`else
`endif

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

// Connection between Croc_domain and User_domain: User Sbr, Croc Mgr
sbr_obi_req_t user_sbr_obi_req;
sbr_obi_rsp_t user_sbr_obi_rsp;

// Connection between Croc_domain and User_domain: Croc Sbr, User Mgr
mgr_obi_req_t user_mgr_obi_req;
mgr_obi_rsp_t user_mgr_obi_rsp;

logic [NumExternalIrqs-1:0] interrupts;
logic [GpioCount-1:0] gpio_in_sync;

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

// Aging Sensors
`ifdef WITH_SENSOR_AM
`define WITH_SENSOR
  .psclk_f_i           ( psclk_f_i  ),
  .alarm_f_o           ( alarm_f_o   ),
  .ff1_f_o            (ff1_f_o),
  .ff2_f_o            (ff2_f_o),
  .xor_out_f_o        (xor_out_f_o),
`else
`endif

`ifdef WITH_SENSOR_LF
`define WITH_SENSOR
  .psclk_rf_i          ( psclk_rf_i ),
  .alarm_rf_o          ( alarm_rf_o   ),
  .ff1_rf_o,
  .ff2_rf_o, 
  .xor_out_rf_o,
`else
`endif

`ifdef WITH_SENSOR_UART
`define WITH_SENSOR
  .psclk_uart_i          ( psclk_uart_i ),
  .alarm_uart_o          ( alarm_uart   ),
`else
`endif

`ifdef WITH_SENSOR_DM
`define WITH_SENSOR
    .psclk_dm_i           (psclk_dm_i),
    .alarm_dm_low_o       (alarm_dm_low),
    .alarm_dm_high_o      (alarm_dm_high),
  `else
 `endif

`ifdef WITH_SENSOR_OBI_DMX
`define WITH_SENSOR
    .psclk_obi_dmx_i  ( psclk_obi_dmx_i ),
    .alarm_obi_dmx_o  ( alarm_obi_dmx ),
  `else
  `endif

// Common signal
`ifdef WITH_SENSOR
  .catcher_clk_i       (catcher_clk_i),
`else
`endif

  .user_sbr_obi_req_o  ( user_sbr_obi_req ),
  .user_sbr_obi_rsp_i  ( user_sbr_obi_rsp ),

  .user_mgr_obi_req_i  ( user_mgr_obi_req ),
  .user_mgr_obi_rsp_o  ( user_mgr_obi_rsp ),

  .interrupts_i ( interrupts  ),
  .core_busy_o  ( status_o    )
);

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

  .sensor_alarm_f_i   ( alarm_f_o  ),  // Conecta saída do Croc na entrada do User
  .sensor_alarm_rf_i  ( alarm_rf_o ),
  .sensor_alarm_obi_dmx_i ( alarm_obi_dmx ),
  .sensor_alarm_uart_i     ( alarm_uart ),

  .gpio_in_sync_i ( gpio_in_sync ),
  .interrupts_o   ( interrupts   )
);

endmodule
