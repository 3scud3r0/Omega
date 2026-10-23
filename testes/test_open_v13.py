import copy
import json
import tempfile
import unittest
from pathlib import Path
from omega_open import logic
from omega_open.engine import build,audit,export,audit_directory,verify_chain
from omega_open.checker import verify_solution, validate_task


def task(name,n,fn):
    return {'id':name,'arity':n,'outputs':[int(fn(i)) for i in range(1<<n)]}


class TestOpenOmega(unittest.TestCase):
    def setUp(self):
        self.tasks=[
            task('paridade_3',3,lambda i:i.bit_count()%2),
            task('majoria_3',3,lambda i:i.bit_count()>=2),
            task('e_4',4,lambda i:i==15),
            task('ou_4',4,lambda i:i!=0),
            task('mux_3',3,lambda i:(i>>1 & 1) if i&1 else (i>>2 & 1)),
            task('paridade_4',4,lambda i:i.bit_count()%2),
        ]
        self.train=['paridade_3','majoria_3','e_4','mux_3']

    def test_synthesis_every_strategy(self):
        for n in range(5):
            for code in range(min(1<<(1<<n),16)):
                table=[(code>>i)&1 for i in range(1<<n)]
                for name,e in logic.candidates(table,n,3):
                    self.assertEqual(logic.truth_table(e,n),table,(n,name))

    def test_certified_evolution(self):
        doc=build(self.tasks,self.train,generations=2)
        self.assertTrue(verify_chain(doc))
        self.assertTrue(audit(doc)['valid'])
        self.assertLessEqual(doc['generations'][-1]['training_cost'][0],doc['generations'][0]['training_cost'][0])

    def test_temper_attempts(self):
        doc=build(self.tasks,self.train,generations=1)
        changes=[
            lambda x:x['tasks'][0]['outputs'].__setitem__(0,1-x['tasks'][0]['outputs'][0]),
            lambda x:x['generations'][0]['solutions']['paridade_3']['ast'].__setitem__(0,'unknown'),
            lambda x:x['generations'][0].__setitem__('training_cost',[0,0]),
            lambda x:x['generations'][0].__setitem__('weights',[10,0,0]),
        ]
        for change in changes:
            bad=copy.deepcopy(doc);change(bad)
            self.assertFalse(verify_chain(bad))

    def test_dir_audit(self):
        doc=build(self.tasks,self.train,generations=1)
        with tempfile.TemporaryDirectory() as td:
            export(doc,td)
            self.assertTrue(audit_directory(td)['valid'])
            path=Path(td)/'politica_ativa.omega'
            path.write_text('malicioso',encoding='utf-8')
            with self.assertRaises(ValueError):audit_directory(td)

    def test_arbitrary_arity_and_budget(self):
        t=task('parity7',7,lambda x:x.bit_count()%2)
        doc=build([t],['parity7'],generations=0,max_orders=1,max_rows=128)
        self.assertTrue(verify_chain(doc))
        with self.assertRaises(ValueError):build([t],['parity7'],max_rows=64)

    def test_reject_bad_task(self):
        bad=task('a',2,lambda i:i&1);bad['outputs']=[0,1]
        with self.assertRaises(ValueError):validate_task(bad)
        bad=task('a',2,lambda i:i&1);bad['outputs'][0]=True
        with self.assertRaises(ValueError):validate_task(bad)

    def test_reject_fake_ast_even_new_hash(self):
        t=task('and2',2,lambda i:i==3)
        doc=build([t],['and2'],generations=0)
        sol=copy.deepcopy(doc['generations'][0]['solutions']['and2'])
        sol['ast']=['c',1]
        self.assertFalse(verify_solution(t,sol))

    def test_determinism(self):
        a=build(self.tasks,self.train,generations=1)
        b=build(self.tasks,self.train,generations=1)
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
