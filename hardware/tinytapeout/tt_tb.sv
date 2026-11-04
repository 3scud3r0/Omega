`timescale 1ns/1ps
module tt_tb;
 reg clk=0,ena=1,rst_n=0;reg [7:0] ui=0,io=0;wire [7:0] out,status,oe;
 tt_um_omega_qpu dut(ui,out,io,status,oe,ena,clk,rst_n);
 always #5 clk=~clk;
 task command(input [1:0] cmd,input [7:0] data);
  begin @(negedge clk);ui=data;io[1:0]=cmd;io[2]=!io[2];
   @(posedge clk);#1;if(status[3]!==io[2])$fatal(1,"Missing ACK");
  end
 endtask
 task read_byte(input [7:0] expected);
  begin command(3,0);if(out!==expected)$fatal(1,"Result byte mismatch");end
 endtask
 initial begin #100000;$fatal(1,"QPU protocol timeout");end
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  if(oe!==8'hf8)$fatal(1,"Pin direction");
  command(0,0);command(1,1);command(1,3);command(1,1);command(1,6);command(2,0);
  wait(status[7]);wait(status[6] || status[5]);@(negedge clk);
  if(!status[6] || status[5:4]!=0)$fatal(1,"QPU execution status");
  read_byte(1);read_byte(0);read_byte(0);read_byte(2);read_byte(0);read_byte(0);
  command(3,0);if(!status[4])$fatal(1,"Overread accepted");
  command(0,0);command(2,0);if(!status[4])$fatal(1,"Partial frame accepted");
  command(0,0);command(1,1);command(1,0);command(1,1);command(1,6);command(2,0);
  wait(status[5]);if(status[6])$fatal(1,"Zero denominator accepted");
  $display("TINY_TAPEOUT_PROTOCOL_VERIFIED");$finish;
 end
endmodule
