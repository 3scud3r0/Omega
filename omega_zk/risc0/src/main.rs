//! Independent, bounded local prover/verifier. Development/fake receipts are
//! disabled at compile time. Only RISC Zero SuccinctReceipt is accepted; the
//! older Omega AIR/FRI research certificate is not a supported proof format.
use bincode::Options;
use risc0_zkvm::{compute_image_id, sha::{Digest, Digestible}, InnerReceipt, MaybePruned, Output, Receipt};
use sha2::{Digest as HashDigest, Sha256};
use std::{error::Error, fs, io::Read, time::Instant};
#[cfg(feature="prover")]
use std::{io::Write,path::Path};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const PROOF_LIMIT: u64 = 4*1024*1024;
// zkVM 3.x proves the user ELF together with its compatibility kernel. Both
// are bound by image ID. The kernel ELF is embedded in a checksum-locked crate.
fn program(elf: &[u8]) -> Vec<u8> {
    risc0_binfmt::ProgramBinary::new(elf,risc0_zkos_v1compat::V1COMPAT_ELF).encode()
}

fn read(path: &str, limit: u64) -> Result<Vec<u8>> {
    let f=fs::File::open(path)?;
    if !f.metadata()?.is_file() || f.metadata()?.len()>limit { return Err("Input size/type limit".into()); }
    let mut bytes=Vec::new(); f.take(limit+1).read_to_end(&mut bytes)?;
    if bytes.len() as u64>limit { return Err("Input byte limit".into()); }
    Ok(bytes)
}
#[cfg(feature="prover")]
fn save(path: &str, bytes: &[u8]) -> Result<()> {
    let mut f=fs::OpenOptions::new().write(true).create_new(true).open(path)?;
    f.write_all(bytes)?; f.sync_all()?; Ok(())
}
fn digest_bytes(raw: &[u8]) -> Digest {
    Digest::from_bytes(Sha256::digest(raw).into())
}
fn codec() -> impl Options {
    bincode::DefaultOptions::new().with_fixint_encoding().with_limit(PROOF_LIMIT).reject_trailing_bytes()
}
fn validate(receipt: &Receipt, id: Digest, journal: &[u8]) -> Result<()> {
    if !matches!(&receipt.inner, InnerReceipt::Succinct(_)) { return Err("Only real succinct STARK receipts accepted".into()); }
    receipt.verify(id)?;
    if receipt.journal.bytes!=journal { return Err("Expected public journal mismatch".into()); }
    Ok(())
}
fn main() {
    if let Err(error)=run() { eprintln!("omega-risc0: {error}"); std::process::exit(2); }
}
fn run() -> Result<()> {
    let args: Vec<String>=std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("image-id") if args.len()==3 => {
            let elf=program(&read(&args[2],1024*1024)?);
            println!("{}",compute_image_id(&elf)?);
        },
        #[cfg(feature="prover")]
        Some("execute") if args.len()==5 => {
            use risc0_zkvm::{default_executor,ExecutorEnv,ExitCode};
            let elf=program(&read(&args[2],1024*1024)?);
            let private=read(&args[3],32)?;
            if private.len()!=32 { return Err("Exactly eight private u32 words required".into()); }
            let journal=read(&args[4],1024)?;
            let env=ExecutorEnv::builder().write_slice(&private).session_limit(Some(1<<22)).segment_limit_po2(16).build()?;
            let session=default_executor().execute(env,&elf)?;
            if session.exit_code!=ExitCode::Halted(0) || session.journal.bytes!=journal {
                return Err("Guest did not establish the expected statement".into());
            }
            println!("{}",serde_json::json!({"executed":true,"proof_generated":false}));
        },
        Some("output-digest") if args.len()==3 => {
            let journal=read(&args[2],1024)?;
            let output=Output { journal:MaybePruned::Pruned(digest_bytes(&journal)), assumptions:MaybePruned::Pruned(Digest::ZERO) };
            println!("{}",hex::encode(output.digest().as_bytes()));
        },
        Some("verify") if args.len()==5 => {
            let bytes=read(&args[2],PROOF_LIMIT)?;
            let raw_id=hex::decode(&args[3])?;
            let id=Digest::try_from(raw_id.as_slice())?;
            let journal=read(&args[4],1024)?;
            let started=Instant::now();
            let receipt: Receipt=codec().deserialize(&bytes)?;
            validate(&receipt,id,&journal)?;
            println!("{}",serde_json::json!({"valid":true,"scheme":"risc0-succinct-stark-3.0.3","bytes":bytes.len(),"verify_us":started.elapsed().as_micros()}));
        },
        #[cfg(feature="prover")]
        Some("prove") if args.len()==6 => {
            use risc0_zkvm::{default_prover,ExecutorEnv,ProverOpts};
            rayon::ThreadPoolBuilder::new().num_threads(2).build_global()?;
            let elf=program(&read(&args[2],1024*1024)?);
            let private=read(&args[3],32)?;
            if private.len()!=32 { return Err("Exactly eight private u32 words required".into()); }
            let journal=read(&args[4],1024)?;
            if Path::new(&args[5]).exists() { return Err("Fresh proof output required".into()); }
            let id=compute_image_id(&elf)?;
            let env=ExecutorEnv::builder().write_slice(&private).session_limit(Some(1<<22)).segment_limit_po2(16).build()?;
            let started=Instant::now();
            let result=default_prover().prove_with_opts(env,&elf,&ProverOpts::succinct())?;
            let elapsed=started.elapsed().as_millis();
            validate(&result.receipt,id,&journal)?;
            let bytes=codec().serialize(&result.receipt)?;
            save(&args[5],&bytes)?;
            println!("{}",serde_json::json!({"valid":true,"scheme":"risc0-succinct-stark-3.0.3","image_id":id.to_string(),"bytes":bytes.len(),"prove_ms":elapsed}));
        },
        _ => return Err("Usage: image-id ELF | output-digest JOURNAL | execute ELF PRIVATE32 JOURNAL | prove ELF PRIVATE32 JOURNAL PROOF | verify PROOF IMAGE_ID JOURNAL".into()),
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use risc0_zkvm::{FakeReceipt,ReceiptClaim};
    #[test]
    fn fake_receipt_is_never_a_proof() {
        let claim=ReceiptClaim::ok(Digest::ZERO,Vec::<u8>::new());
        let fake=Receipt::new(InnerReceipt::Fake(FakeReceipt::new(claim)),Vec::new());
        assert!(validate(&fake,Digest::ZERO,&[]).is_err());
        let wire=codec().serialize(&fake).unwrap();
        let roundtrip:Receipt=codec().deserialize(&wire).unwrap();
        assert!(validate(&roundtrip,Digest::ZERO,&[]).is_err());
        let mut trailing=wire;trailing.push(0);
        assert!(codec().deserialize::<Receipt>(&trailing).is_err());
    }
    #[test]
    fn malformed_receipts_fail_deserialization() {
        for raw in [vec![],vec![0;64],vec![255;4096]] {
            assert!(codec().deserialize::<Receipt>(&raw).is_err());
        }
    }
}
