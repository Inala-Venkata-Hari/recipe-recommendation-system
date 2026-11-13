"""Create a dependency-free, offline PDF fallback from the local HTML slide deck."""
from html.parser import HTMLParser
from pathlib import Path
import textwrap,unicodedata
ROOT=Path(__file__).resolve().parent
class Parser(HTMLParser):
    def __init__(self):super().__init__();self.slides=[];self.current=None;self.tag=None
    def handle_starttag(self,tag,attrs):
        if tag=='section':self.current={'h2':'','h1':'','p':'','li':[]}
        if self.current is not None and tag in ['h1','h2','p','li']:self.tag=tag;self.buffer=[]
    def handle_data(self,data):
        if self.current is not None and self.tag:self.buffer.append(data)
    def handle_endtag(self,tag):
        if self.current is not None and tag==self.tag:
            value=''.join(self.buffer)
            if tag=='li':self.current['li'].append(value)
            else:self.current[tag]=value
            self.tag=None
        if tag=='section' and self.current is not None:self.slides.append(self.current);self.current=None

def plain(value):
    value=value.replace('→',' -> ').replace('–','-').replace('—','-').replace('’',"'").replace('×','x')
    return unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode()
def quote(value):return plain(value).replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
def text(x,y,value,size=18,font='F1',color='0.08 0.2 0.17'):
    return f'BT /{font} {size} Tf {color} rg {x} {y} Td ({quote(value)}) Tj ET\n'
parser=Parser();parser.feed((ROOT/'presentation.html').read_text())
objects=[]
def add(value):objects.append(value.encode() if isinstance(value,str) else value);return len(objects)
catalog=add('');pages=add('');regular=add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');bold=add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>');page_ids=[]
for number,slide in enumerate(parser.slides,1):
    commands='0.96 0.98 0.97 rg 0 0 960 540 re f\n0.06 0.38 0.29 rg 0 515 960 25 re f\n'
    commands+=text(55,472,slide['h2'].upper(),15,'F2','0.06 0.38 0.29')
    y=428
    for line in textwrap.wrap(plain(slide['h1']),width=46):commands+=text(55,y,line,32,'F2');y-=39
    y-=4;commands+=text(55,y,slide['p'],14,color='0.3 0.4 0.36');y-=43
    for bullet in slide['li']:
        lines=textwrap.wrap(plain(bullet),width=90)
        for i,line in enumerate(lines):commands+=text(60 if i==0 else 78,y,('- '+line) if i==0 else line,17);y-=23
        y-=14
    if y<30:raise ValueError(f'Slide {number} overflows')
    commands+=text(55,22,'Smart Cart | Offline demonstration | 12 November 2026',10,color='0.35 0.45 0.41')+text(875,22,f'{number} / {len(parser.slides)}',10)
    raw=commands.encode();stream=add(b'<< /Length '+str(len(raw)).encode()+b' >>\nstream\n'+raw+b'endstream')
    page_ids.append(add(f'<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 960 540] /Resources << /Font << /F1 {regular} 0 R /F2 {bold} 0 R >> >> /Contents {stream} 0 R >>'))
objects[catalog-1]=f'<< /Type /Catalog /Pages {pages} 0 R >>'.encode()
objects[pages-1]=('<< /Type /Pages /Count '+str(len(page_ids))+' /Kids [ '+' '.join(f'{p} 0 R' for p in page_ids)+' ] >>').encode()
output=bytearray(b'%PDF-1.4\n');offsets=[0]
for i,obj in enumerate(objects,1):offsets.append(len(output));output.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
xref=len(output);output.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
for offset in offsets[1:]:output.extend(f'{offset:010d} 00000 n \n'.encode())
output.extend(f'trailer\n<< /Size {len(objects)+1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
(ROOT/'presentation.pdf').write_bytes(output)
print('Created',len(page_ids),'PDF slides')
