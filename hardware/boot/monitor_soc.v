// ULX3S 85F 25MHz monitor platform. A small hardware boot target, distinct from
// the QEMU virt Sv39 kernel. Fixed ROM/RAM; no external memory or privileged ISA.
module omega_monitor_soc #(parameter ROM_FILE="monitor.hex",parameter CLOCK_HZ=25000000,parameter BAUD=115200)
 (input wire clk_25mhz, input wire reset_n,output wire ftdi_rxd,output wire trapped);
 localparam DIVISOR=CLOCK_HZ/BAUD;
 reg [31:0] rom[0:127];reg [63:0] ram[0:15];
 reg [3:0] startup=0;
 wire reset=!reset_n || startup!=15;
 reg [9:0] tx=10'h3ff;reg [3:0] bits=0;reg [31:0] ticks=0;
 wire busy=bits!=0;
 wire [63:0] pc,address,wdata;wire [7:0] mask;
 wire request,write;
 wire fetch_fault=pc<64'h80000000 || pc>=64'h80000200;
 wire [31:0] ins=fetch_fault?32'b0:rom[pc[8:2]];
 wire is_ram=address>=64'h1000000 && address<64'h1000080;
 wire is_rom=address>=64'h80000000 && address<64'h80000200;
 wire is_uart=address==64'h10000000;
 wire is_status=address==64'h10000008;
 wire fault=!(is_ram || is_uart || (!write && (is_status || is_rom)));
 wire ready=!(is_uart && write && busy);
 wire [63:0] rdata=is_ram?ram[address[6:3]]:is_status?{63'b0,busy}:
   is_rom?{rom[{address[8:3],1'b1}],rom[{address[8:3],1'b0}]}:64'b0;
 integer j;
 initial begin
  // The generator emits all 128 words. A preceding zero-initialization loop
  // conflicts with readmemh initialization in synthesis (though not simulation).
  $readmemh(ROM_FILE,rom);
 end
 always @(posedge clk_25mhz)begin
  if(startup!=15)startup<=startup+1;
  if(reset)begin
   tx<=10'h3ff;bits<=0;ticks<=0;
   for(j=0;j<16;j=j+1)ram[j]<=0;
  end else begin
   if(bits!=0)begin
    if(ticks==DIVISOR-1)begin tx<={1'b1,tx[9:1]};bits<=bits-1;ticks<=0;end
    else ticks<=ticks+1;
   end
   if(request && ready && !fault)begin
    if(write && is_ram)for(j=0;j<8;j=j+1)if(mask[j])ram[address[6:3]][j*8+:8]<=wdata[j*8+:8];
    if(write && is_uart)begin tx<={1'b1,wdata[7:0],1'b0};bits<=10;ticks<=0;end
   end
  end
 end
 assign ftdi_rxd=tx[0];
 omega_rv64_core cpu(clk_25mhz,reset,pc,ins,fetch_fault,request,write,address,wdata,mask,rdata,ready,fault,trapped);
endmodule
