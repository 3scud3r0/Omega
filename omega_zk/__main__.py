"""Explicit local ZK execution commands; no automatic proof acceptance/promotion."""
import argparse
import json
from pathlib import Path
from .execution import Engine


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    compile=sub.add_parser('compile');compile.add_argument('source',type=Path)
    compile.add_argument('--result',type=int,required=True);compile.add_argument('--fuel',type=int,default=1000)
    compile.add_argument('--output',type=Path,required=True)
    prove=sub.add_parser('prove');prove.add_argument('program',type=Path);prove.add_argument('private',type=Path)
    prove.add_argument('--output',type=Path,required=True)
    verify=sub.add_parser('verify');verify.add_argument('proof',type=Path)
    verify.add_argument('--image-id',required=True);verify.add_argument('--journal',type=Path,required=True)
    args=parser.parse_args();engine=Engine(args.tool)
    if args.command=='compile':
        if args.output.exists():raise FileExistsError(args.output)
        p=engine.compile(args.source.read_text(),args.result,fuel=args.fuel)
        image_id=engine.image_id(p)
        args.output.mkdir(parents=True)
        (args.output/'guest.elf').write_bytes(p.elf);(args.output/'journal.json').write_bytes(p.journal)
        (args.output/'image-id.txt').write_text(image_id+'\n')
        print(json.dumps({'image_id':image_id,'output':str(args.output),'proof_generated':False}))
    elif args.command=='prove':
        from .execution import Program
        if args.output.exists():raise FileExistsError(args.output)
        private=json.loads(args.private.read_text());journal=(args.program/'journal.json').read_bytes()
        p=Program((args.program/'guest.elf').read_bytes(),journal,(),json.loads(journal)['fuel'])
        proof,metrics=engine.prove(p,private)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('xb') as out:out.write(proof)
        print(json.dumps(metrics))
    else:print(json.dumps(engine.verify(args.proof.read_bytes(),args.image_id,args.journal.read_bytes())))


if __name__=='__main__':main()
