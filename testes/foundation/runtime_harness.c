/* Fixed diagnostic target: inputs are data, never C source. */
#include "runtime.h"
int main(int argc, char **argv) {
  o_init(argc, argv);
  if (argc < 2) o_die("Mode required");
  if (!strcmp(argv[1], "json")) {
    if (argc != 3) o_die("Input required");
    o_print(o_json(o_parsejson(o_str(argv[2]))));
  } else if (!strcmp(argv[1], "number")) {
    if (argc != 3) o_die("Input required");
    o_print(o_text(o_num(argv[2])));
  } else if (!strcmp(argv[1], "cycle")) {
    V a=o_list();o_push(a,a);o_print(o_json(a));
  } else if (!strcmp(argv[1], "equalcycle")) {
    V a=o_list();o_push(a,a);o_print(o_eq(a,a));
  } else if (!strcmp(argv[1], "fuel")) {
    for (;;) o_tick();
  } else o_die("Unknown mode");
  return 0;
}
