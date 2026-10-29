"""Instrument the exact static-scale edge emitter with a bounded C trace ring."""
from pathlib import Path
import re
from omega.edge import emit as emit_edge


def emit(graph,input_bounds,output_bounds,directory,*,input_scale=1):
    result=emit_edge(graph,input_bounds,output_bounds,directory,input_scale=input_scale)
    root=Path(directory);source=Path(result['source']);lines=source.read_text().splitlines()
    declarations=[]
    for index,line in enumerate(lines):
        match=re.search(r'\b(?:const\s+)?int64_t x(\d+)\s*=',line)
        if match:declarations.append((index,int(match.group(1))))
    output=next(i for i,line in enumerate(lines) if 'output[0]' in line)
    insertions={}
    for position,(start,node) in enumerate(declarations):
        end=declarations[position+1][0] if position+1<len(declarations) else output
        op=1 if node<graph['inputs'] else 7 if graph['nodes'][node-graph['inputs']]['op']=='relu' else 8
        branch='0' if op!=7 else f'(x{graph["nodes"][node-graph["inputs"]]["input"]}>0)'
        insertions.setdefault(end,[]).append(f'  if (omega_trace_record(trace, cycle, {node}, {op}, {branch}, x{node}, {result["node_scales"][node]}ULL)) return -3;')
    text=['#include "proof_envelope.h"']
    for i,line in enumerate(lines):
        text.extend(insertions.get(i,[]))
        text.append(line.replace('int omega_edge(const int64_t *input, int64_t *output) {',
                    'int omega_edge_traced(const int64_t *input, int64_t *output, OmegaTraceRing *trace, uint64_t cycle) {'))
    source.write_text('\n'.join(text)+'\n')
    for name in ('proof_envelope.h','glass_box_trace.c'):(root/name).write_bytes(Path(__file__).with_name(name).read_bytes())
    return {**result,'trace_event_count':len(declarations),'trace_storage':'caller-owned fixed-capacity circular buffer; overwrites count as dropped',
            'trace_runtime':str(root/'glass_box_trace.c')}
