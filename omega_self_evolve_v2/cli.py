import argparse,json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .cycle import evolve_from_receipt


def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega bootstrap-cycle')
    parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--public-key',type=Path,required=True)
    parser.add_argument('--lhs',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--install',action='store_true');parser.add_argument('--commit',action='store_true');parser.add_argument('--replace-source',action='store_true')
    args=parser.parse_args(argv)
    receipt=json.loads(args.receipt.read_text());key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(args.public_key.read_text().strip()))
    result=evolve_from_receipt(args.lhs,receipt,args.receipt.parent,args.output,public_key=key,install=args.install,commit=args.commit,replace_source=args.replace_source)
    print(json.dumps({'fixed_point':result['bootstrap']['fixed_point'],'objective':result['objective'],'runtime_epoch':result.get('runtime_epoch')},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
