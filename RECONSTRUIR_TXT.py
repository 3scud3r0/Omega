"""Reconstrói os arquivos da linguagem Ômega a partir do TXT consolidado.

Uso:
    python RECONSTRUIR_TXT.py Omega_CODIGO_INTEGRAL_v0_1_a_v1_2.txt destino/

Nenhum trecho do TXT é executado. Cada arquivo é validado por SHA-256.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

MARCADOR = b'OMEGA-DADOS-INICIO\n'
PREFIXO = b'OMEGA-FILE '
FIM = b'\nOMEGA-END\n'


def reconstruir(arquivo_txt: Path, destino: Path) -> int:
    bruto = arquivo_txt.read_bytes()
    comeco = bruto.find(MARCADOR)
    if comeco < 0:
        raise ValueError('TXT sem seção de dados')
    pos = comeco + len(MARCADOR)
    quantidade = 0
    while pos < len(bruto):
        if not bruto.startswith(PREFIXO, pos):
            if not bruto[pos:].strip():
                break
            raise ValueError('Cabeçalho de arquivo inválido no deslocamento '+str(pos))
        fim_cabecalho = bruto.index(b'\n',pos)
        registro = json.loads(bruto[pos+len(PREFIXO):fim_cabecalho].decode('utf-8'))
        nome = registro['caminho']
        path = PurePosixPath(nome)
        if (path.is_absolute() or '..' in path.parts or '\\' in nome or
                any(p in ('', '.') for p in path.parts)):
            raise ValueError('Caminho inseguro dentro do TXT')
        size = registro['bytes']
        if type(size) is not int or not 0 <= size <= 100_000_000:
            raise ValueError('Tamanho inválido de arquivo')
        start = fim_cabecalho + 1
        blob = bruto[start:start+size]
        if len(blob) != size or not bruto.startswith(FIM, start+size):
            raise ValueError('Arquivo truncado ou delimitador incorreto: '+nome)
        if hashlib.sha256(blob).hexdigest() != registro['sha256']:
            raise ValueError('SHA-256 incorreto: '+nome)
        alvo = destino.joinpath(*path.parts)
        alvo.parent.mkdir(parents=True,exist_ok=True)
        alvo.write_bytes(blob)
        quantidade += 1
        pos = start + size + len(FIM)
    return quantidade


if __name__=='__main__':
    if len(sys.argv)!=3:
        print('Uso: python RECONSTRUIR_TXT.py ARQUIVO.txt PASTA_DESTINO')
        raise SystemExit(2)
    try:
        n = reconstruir(Path(sys.argv[1]),Path(sys.argv[2]))
        print(f'Reconstruídos e validados: {n} arquivos')
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as ex:
        print('ERRO:',ex,file=sys.stderr)
        raise SystemExit(1)
