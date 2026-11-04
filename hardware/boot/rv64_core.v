// Single-cycle RV64I monitor core. No privileged ISA, MMU, interrupts, M/A/C/F/D
// or Linux ABI. Unsupported encodings, misalignment and bus errors trap closed.
// Separate instruction/data ports; data ready may stall without side effects.
module omega_rv64_core(input wire clk, reset,
 output reg [63:0] pc, input wire [31:0] instruction, input wire fetch_fault,
 output reg mem_valid, mem_write, output reg [63:0] mem_address,mem_wdata,
 output reg [7:0] mem_mask, input wire [63:0] mem_rdata,
 input wire mem_ready,mem_fault, output reg trapped);
 reg [63:0] x[0:31];
 wire [6:0] opcode=instruction[6:0];
 wire [4:0] rd=instruction[11:7],rs1=instruction[19:15],rs2=instruction[24:20];
 wire [2:0] f3=instruction[14:12];
 wire [6:0] f7=instruction[31:25];
 wire [63:0] a=rs1==0?64'b0:x[rs1], b=rs2==0?64'b0:x[rs2];
 wire [63:0] imm_i={{52{instruction[31]}},instruction[31:20]};
 wire [63:0] imm_s={{52{instruction[31]}},instruction[31:25],instruction[11:7]};
 wire [63:0] imm_b={{51{instruction[31]}},instruction[31],instruction[7],instruction[30:25],instruction[11:8],1'b0};
 wire [63:0] imm_j={{43{instruction[31]}},instruction[31],instruction[19:12],instruction[20],instruction[30:21],1'b0};
 wire [63:0] imm_u={{32{instruction[31]}},instruction[31:12],12'b0};
 reg [63:0] result,next_pc,shifted;
 reg valid,write_rd,take_branch;
 integer i;
 always @* begin
  valid=1;write_rd=0;result=0;next_pc=pc+4;take_branch=0;
  mem_valid=0;mem_write=0;mem_address=0;mem_wdata=0;mem_mask=0;shifted=0;
  case(opcode)
   7'h37: begin write_rd=1;result=imm_u;end
   7'h17: begin write_rd=1;result=pc+imm_u;end
   7'h6f: begin write_rd=1;result=pc+4;next_pc=pc+imm_j;end
   7'h67: begin
    if(f3!=0) valid=0;
    write_rd=1;result=pc+4;next_pc=(a+imm_i)&~64'b1;
   end
   7'h63: begin
    case(f3)
     0:take_branch=a==b;1:take_branch=a!=b;
     4:take_branch=$signed(a)<$signed(b);5:take_branch=$signed(a)>=$signed(b);
     6:take_branch=a<b;7:take_branch=a>=b;
     default:valid=0;
    endcase
    if(take_branch) next_pc=pc+imm_b;
   end
   7'h13: begin
    write_rd=1;
    case(f3)
     0:result=a+imm_i;
     2:result={63'b0,$signed(a)<$signed(imm_i)};
     3:result={63'b0,a<imm_i};
     4:result=a^imm_i;6:result=a|imm_i;7:result=a&imm_i;
     1:begin result=a<<instruction[25:20];if(instruction[31:26]!=0)valid=0;end
     5:begin
      if(instruction[31:26]==0)result=a>>instruction[25:20];
      else if(instruction[31:26]==6'h10)result=$signed(a)>>>instruction[25:20];
      else valid=0;
     end
    endcase
   end
   7'h33: begin
    write_rd=1;
    case(f3)
     0:if(f7==0)result=a+b;else if(f7==7'h20)result=a-b;else valid=0;
     1:begin result=a<<b[5:0];if(f7!=0)valid=0;end
     2:begin result={63'b0,$signed(a)<$signed(b)};if(f7!=0)valid=0;end
     3:begin result={63'b0,a<b};if(f7!=0)valid=0;end
     4:begin result=a^b;if(f7!=0)valid=0;end
     5:if(f7==0)result=a>>b[5:0];else if(f7==7'h20)result=$signed(a)>>>b[5:0];else valid=0;
     6:begin result=a|b;if(f7!=0)valid=0;end
     7:begin result=a&b;if(f7!=0)valid=0;end
    endcase
   end
   7'h03: begin
    mem_valid=1;write_rd=1;mem_address=a+imm_i;
    shifted=mem_rdata>>{mem_address[2:0],3'b0};
    case(f3)
     0:result={{56{shifted[7]}},shifted[7:0]};
     1:begin result={{48{shifted[15]}},shifted[15:0]};if(mem_address[0])valid=0;end
     2:begin result={{32{shifted[31]}},shifted[31:0]};if(mem_address[1:0]!=0)valid=0;end
     3:begin result=shifted;if(mem_address[2:0]!=0)valid=0;end
     4:result={56'b0,shifted[7:0]};
     5:begin result={48'b0,shifted[15:0]};if(mem_address[0])valid=0;end
     6:begin result={32'b0,shifted[31:0]};if(mem_address[1:0]!=0)valid=0;end
     default:valid=0;
    endcase
   end
   7'h23: begin
    mem_valid=1;mem_write=1;mem_address=a+imm_s;
    mem_wdata=b<<{mem_address[2:0],3'b0};
    case(f3)
     0:mem_mask=8'b1<<mem_address[2:0];
     1:begin mem_mask=8'b11<<mem_address[2:0];if(mem_address[0])valid=0;end
     2:begin mem_mask=8'b1111<<mem_address[2:0];if(mem_address[1:0]!=0)valid=0;end
     3:begin mem_mask=8'hff;if(mem_address[2:0]!=0)valid=0;end
     default:valid=0;
    endcase
   end
   7'h0f:if(f3!=0 || rd!=0 || rs1!=0)valid=0; // FENCE only
   default:valid=0;
  endcase
  if(!valid || trapped || reset || fetch_fault || pc[1:0]!=0 || next_pc[1:0]!=0) mem_valid=0;
 end
 always @(posedge clk) begin
  if(reset) begin
   pc<=64'h80000000;trapped<=0;
   for(i=0;i<32;i=i+1)x[i]<=0;
  end else if(!trapped) begin
   if(fetch_fault || !valid || pc[1:0]!=0 || next_pc[1:0]!=0 || (mem_valid && mem_fault))trapped<=1;
   else if(!mem_valid || mem_ready)begin
    if(write_rd && rd!=0)x[rd]<=result;
    pc<=next_pc;
   end
  end
 end
endmodule
