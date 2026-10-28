// Bounded rational reference ALU: 00 add, 01 subtract, 10 multiply, 11 divide.
// Operands exclude the most-negative signed numerator and use positive signed
// denominator range. Overflow/zero division trap; approximation raises IRQ.
module rational_alu #(parameter W=16)(
 input wire clk,reset,start,input wire [1:0] opcode,
 input wire signed [W-1:0] an,bn,input wire [W-1:0] ad,bd,max_denominator,
 output wire ready,output reg valid,error,irq,
 output reg signed [W-1:0] pn,output reg [W-1:0] pd,
 output reg [3*W+2:0] delta_numerator,delta_denominator);
 localparam IW=2*W+2;
 reg signed [IW-1:0] raw_n,signed_b;reg [IW-1:0] raw_d,mag,b_magnitude;
 reg negative,bad;wire [W-1:0] qp,qq;wire qe,qa;
 wire [IW+W:0] en,ed;
 assign ready=1'b1;
 stern_brocot #(.IW(IW),.OW(W)) quantizer(mag,raw_d,max_denominator,qp,qq,qe,qa,en,ed);
 always @* begin
  raw_n=0;raw_d=1;
  signed_b=bn;b_magnitude=signed_b<0?-signed_b:signed_b;
  bad=(ad==0||bd==0||ad[W-1]||bd[W-1]||an=={1'b1,{(W-1){1'b0}}}||bn=={1'b1,{(W-1){1'b0}}}||max_denominator==0||max_denominator[W-1]);
  case(opcode)
   0:begin raw_n=$signed(an)*$signed({1'b0,bd})+$signed(bn)*$signed({1'b0,ad});raw_d=ad*bd;end
   1:begin raw_n=$signed(an)*$signed({1'b0,bd})-$signed(bn)*$signed({1'b0,ad});raw_d=ad*bd;end
   2:begin raw_n=$signed(an)*$signed(bn);raw_d=ad*bd;end
   3:begin
    if(bn==0)bad=1;
    raw_n=$signed(an)*$signed({1'b0,bd});
    if(bn<0)raw_n=-raw_n;
    raw_d=ad*b_magnitude;
   end
  endcase
  negative=raw_n<0;mag=negative?-raw_n:raw_n;
 end
 always @(posedge clk)begin
  if(reset)begin valid<=0;error<=0;irq<=0;pn<=0;pd<=1;delta_numerator<=0;delta_denominator<=1;end
  else begin
   valid<=start;
   if(start)begin error<=bad||qe;irq<=!bad&&!qe&&qa;pn<=negative?-$signed(qp):$signed(qp);pd<=qq;delta_numerator<=en;delta_denominator<=ed;end
  end
 end
endmodule
