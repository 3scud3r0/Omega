// Continued-fraction convergents / Stern-Brocot semiconvergent boundary.
// Unsigned magnitude interface. Signedness is handled by the ALU. Dividers
// are combinational: this reference RTL makes no frequency/area guarantee.
module stern_brocot #(parameter IW=34,OW=16)(
 input wire [IW-1:0] numerator,denominator,
 input wire [OW-1:0] max_denominator,
 output reg [OW-1:0] p,q,output reg error,approximate,
 output reg [IW+OW:0] delta_numerator,delta_denominator);
 localparam T=2*IW+2*OW+4;
 reg [T-1:0] n,d,p0,p1,q0,q1,a,q2,p2,k,bp,bq,lp,lq,e1,e2,original_n,original_d;
 reg finished;integer i;
 always @* begin
  p=0;q=1;error=0;approximate=0;delta_numerator=0;delta_denominator=1;
  n=numerator;d=denominator;original_n=n;original_d=d;
  p0=0;p1=1;q0=1;q1=0;a=0;q2=0;p2=0;k=0;bp=0;bq=1;lp=0;lq=1;e1=0;e2=0;finished=0;
  if(d==0||max_denominator==0)begin error=1;finished=1;end
  for(i=0;i<2*IW+2;i=i+1)begin
   if(!finished)begin
    if(d==0)begin bp=p1;bq=q1;finished=1;end
    else begin
     a=n/d;q2=q0+a*q1;p2=p0+a*p1;
     if(q2>max_denominator)begin
      k=(max_denominator-q0)/q1;lp=p0+k*p1;lq=q0+k*q1;
      e1=(original_n*lq>=lp*original_d)?original_n*lq-lp*original_d:lp*original_d-original_n*lq;
      e2=(original_n*q1>=p1*original_d)?original_n*q1-p1*original_d:p1*original_d-original_n*q1;
      // Tie goes to the convergent, as Fraction.limit_denominator does.
      if(e2*lq<=e1*q1)begin bp=p1;bq=q1;end else begin bp=lp;bq=lq;end
      finished=1;
     end else begin
      p0=p1;p1=p2;q0=q1;q1=q2;k=n-a*d;n=d;d=k;
     end
    end
   end
  end
  if(!finished||bp>((1<<(OW-1))-1)||bq==0||bq>max_denominator)error=1;
  if(!error)begin
   p=bp;q=bq;
   delta_numerator=(original_n*bq>=bp*original_d)?original_n*bq-bp*original_d:bp*original_d-original_n*bq;
   delta_denominator=original_d*bq;approximate=(delta_numerator!=0);
  end
 end
endmodule
