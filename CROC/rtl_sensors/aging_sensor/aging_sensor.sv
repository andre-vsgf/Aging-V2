`timescale 1ns / 1ps

/* Instance example:
aging_sensor sensor_0(
    .sclk(soc_clk),
    .psclk(dpsclk),
    .in_sensor(o_critpath[0]),
    .reset(wiz_reset),
    .clk_en,
    .alarm(o_sensor[0]),
    .alarm_holder (o_sensor_holder[0]),
    .xor_out (),
    .ff1 (),
    .ff2 ()
    );
*/

module aging_sensor(
    input sclk,
    input  psclk, 
    input  in_sensor,
    input reset,
    input clk_en,
    output  alarm,
    //output ff1_out,
    output alarm_holder,
    //output wire ff1_out
    output xor_out,
    output ff1,
	output ff2
    );
	 
	 //wire xor_out;
	// wire ff1;
	// wire ff2;
	 wire and_out;
	 wire buff_out;
	
	assign ff1_out = ff2;
	
	/*(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	 LUT1_L #(.INIT(2'b10) // Specify LUT Contents
	)BUF1 (
	.LO(buff_out), // Connect to the output of a LUT
	.I0(and_out) // Connect to the input of a LUT
	);*/
	
	(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	LUT2_L #(
	.INIT(4'b0110) // Specify LUT Contents
	) XOR1 (
	.LO(xor_out), // LUT local output
	.I0(ff1), // LUT input
	.I1(ff2) // LUT input
	);
	
	/*(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	LUT2_L #(
	.INIT(4'b1000) // Specify LUT Contents
	) AND1 (
	.LO(and_out), // LUT local output
	.I0(clk_en), // LUT input
	.I1(xor_out) // LUT input
	);*/
	
	
	(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	FDCE #(
	.INIT(1'b0) // Initial value of register (1'b0 or 1'b1)
	) FF2 (
	.Q(ff2), // Data output
	.C(psclk), // Clock input
	.CE(1'b1), // Clock enable input
	.CLR(reset), // Asynchronous clear input
	.D(in_sensor) // Data input
	);
	
	(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	FDCE #(
	.INIT(1'b0) // Initial value of register (1'b0 or 1'b1)
	) FF1 (
	.Q(ff1), // Data output
	.C(sclk), // Clock input
	.CE(1'b1), // Clock enable input
	.CLR(reset), // Asynchronous clear input
	.D(in_sensor) // Data input
	);
	
	(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	FDCE #(
	.INIT(1'b0) // Initial value of register (1'b0 or 1'b1)
	) FF3 (
	.Q(alarm), // Data output
	.C(clk_en), // Clock input
	.CE(1'b1), // Clock enable input
	.CLR(reset), // Asynchronous clear input
	.D(xor_out) // Data input
	);
	
	(* AREA_GROUP = "sensor" *)
	(* U_SET= "sensor" *)
	(* dont_touch = "true" *)
	FDCE #(
	.INIT(1'b0) // Initial value of register (1'b0 or 1'b1)
	) FF_alarm_holder (
	.Q(alarm_holder), // Data output
	.C(alarm), // Clock input
	.CE(1'b1), // Clock enable input
	.CLR(reset), // Asynchronous clear input
	.D(1'b1) // Data input
	);

    //assign ff1_out = ff1;

endmodule