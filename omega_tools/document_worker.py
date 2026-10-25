"""Executed only inside the document parser sandbox."""
import base64,json,sys,io
from pathlib import Path
def main():
    sys.path.insert(0,sys.argv[1]);request=json.loads(Path(sys.argv[2]).read_bytes());data=base64.b64decode(request['data'],validate=True)
    if len(data)>8*1024**2:raise ValueError('Document budget exceeded')
    kind=request['kind'];result=[]
    if kind=='pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted or len(reader.pages)>256:raise ValueError('Unsupported encrypted/large PDF')
        total=0
        for number,page in enumerate(reader.pages):
            text=page.extract_text() or '';total+=len(text)
            if total>1000000:raise ValueError('Extracted document budget exceeded')
            result.append({'page':number+1,'text':text})
    elif kind in ('text','json'):
        text=data.decode('utf-8')
        if len(text)>1000000:raise ValueError('Text budget exceeded')
        result=[{'page':1,'text':text}]
        if kind=='json':json.loads(text)
    else:raise ValueError('Unsupported document kind')
    print(json.dumps({'pages':result},ensure_ascii=False))
if __name__=='__main__':main()
