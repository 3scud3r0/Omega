// Iterative Stein GCD: one subtraction/shift per cycle, ready/valid handshake.
module gcd_stein #(parameter W=16)(
 input wire clk,reset,start,input wire [W-1:0] a,b,
 output wire ready,output reg valid,output reg [W-1:0] result);
 reg busy;reg [W-1:0] u,v;integer shifts;
 assign ready=!busy;
 always @(posedge clk) begin
  if(reset)begin busy<=0;valid<=0;result<=0;u<=0;v<=0;shifts<=0;end
  else begin
   valid<=0;
   if(start&&!busy)begin u<=a;v<=b;shifts<=0;busy<=1;end
   else if(busy)begin
    if(u==0||v==0)begin result<=(u|v)<<shifts;busy<=0;valid<=1;end
    else if(!u[0]&&!v[0])begin u<=u>>1;v<=v>>1;shifts<=shifts+1;end
    else if(!u[0])u<=u>>1;
    else if(!v[0])v<=v>>1;
    else if(u>v)u<=u-v;
    else v<=v-u;
   end
  end
 end
endmodule
