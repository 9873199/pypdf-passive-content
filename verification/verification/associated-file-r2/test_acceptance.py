from io import BytesIO
import hashlib,json
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ArrayObject,DictionaryObject,NameObject,NumberObject,TextStringObject,DecodedStreamObject
DATA=b'Quarterly notes: read-only attachment fixture.\n'
def d(**entries):return DictionaryObject({NameObject('/'+k):v for k,v in entries.items()})
def attached():
 w=PdfWriter();w.pdf_header='%PDF-2.0';w.add_blank_page(width=200,height=200)
 stream=DecodedStreamObject();stream.set_data(DATA);stream[NameObject('/Type')]=NameObject('/EmbeddedFile')
 file=w._add_object(d(Type=NameObject('/Filespec'),F=TextStringObject('notes.txt'),UF=TextStringObject('notes.txt'),AFRelationship=NameObject('/Data'),EF=d(F=w._add_object(stream))))
 note=d(Type=NameObject('/Annot'),Subtype=NameObject('/Text'),Rect=ArrayObject([NumberObject(v) for v in (0,0,20,20)]),Contents=TextStringObject('Quarterly notes'),AF=ArrayObject([file]))
 w.pages[0][NameObject('/Annots')]=ArrayObject([w._add_object(note)]);return w
def reopen(w):
 buffer=BytesIO();w.write(buffer);return PdfReader(BytesIO(buffer.getvalue()))
def attachment(r):return r.pages[0]['/Annots'][0].get_object()['/AF'][0].get_object()
def test_fixture_contains_real_embedded_file():
 r=reopen(attached());file=attachment(r);assert file['/F']=='notes.txt' and file['/EF']['/F'].get_data()==DATA

def test_cleaning_removes_associated_file_entry_on_ordinary_annotation():
 w=attached();w.remove_active_content();r=reopen(w);note=r.pages[0]['/Annots'][0].get_object()
 if '/AF' in note:
  file=attachment(r);data=file['/EF']['/F'].get_data();print(json.dumps({'remaining_file':str(file['/F']),'embedded_payload_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'reachable_after_cleanup':True}))
 assert '/AF' not in note

def test_cloning_with_associated_file_does_not_mutate_input_reader():
 original=reopen(attached());clone=PdfWriter(clone_from=original);clone.remove_active_content();reopen(clone)
 assert attachment(original)['/EF']['/F'].get_data()==DATA