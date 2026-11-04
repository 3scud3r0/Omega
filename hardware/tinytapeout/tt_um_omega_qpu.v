// Tiny Tapeout standard pin wrapper for qpu_exact, not a fabricated chip.
// ui_in: byte data. uio_in[1:0]: command (0 reset frame, 1 push byte,
// 2 start, 3 read next byte). uio_in[2]: request toggle. uio_out[3]: ack
// toggle; [4]: protocol error; [5]: arithmetic error; [6]: valid; [7]: busy.
// A frame contains four bytes a,b,c,d for a/b+c/d. Six output bytes are
// numerator little-endian (3 bytes) followed by denominator (3 bytes).
module tt_um_omega_qpu(input wire [7:0] ui_in,output reg [7:0] uo_out,
 input wire [7:0] uio_in,output wire [7:0] uio_out,output wire [7:0] uio_oe,
 input wire ena,clk,rst_n);
 reg [7:0] args[0:3];reg [2:0] count,index;
 reg ack,start,protocol_error,valid,arithmetic_error;
 wire busy,done,error;wire [16:0] numerator,denominator;
 reg [16:0] saved_n,saved_d;
 integer i;
 assign uio_oe=8'hf8;
 assign uio_out={busy,valid,arithmetic_error,protocol_error,ack,3'b0};
 qpu_exact core(clk,!rst_n,start,args[0],args[1],args[2],args[3],busy,done,error,numerator,denominator);
 always @(posedge clk)begin
  start<=0;
  if(!rst_n)begin
   count<=0;index<=0;ack<=0;protocol_error<=0;valid<=0;arithmetic_error<=0;
   start<=0;uo_out<=0;saved_n<=0;saved_d<=1;
   for(i=0;i<4;i=i+1)args[i]<=0;
  end else begin
   if(done)begin valid<=!error;arithmetic_error<=error;saved_n<=numerator;saved_d<=denominator;index<=0;end
   if(ena && uio_in[2]!=ack)begin
    ack<=uio_in[2];
    if(busy || start)protocol_error<=1;
    else case(uio_in[1:0])
     0:begin count<=0;index<=0;protocol_error<=0;valid<=0;arithmetic_error<=0;uo_out<=0;end
     1:if(count<4)begin args[count]<=ui_in;count<=count+1;end else protocol_error<=1;
     2:if(count==4)begin start<=1;valid<=0;arithmetic_error<=0;index<=0;end else protocol_error<=1;
     3:if(valid && index<6)begin
      case(index)
       0:uo_out<=saved_n[7:0];1:uo_out<=saved_n[15:8];2:uo_out<={7'b0,saved_n[16]};
       3:uo_out<=saved_d[7:0];4:uo_out<=saved_d[15:8];5:uo_out<={7'b0,saved_d[16]};
      endcase
      index<=index+1;
     end else protocol_error<=1;
    endcase
   end
  end
 end
endmodule
