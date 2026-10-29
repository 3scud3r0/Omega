"""Explicit foreign numerical models and reviewable native source output."""
import argparse,json
from pathlib import Path
from .frontends import python_function,c_function,wasm_function,save


def main(argv=None):
    p=argparse.ArgumentParser(prog='omega ingest');sub=p.add_subparsers(dest='language',required=True)
    for name in ('python','c','wasm'):
        sp=sub.add_parser(name);sp.add_argument('source',type=Path);sp.add_argument('--function',required=True);sp.add_argument('--output',type=Path,required=True)
        if name!='wasm':sp.add_argument('--rational-reals',action='store_true',help='Explicitly change float semantics to rational real arithmetic')
    neural=sub.add_parser('onnx');neural.add_argument('source',type=Path);neural.add_argument('--output',type=Path,required=True);neural.add_argument('--allow-approx',action='store_true');neural.add_argument('--precision-bits',type=int,default=32)
    tensor=sub.add_parser('safetensors');tensor.add_argument('source',type=Path)
    args=p.parse_args(argv)
    try:
        if args.language=='safetensors':
            from .tensors import safetensors
            output={name:{'shape':t.shape,'weights':[str(x) for x in t.values]} for name,t in safetensors(args.source).items()}
        else:
            if args.language=='python':result=python_function(args.source,args.function,rational_reals=args.rational_reals)
            elif args.language=='c':result=c_function(args.source,args.function,rational_reals=args.rational_reals)
            elif args.language=='wasm':result=wasm_function(args.source,args.function)
            else:
                from .tensors import onnx
                result=onnx(args.source,allow_approx=args.allow_approx,precision_bits=args.precision_bits)
            output=save(result,args.output)
        print(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2));return 0
    except (ValueError,RuntimeError,OSError) as error:p.exit(1,str(error)+'\n')


if __name__=='__main__':raise SystemExit(main())
