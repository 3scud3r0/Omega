// FPGA-only power-on initialized divider. External reset remains synchronous
// to the derived core clock. Board 25MHz, core 6.25MHz; no false-path exception.
module ulx3s_monitor_top(input wire clk_25mhz,input wire reset_n,
 output wire ftdi_rxd,output wire trapped);
 reg [1:0] divider=0;
 always @(posedge clk_25mhz)divider<=divider+1;
 wire core_clk=divider[1];
 omega_monitor_soc #(.CLOCK_HZ(6250000),.BAUD(115200)) core(core_clk,reset_n,ftdi_rxd,trapped);
endmodule
