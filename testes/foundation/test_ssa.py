from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random

import pytest

from omega.ssa import Value,Block,Terminator,Graph,analyze,verify_analysis,analyze_tensor,tensor_graph
from omega.typesystem import RATIONAL,NumericType,TypeCheckError
from omega.typed_ir import TypedIR

ROOT=Path(__file__).resolve().parents[2]


def v(name,op,args=(),incoming=(),literal=None,annotation=RATIONAL):
    return Value(name,op,tuple(args),annotation,tuple(incoming),literal)


def diamond():
    return Graph('entry',(
        Block('entry',(v('condition','input'),),Terminator('branch',('left','right'),('condition',))),
        Block('left',(v('a','num',literal='1'),),Terminator('jump',('merge',))),
        Block('right',(v('b','num',literal='2'),),Terminator('jump',('merge',))),
        Block('merge',(v('result','phi',incoming=(('left','a'),('right','b'))),),Terminator('return',(),('result',))),
    ))


def loop():
    return Graph('entry',(
        Block('entry',(v('zero','num',literal='0'),v('one','num',literal='1'),v('limit','input')),Terminator('jump',('header',))),
        Block('header',(v('i','phi',incoming=(('entry','zero'),('body','next_value'))),v('condition','-',('limit','i'))),
              Terminator('branch',('body','exit'),('condition',))),
        Block('body',(v('next_value','+',('i','one')),),Terminator('jump',('header',))),
        Block('exit',(),Terminator('return',(),('i',))),
    ))


def test_diamond_phi_operands_are_uses_on_predecessor_edges():
    graph=diamond();report=analyze(graph)
    assert report['blocks']['merge']['dominators']==['entry','merge']
    assert report['blocks']['left']['dominance_frontier']==['merge']
    assert report['values']['a']['uses']==[{'block':'merge','index':0,'operand':0,'edge':'left'}]
    assert verify_analysis(graph,report)
    assert analyze(replace(graph,blocks=tuple(reversed(graph.blocks))))==report


def test_loop_backedge_is_valid_and_header_is_its_own_frontier():
    report=analyze(loop())
    assert report['blocks']['body']['immediate_dominator']=='header'
    assert report['blocks']['header']['dominance_frontier']==['header']
    assert report['blocks']['body']['dominance_frontier']==['header']
    assert report['values']['next_value']['uses'][0]['edge']=='body'


@pytest.mark.parametrize('mutation',[
    lambda g:replace(g,entry='missing'),
    lambda g:replace(g,entry=[]),
    lambda g:replace(g,blocks=g.blocks+(g.blocks[1],)),
    lambda g:replace(g,blocks=g.blocks+(Block('unreachable',(),Terminator('return')),)),
    lambda g:replace(g,blocks=(replace(g.blocks[0],terminator=Terminator('jump',('missing',))),*g.blocks[1:])),
    lambda g:replace(g,blocks=(g.blocks[0],replace(g.blocks[1],values=(v('condition','num',literal='0'),)),*g.blocks[2:])),
    lambda g:replace(g,blocks=(g.blocks[0],g.blocks[1],replace(g.blocks[2],values=(v('b','+',('a','condition')),)),g.blocks[3])),
    lambda g:replace(g,blocks=(*g.blocks[:3],replace(g.blocks[3],values=(v('result','phi',incoming=(('left','a'),)),)))),
    lambda g:replace(g,blocks=(*g.blocks[:3],replace(g.blocks[3],values=(v('result','phi',incoming=(('left','a'),('right','a'))),)))),
    lambda g:replace(g,blocks=(*g.blocks[:3],replace(g.blocks[3],values=(v('result','phi',incoming=(('left','a'),('left','a'))),)))),
])
def test_malformed_cfg_ssa_and_non_dominating_uses_rejected(mutation):
    with pytest.raises(TypeCheckError):analyze(mutation(diamond()))


def test_forward_use_phi_order_and_incorrect_type_rejected():
    bad=(v('answer','+',('later','later')),v('later','num',literal='1'))
    with pytest.raises(TypeCheckError):analyze(Graph('entry',(Block('entry',bad,Terminator('return')),)))
    values=(v('x','num',literal='1'),v('y','relu',('x',),annotation=NumericType((2,))))
    with pytest.raises(TypeCheckError):analyze(Graph('entry',(Block('entry',values,Terminator('return')),)))
    graph=loop();header=graph.blocks[1]
    with pytest.raises(TypeCheckError):analyze(replace(graph,blocks=(graph.blocks[0],replace(header,values=tuple(reversed(header.values))),*graph.blocks[2:])))


def test_dominators_and_frontiers_match_path_removal_oracle_on_generated_cfgs():
    rng=random.Random(15)
    for _ in range(80):
        count=rng.randrange(2,11);names=['b'+str(i) for i in range(count)];blocks=[]
        for i,name in enumerate(names):
            values=(v('condition','input'),) if i==0 else ()
            if i==count-1:term=Terminator('return',(),('condition',))
            else:
                targets=tuple(sorted({names[i+1],rng.choice(names[1:])}))
                term=Terminator('jump',targets) if len(targets)==1 else Terminator('branch',targets,('condition',))
            blocks.append(Block(name,values,term))
        graph=Graph('b0',tuple(blocks));report=analyze(graph)
        def without(removed):
            reachable=set();pending=['b0']
            while pending:
                name=pending.pop()
                if name==removed or name in reachable:continue
                reachable.add(name);pending.extend(report['blocks'][name]['successors'])
            return reachable
        oracle={name:{d for d in names if name not in without(d)} for name in names}
        for name in names:
            assert set(report['blocks'][name]['dominators'])==oracle[name]
            expected={target for target in names if (name==target or name not in oracle[target]) and
                      any(name in oracle[p] for p in report['blocks'][target]['predecessors'])}
            assert set(report['blocks'][name]['dominance_frontier'])==expected


def test_forged_dominator_and_bool_as_integer_reports_rejected():
    graph=diamond();report=analyze(graph)
    changed=deepcopy(report);changed['blocks']['merge']['dominators'].append('left')
    with pytest.raises(TypeCheckError):verify_analysis(graph,changed)
    changed=deepcopy(report);changed['values']['a']['index']=False
    with pytest.raises(TypeCheckError):verify_analysis(graph,changed)


def test_tensor_corpus_def_use_consistent_and_bound_to_validated_ir():
    from omega_selfhost.driver import compile_ir
    cases=json.loads((ROOT/'testes/corpus.json').read_text())['cases']
    for case in cases:
        if case['language']!='tensor' or case['expected']=='compile_reject':continue
        ir=TypedIR.from_legacy(compile_ir(ROOT/case['path']))
        result=analyze_tensor(ir)
        assert result['typed_ir_sha256']==ir.sha256
        assert len(result['values'])==len(ir.legacy()['nos'])
        pure=analyze(tensor_graph(ir))
        for name,value in pure['values'].items():
            for use in value['uses']:assert value['index']<use['index']
        assert verify_analysis(tensor_graph(ir),pure)


def test_cli_reports_explicit_single_evaluation_scope(capsys):
    from omega.cli import principal
    assert principal(['native-ssa',str(ROOT/'exemplos/rede_profunda.omega')])==0
    report=json.loads(capsys.readouterr().out)
    assert report['format']=='omega-ssa-analysis-1'
    assert 'mutable commands are not lowered' in report['scope']
    assert report['blocks']['entry']['dominators']==['entry']
