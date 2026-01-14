// Copyright 2024 ETH Zurich and University of Bologna.
// SPDX-License-Identifier: SHL-0.51

module user_sensor_monitor import croc_pkg::*; #(
  parameter obi_pkg::obi_cfg_t ObiCfg   = croc_pkg::SbrObiCfg,
  parameter type                obi_req_t = sbr_obi_req_t,
  parameter type                obi_rsp_t = sbr_obi_rsp_t
) (
  input  logic        clk_i,
  input  logic        rst_ni,
  input  obi_req_t    obi_req_i,
  output obi_rsp_t    obi_rsp_o,

  // Entradas dos sensores (vindas do user_domain -> croc_soc)
  input  logic [31:0] alarm_f_i,
  input  logic [31:0] alarm_rf_i,
  input  logic [(cf_math_pkg::idx_width(NumXbarSbr)*NumXbarManagers)+cf_math_pkg::idx_width(NumPeriphs)-1:0]       alarm_obi_dmx_i,
  input  logic [19-1:0]        alarm_uart_i
);

  logic [31:0] rsp_data;
  logic        req_q;
  logic [31:0] addr_q;
  logic [ObiCfg.IdWidth-1:0] id_q;

  // 1. Grant Imediato
  assign obi_rsp_o.gnt = obi_req_i.req;

  // 2. Captura (Request)
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      req_q  <= '0;
      addr_q <= '0;
      id_q   <= '0;
    end else begin
      req_q  <= obi_req_i.req;
      addr_q <= obi_req_i.a.addr;
      id_q   <= obi_req_i.a.aid;
    end
  end


  always_comb begin
    // (Offset 0x00) -> Lê Sensor F
    // (Offset 0x04) -> Lê Sensor RF
    // (Offset 0x08) -> Lê Sensor OBI DMX 
    // (Offset 0x0C) -> Lê Sensor UART

    case(addr_q[3:0])
      4'h0: begin
        rsp_data = alarm_f_i;
      end
      4'h4: begin
        rsp_data = alarm_rf_i;
      end
      4'h8: begin
        rsp_data = {20'd0, alarm_obi_dmx_i};
      end
      4'hC: begin
        rsp_data = {13'd0, alarm_uart_i};
      end
      
      default: begin
        rsp_data = '0;
      end
    endcase
  end

  // 4. Resposta (Response)
  always_comb begin
    obi_rsp_o.r.rdata      = rsp_data;
    obi_rsp_o.r.rid        = id_q;
    obi_rsp_o.r.err        = 1'b0;
    obi_rsp_o.r.r_optional = '0;
    obi_rsp_o.rvalid       = req_q;
  end

endmodule