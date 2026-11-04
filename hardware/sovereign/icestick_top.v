// Autonomous board self-test: 1/3 + 1/6 = 1/2. LED1 indicates pass,
// LED2 failure, LED3 heartbeat, LED4 busy, LED5 initialized.
module icestick_top(input wire clki,output wire led1,led2,led3,led4,led5);
 reg [23:0] cycles=0;
 reg [3:0] startup=0;
 reg pass=0,fail=0;
 wire reset=startup<8;
 wire start=startup==9;
 wire busy,done,error;
 wire [16:0] n,d;
 always @(posedge clki) begin
  cycles<=cycles+1;
  if(startup!=15) startup<=startup+1;
  if(done) begin pass<=!error && n==1 && d==2;fail<=error || n!=1 || d!=2;end
 end
 qpu_exact core(clki,reset,start,8'd1,8'd3,8'd1,8'd6,busy,done,error,n,d);
 assign led1=pass;assign led2=fail;assign led3=cycles[23];assign led4=busy;assign led5=!reset;
endmodule
