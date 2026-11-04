// Bounded exact unsigned rational addition: a/b + c/d. 8-bit inputs,
// 17-bit normalized outputs, iterative products/GCD/division. No DSP/divider.
// Error is explicit for a zero denominator. Inputs are sampled only on start
// when !busy. done is a one-cycle pulse; result remains stable until next start.
module qpu_exact(input wire clk, input wire reset, input wire start,
 input wire [7:0] a,b,c,d, output reg busy,done,error,
 output reg [16:0] numerator,denominator);
 reg [2:0] state;
 reg [4:0] count;
 reg [15:0] x1,x2,x3,p1,p2,p3;
 reg [7:0] y1,y2,y3;
 reg [16:0] raw_n,raw_d,g1,g2,gcd_value;
 reg [16:0] dividend,remainder,quotient;
 wire [17:0] trial={remainder,dividend[16]};
 wire [16:0] next_r=trial>={1'b0,gcd_value} ? trial-gcd_value : trial;
 wire [16:0] next_q={quotient[15:0],trial>={1'b0,gcd_value}};
 always @(posedge clk) begin
  done<=0;
  if(reset) begin
   state<=0; busy<=0; done<=0; error<=0; numerator<=0; denominator<=1;
   count<=0; x1<=0;x2<=0;x3<=0;p1<=0;p2<=0;p3<=0;
   y1<=0;y2<=0;y3<=0;raw_n<=0;raw_d<=0;g1<=0;g2<=0;
   gcd_value<=1;dividend<=0;remainder<=0;quotient<=0;
  end else case(state)
   0: if(start) begin
    error<=0; busy<=1;
    if(b==0 || d==0) begin error<=1;done<=1;busy<=0;end
    else begin
     x1<={8'b0,a}; y1<=d; x2<={8'b0,c};y2<=b;x3<={8'b0,b};y3<=d;
     p1<=0;p2<=0;p3<=0;count<=8;state<=1;
    end
   end
   1: begin
    if(y1[0]) p1<=p1+x1;
    if(y2[0]) p2<=p2+x2;
    if(y3[0]) p3<=p3+x3;
    x1<=x1<<1;x2<=x2<<1;x3<=x3<<1;
    y1<=y1>>1;y2<=y2>>1;y3<=y3>>1;
    count<=count-1;
    if(count==1) state<=2;
   end
   2: begin
    raw_n<={1'b0,p1}+{1'b0,p2};raw_d<={1'b0,p3};
    g1<={1'b0,p1}+{1'b0,p2};g2<={1'b0,p3};state<=3;
   end
   3: begin
    if(g1==0 || g1==g2) begin
     gcd_value<=g2;dividend<=raw_n;remainder<=0;quotient<=0;count<=17;state<=4;
    end else if(g1>g2) g1<=g1-g2;
    else g2<=g2-g1;
   end
   4: begin
    remainder<=next_r;quotient<=next_q;dividend<=dividend<<1;count<=count-1;
    if(count==1) begin
     numerator<=next_q;dividend<=raw_d;remainder<=0;quotient<=0;count<=17;state<=5;
    end
   end
   5: begin
    remainder<=next_r;quotient<=next_q;dividend<=dividend<<1;count<=count-1;
    if(count==1) begin denominator<=next_q;state<=0;busy<=0;done<=1;end
   end
   default: begin state<=0;busy<=0;error<=1;done<=1;end
  endcase
 end
endmodule
