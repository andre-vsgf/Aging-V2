// Copyright 2024 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51
//
// Authors:
// - Philippe Sauter <phsauter@iis.ee.ethz.ch>

`include "register_interface/typedef.svh"
`include "obi/typedef.svh"

package user_pkg;

  ////////////////////////////////
  // User Manager Address maps //
  ///////////////////////////////
  
  // None


  /////////////////////////////////////
  // User Subordinate Address maps ////
  /////////////////////////////////////

  localparam int unsigned NumUserDomainSubordinates = 1;

  // Endereço Base: 0x20000000 (O mesmo que usamos no teste, mas agora é definitivo)
  localparam bit [31:0] UserSensorsAddrOffset = croc_pkg::UserBaseAddr;
  localparam bit [31:0] UserSensorsAddrRange  = 32'h0000_1000; // 4KB

  localparam int unsigned NumDemuxSbrRules  = NumUserDomainSubordinates;
  localparam int unsigned NumDemuxSbr       = NumDemuxSbrRules + 1;

  typedef enum int {
    UserError   = 0,
    UserSensors = 1  // <--- Nome novo e profissional
  } user_demux_outputs_e;

  localparam croc_pkg::addr_map_rule_t [NumDemuxSbrRules-1:0] user_addr_map = '{
    '{ idx: UserSensors, start_addr: UserSensorsAddrOffset, end_addr: UserSensorsAddrOffset + UserSensorsAddrRange }
  };


endpackage
