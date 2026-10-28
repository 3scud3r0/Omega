"""The CLI prepares artifacts only; external dispatch requires a host instance."""
import argparse,json
from pathlib import Path
from .policy import Policy
from .actions import prepare

def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega action')
    parser.add_argument('policy',type=Path);parser.add_argument('state',type=Path);parser.add_argument('proposal',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    # This demonstrator explicitly produces an ephemeral public identity. It
    # cannot mint a host capability or dispatch an external effect.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key=Ed25519PrivateKey.generate()
    bundle=prepare(Policy(json.loads(args.policy.read_text())),json.loads(args.state.read_text()),json.loads(args.proposal.read_text()),signing_key=key)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'action.omega').write_text(bundle['program']);(args.output/'action.lean').write_text(bundle['proof'])
    (args.output/'action.json').write_text(json.dumps(bundle,sort_keys=True,indent=2)+'\n')
    (args.output/'public-key.hex').write_text(key.public_key().public_bytes_raw().hex()+'\n')
    print(json.dumps({'subject':bundle['subject'],'external_effects':False}));return 0
