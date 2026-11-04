// FPGA-only power-on initialized divider. Two flops synchronize the external
// button into the core clock domain. Board 25MHz, core 6.25MHz; no false paths.
module ulx3s_monitor_top(input wire clk_25mhz,input wire reset_n,
 output wire ftdi_rxd,output wire trapped);
 reg [1:0] divider=0;
 always @(posedge clk_25mhz)divider<=divider+1;
 wire core_clk=divider[1];
 (* ASYNC_REG="TRUE" *) reg [1:0] reset_sync=0;
 always @(posedge core_clk) reset_sync<={reset_sync[0],reset_n};
 omega_monitor_soc #(.CLOCK_HZ(6250000),.BAUD(115200)) core(core_clk,reset_sync[1],ftdi_rxd,trapped);
endmodule
