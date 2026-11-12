"""Construct only local small PDFs; verify reopened reachable objects."""
from io import BytesIO
import pytest
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ArrayObject,DictionaryObject,NameObject,NumberObject,TextStringObject,DecodedStreamObject,IndirectObject

def key(s):return NameObject(s)
def resolve(v):return v.get_object() if isinstance(v,IndirectObject) else v
def arr(*v):return ArrayObject(list(v))
def obj(**values):return DictionaryObject({NameObject('/'+k):v for k,v in values.items()})
def writer():
 w=PdfWriter();w.add_blank_page(width=200,height=200);return w

def goto(w):return obj(S=key('/GoTo'),D=arr(w.pages[0].indirect_reference,key('/Fit')))
def bad(kind='/JavaScript'):
 d=obj(S=key(kind))
 if kind=='/JavaScript':d[key('/JS')]=TextStringObject('void(0)')
 elif kind=='/URI':d[key('/URI')]=TextStringObject('https://invalid.example/')
 else:d[key('/F')]=TextStringObject('never-open')
 return d

def save(w):
 out=BytesIO();w.write(out);out.seek(0);return PdfReader(out)
def clean(w):w.remove_active_content();return save(w)
def walk(root):
 todo=[root];seen=set()
 while todo:
  v=todo.pop()
  if isinstance(v,IndirectObject):v=v.get_object()
  if not isinstance(v,(dict,list)):continue
  if id(v) in seen:continue
  seen.add(id(v));yield v
  todo.extend(v.values() if isinstance(v,dict) else v)
def assert_passive(reader):
 for v in walk(reader.trailer['/Root']):
  if isinstance(v,dict):
   assert not any(x in v for x in ['/JS','/XFA','/EmbeddedFiles','/AF'])
   if '/S' in v:assert v['/S']=='/GoTo'

@pytest.mark.parametrize('kind',['/JavaScript','/Launch','/URI','/GoToR','/SubmitForm','/ResetForm','/ImportData','/Rendition','/Sound','/Movie'])
def test_catalog_dangerous_open_actions_removed(kind):
 w=writer();w.root_object[key('/OpenAction')]=w._add_object(bad(kind));r=clean(w);assert '/OpenAction' not in r.trailer['/Root']
def test_open_destination_array_preserved():
 w=writer();w.root_object[key('/OpenAction')]=arr(w.pages[0].indirect_reference,key('/Fit'));r=clean(w);assert isinstance(r.trailer['/Root']['/OpenAction'],list)
def test_allowed_internal_navigation_and_next_good_entries():
 w=writer();a=goto(w);good=goto(w);a[key('/Next')]=arr(w._add_object(bad()),w._add_object(good),w._add_object(bad('/URI')));w.root_object[key('/OpenAction')]=w._add_object(a)
 r=clean(w);a=r.trailer['/Root']['/OpenAction'];assert a['/S']=='/GoTo'
 next_=resolve(a.get('/Next'));values=next_ if isinstance(next_,list) else [next_] if next_ else []
 assert len(values)==1 and values[0].get_object()['/S']=='/GoTo';assert_passive(r)
def test_bad_single_next_dropped_without_losing_goto():
 w=writer();a=goto(w);a[key('/Next')]=w._add_object(bad());w.root_object[key('/OpenAction')]=w._add_object(a);r=clean(w)
 assert r.trailer['/Root']['/OpenAction']['/S']=='/GoTo';assert not resolve(r.trailer['/Root']['/OpenAction'].get('/Next'));assert_passive(r)
def test_shared_and_cyclic_indirect_action_graph_terminates():
 w=writer();a=goto(w);b=goto(w);ra=w._add_object(a);rb=w._add_object(b);a[key('/Next')]=arr(rb,w._add_object(bad()));b[key('/Next')]=ra
 w.root_object[key('/OpenAction')]=ra;w.pages[0][key('/A')]=ra;r=clean(w);assert_passive(r)
def test_page_and_annotation_actions_removed_but_static_link_remains():
 w=writer();w.pages[0][key('/AA')]=obj(O=w._add_object(bad()))
 link=obj(Type=key('/Annot'),Subtype=key('/Link'),Rect=arr(*[NumberObject(n) for n in [0,0,50,50]]),A=w._add_object(bad('/URI')))
 text=obj(Type=key('/Annot'),Subtype=key('/Text'),Rect=arr(*[NumberObject(n) for n in [0,0,10,10]]),Contents=TextStringObject('keep this note'))
 w.pages[0][key('/Annots')]=arr(w._add_object(link),w._add_object(text));r=clean(w);annots=[x.get_object() for x in r.pages[0]['/Annots']]
 assert len(annots)==2 and all('/A' not in x for x in annots);assert annots[1]['/Contents']=='keep this note';assert_passive(r)
@pytest.mark.parametrize('kind',['/RichMedia','/Movie','/Sound','/Screen'])
def test_active_media_annotation_removed(kind):
 w=writer();w.pages[0][key('/Annots')]=arr(w._add_object(obj(Type=key('/Annot'),Subtype=key(kind),Rect=arr(NumberObject(0),NumberObject(0),NumberObject(1),NumberObject(1)))))
 r=clean(w);assert not resolve(r.pages[0].get('/Annots'))
def test_nested_field_aa_and_xfa_removed_static_field_preserved():
 w=writer();child=obj(T=TextStringObject('child'),FT=key('/Tx'),V=TextStringObject('retained'),AA=obj(K=w._add_object(bad())))
 parent=obj(T=TextStringObject('parent'),Kids=arr(w._add_object(child)),AA=obj(F=w._add_object(bad())))
 w.root_object[key('/AcroForm')]=w._add_object(obj(Fields=arr(w._add_object(parent)),XFA=TextStringObject('active')))
 r=clean(w);form=r.trailer['/Root']['/AcroForm'];leaf=form['/Fields'][0].get_object()['/Kids'][0].get_object();assert leaf['/V']=='retained';assert_passive(r)
def test_embedded_entrypoints_removed_other_names_preserved():
 w=writer();dest=obj(Names=arr(TextStringObject('start'),arr(w.pages[0].indirect_reference,key('/Fit'))));files=obj(Names=arr(TextStringObject('attachment'),obj(Type=key('/Filespec'),F=TextStringObject('x.txt'))))
 w.root_object[key('/Names')]=obj(JavaScript=obj(Names=arr(TextStringObject('run'),w._add_object(bad()))),EmbeddedFiles=files,Dests=dest)
 w.root_object[key('/AF')]=arr(w._add_object(obj(Type=key('/Filespec'),F=TextStringObject('x.txt'))));r=clean(w)
 assert '/Dests' in r.trailer['/Root']['/Names'];assert_passive(r)
def test_contents_metadata_and_idempotence():
 w=writer();stream=DecodedStreamObject();stream.set_data(b'q\nQ\n');w.pages[0][key('/Contents')]=w._add_object(stream);w.add_metadata({'/Title':'retain title'});w.root_object[key('/OpenAction')]=w._add_object(bad())
 w.remove_active_content();r=save(w);w.remove_active_content();r2=save(w)
 assert r.pages[0]['/Contents'].get_data()==r2.pages[0]['/Contents'].get_data()==b'q\nQ\n';assert r2.metadata.title=='retain title';assert len(r2.pages)==1;assert_passive(r2)
def test_reader_clone_not_mutated():
 original=writer();original.root_object[key('/OpenAction')]=original._add_object(bad());reader=save(original)
 w=PdfWriter(clone_from=reader);r=clean(w)
 assert reader.trailer['/Root']['/OpenAction']['/S']=='/JavaScript';assert '/OpenAction' not in r.trailer['/Root']


def test_internal_goto_page_and_annotation_actions_retained():
 w=writer();w.pages[0][key('/A')]=w._add_object(goto(w))
 link=obj(Type=key('/Annot'),Subtype=key('/Link'),Rect=arr(NumberObject(0),NumberObject(0),NumberObject(5),NumberObject(5)),A=w._add_object(goto(w)))
 w.pages[0][key('/Annots')]=arr(w._add_object(link));r=clean(w)
 assert r.pages[0]['/A']['/S']=='/GoTo'
 assert r.pages[0]['/Annots'][0].get_object()['/A']['/S']=='/GoTo';assert_passive(r)

def test_mixed_additional_actions_preserve_allowed_events():
 w=writer();w.root_object[key('/AA')]=obj(WC=w._add_object(bad()),WS=w._add_object(goto(w)))
 w.pages[0][key('/AA')]=obj(O=w._add_object(goto(w)),C=w._add_object(bad('/URI')))
 widget=obj(Type=key('/Annot'),Subtype=key('/Widget'),Rect=arr(NumberObject(0),NumberObject(0),NumberObject(5),NumberObject(5)),AA=obj(E=w._add_object(goto(w)),X=w._add_object(bad('/Launch'))))
 w.pages[0][key('/Annots')]=arr(w._add_object(widget));r=clean(w)
 assert r.trailer['/Root']['/AA']['/WS']['/S']=='/GoTo'
 assert '/WC' not in r.trailer['/Root']['/AA']
 assert r.pages[0]['/AA']['/O']['/S']=='/GoTo' and '/C' not in r.pages[0]['/AA']
 aa=r.pages[0]['/Annots'][0].get_object()['/AA'];assert aa['/E']['/S']=='/GoTo' and '/X' not in aa;assert_passive(r)

def test_indirect_next_array_filters_without_losing_good_gotos():
 w=writer();a=goto(w);a[key('/Next')]=w._add_object(arr(w._add_object(bad()),w._add_object(goto(w)),w._add_object(bad('/GoToR')),w._add_object(goto(w))))
 w.root_object[key('/OpenAction')]=w._add_object(a);r=clean(w);following=resolve(r.trailer['/Root']['/OpenAction']['/Next'])
 assert len(following)==2 and all(x.get_object()['/S']=='/GoTo' for x in following);assert_passive(r)

def test_single_allowed_next_preserved():
 w=writer();a=goto(w);a[key('/Next')]=w._add_object(goto(w));w.root_object[key('/OpenAction')]=w._add_object(a)
 r=clean(w);assert r.trailer['/Root']['/OpenAction']['/Next']['/S']=='/GoTo';assert_passive(r)

def test_indirect_annotations_array_removes_media_keeps_notes():
 w=writer();note=obj(Type=key('/Annot'),Subtype=key('/Text'),Rect=arr(NumberObject(0),NumberObject(0),NumberObject(5),NumberObject(5)),Contents=TextStringObject('normal note'))
 media=obj(Type=key('/Annot'),Subtype=key('/Screen'),Rect=arr(NumberObject(0),NumberObject(0),NumberObject(5),NumberObject(5)))
 w.pages[0][key('/Annots')]=w._add_object(arr(w._add_object(media),w._add_object(note)));r=clean(w)
 values=r.pages[0]['/Annots'];assert len(values)==1 and values[0].get_object()['/Contents']=='normal note';assert_passive(r)

def test_field_tree_with_parent_backrefs_and_allowed_actions():
 w=writer();parent=obj(T=TextStringObject('group'));rp=w._add_object(parent)
 child=obj(T=TextStringObject('name'),FT=key('/Tx'),V=TextStringObject('retained'),Parent=rp,AA=obj(K=w._add_object(bad()),F=w._add_object(goto(w))))
 parent[key('/Kids')]=arr(w._add_object(child));w.root_object[key('/AcroForm')]=w._add_object(obj(Fields=arr(rp)))
 r=clean(w);leaf=r.trailer['/Root']['/AcroForm']['/Fields'][0].get_object()['/Kids'][0].get_object()
 assert leaf['/V']=='retained' and leaf['/AA']['/F']['/S']=='/GoTo' and '/K' not in leaf['/AA'];assert_passive(r)

def test_page_and_annotation_associated_file_entrypoints_removed():
 w=writer();file=w._add_object(obj(Type=key('/Filespec'),F=TextStringObject('unused.txt')))
 w.pages[0][key('/AF')]=arr(file)
 note=obj(Type=key('/Annot'),Subtype=key('/Text'),Rect=arr(NumberObject(0),NumberObject(0),NumberObject(5),NumberObject(5)),AF=arr(file))
 w.pages[0][key('/Annots')]=arr(w._add_object(note));r=clean(w)
 assert len(r.pages[0]['/Annots'])==1;assert_passive(r)
def test_page_direct_action_entry_removed_when_not_internal_goto():
 w=writer();w.pages[0][key('/A')]=w._add_object(bad('/URI'));r=clean(w)
 assert '/A' not in r.pages[0];assert_passive(r)