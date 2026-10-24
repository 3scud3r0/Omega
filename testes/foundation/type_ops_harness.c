#include "runtime.h"
int main(int argc,char **argv) {
  o_init(argc,argv);
  if(argc!=4)o_die("operator and two operands required");
  V a=o_parsejson(o_str(argv[2])),b=o_parsejson(o_str(argv[3])),r=NULL;
  const char *op=argv[1];
  if(!strcmp(op,"+"))r=o_add(a,b);
  else if(!strcmp(op,"-"))r=o_sub(a,b);
  else if(!strcmp(op,"*"))r=o_mul(a,b);
  else if(!strcmp(op,"/"))r=o_div(a,b);
  else if(!strcmp(op,"%"))r=o_mod(a,b);
  else if(!strcmp(op,"<"))r=o_lt(a,b);
  else if(!strcmp(op,"<="))r=o_le(a,b);
  else if(!strcmp(op,">"))r=o_gt(a,b);
  else if(!strcmp(op,">="))r=o_ge(a,b);
  else if(!strcmp(op,"=="))r=o_eq(a,b);
  else if(!strcmp(op,"!="))r=o_ne(a,b);
  else if(!strcmp(op,"&&"))r=o_bool(o_truth(a)&&o_truth(b));
  else if(!strcmp(op,"||"))r=o_bool(o_truth(a)||o_truth(b));
  else o_die("unknown operator");
  o_print(o_json(r));return 0;
}
