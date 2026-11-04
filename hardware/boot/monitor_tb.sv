`timescale 1ns/1ps
module monitor_tb;
 reg clk=0;reg reset_n=0;wire serial,trapped;
 integer count=0,i;reg [7:0] received;
 reg [8*26-1:0] expected="OMEGA RV64 MONITOR: 42 OK\n";
 always #5 clk=~clk;
 omega_monitor_soc #(.CLOCK_HZ(100),.BAUD(10)) dut(clk,reset_n,serial,trapped);
 initial begin #100;reset_n=1;end
 initial begin #2000000;$fatal(1,"Monitor serial timeout");end
 always @(posedge clk)if(trapped)$fatal(1,"Unexpected RV64 trap PC=%h ins=%h a=%h b=%h",dut.pc,dut.ins,dut.cpu.a,dut.cpu.b);
 initial begin
  wait(reset_n);
  repeat(26)begin
   @(negedge serial);repeat(15)@(posedge clk);
   for(i=0;i<8;i=i+1)begin received[i]=serial;repeat(10)@(posedge clk);end
   if(!serial)$fatal(1,"UART stop bit");
   $write("%c",received);
   // Compare exact transmitted bytes; no reliance on a success-looking log.
   if(received!==expected[(25-count)*8+:8])$fatal(1,"UART byte mismatch index %d",count);
   count=count+1;
  end
  $display("BOOT_SERIAL_VERIFIED");$finish;
 end
endmodule
