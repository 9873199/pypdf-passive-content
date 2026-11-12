"""Separate local verification demo; calls the frozen library without altering it."""
import argparse,json
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ArrayObject,DictionaryObject,NameObject,NumberObject,TextStringObject,IndirectObject,DecodedStreamObject

def n(v):return NameObject(v)
def d(**values):return DictionaryObject({n('/'+k):v for k,v in values.items()})
def array(*values):return ArrayObject(list(values))
def action(kind,**fields):return d(S=n(kind),**fields)
def resolve(v):return v.get_object() if isinstance(v,IndirectObject) else v
def objects(root):
 seen=set();todo=[root]
 while todo:
  obj=resolve(todo.pop())
  if not isinstance(obj,(dict,list)) or id(obj) in seen:continue
  seen.add(id(obj));yield obj;todo.extend(obj.values() if isinstance(obj,dict) else obj)
def summary(reader):
 values=list(objects(reader.trailer['/Root']));actions=[str(v['/S']) for v in values if isinstance(v,dict) and '/S' in v]
 active=[v for v in actions if v!='/GoTo'];unsafe_keys=[k for v in values if isinstance(v,dict) for k in ('/JS','/JavaScript','/XFA','/EmbeddedFiles','/AF') if k in v]
 annotations=[str(ref.get_object().get('/Subtype')) for page in reader.pages for ref in resolve(page.get('/Annots',[]))]
 return {'pages':len(reader.pages),'title':reader.metadata.title,'actions':actions,'active_actions':active,'active_entry_keys':unsafe_keys,'annotations':annotations}
def main(output):
 assert output.resolve().is_relative_to(Path(r'D:\hc\userFeedback\cache').resolve());output.mkdir(parents=True,exist_ok=False)
 w=PdfWriter();w.add_blank_page(width=300,height=300);w.add_blank_page(width=300,height=300);w.add_metadata({'/Title':'Quarterly account summary'})
 content=DecodedStreamObject();content.set_data(b'q\nQ\n');w.pages[0][n('/Contents')]=w._add_object(content)
 def goto():return action('/GoTo',D=array(w.pages[1].indirect_reference,n('/Fit')))
 first=goto();first[n('/Next')]=array(w._add_object(action('/JavaScript',JS=TextStringObject('void(0)'))),w._add_object(goto()),w._add_object(action('/URI',URI=TextStringObject('https://invalid.example/'))))
 w.root_object[n('/OpenAction')]=w._add_object(first)
 w.pages[0][n('/AA')]=d(O=w._add_object(action('/JavaScript',JS=TextStringObject('void(0)'))))
 rect=array(*[NumberObject(x) for x in (0,0,40,40)])
 text=d(Type=n('/Annot'),Subtype=n('/Text'),Rect=rect,Contents=TextStringObject('Reviewed account figures'))
 link=d(Type=n('/Annot'),Subtype=n('/Link'),Rect=rect,A=w._add_object(goto()))
 media=d(Type=n('/Annot'),Subtype=n('/Screen'),Rect=rect)
 w.pages[0][n('/Annots')]=array(w._add_object(text),w._add_object(link),w._add_object(media))
 field=d(FT=n('/Tx'),T=TextStringObject('account'),V=TextStringObject('approved'),AA=d(K=w._add_object(action('/JavaScript',JS=TextStringObject('void(0)')))))
 w.root_object[n('/AcroForm')]=w._add_object(d(Fields=array(w._add_object(field)),XFA=TextStringObject('removed packet')))
 w.root_object[n('/Names')]=d(JavaScript=d(Names=array(TextStringObject('open'),w._add_object(action('/JavaScript',JS=TextStringObject('void(0)'))))),EmbeddedFiles=d(Names=array()))
 w.root_object[n('/AF')]=array(w._add_object(d(Type=n('/Filespec'),F=TextStringObject('unused.txt'))))
 source=output/'account-input.pdf';w.write(source);before=summary(PdfReader(source));print('Input PDF:');print(json.dumps(before,indent=2))
 print('\nRemoving active content...');w.remove_active_content();first_path=output/'account-readable.pdf';w.write(first_path);r=PdfReader(first_path);after=summary(r);print('\nSaved and reopened PDF:');print(json.dumps(after,indent=2))
 w.remove_active_content();second=output/'account-readable-again.pdf';w.write(second);again=summary(PdfReader(second))
 checks={'no_active_actions':not after['active_actions'],'no_active_entrypoints':not after['active_entry_keys'],'normal_pages_and_title_retained':after['pages']==2 and after['title']==before['title'],'ordinary_annotations_retained':after['annotations']==['/Text','/Link'],'internal_navigation_retained':after['actions'] and all(x=='/GoTo' for x in after['actions']),'static_field_retained':r.trailer['/Root']['/AcroForm']['/Fields'][0].get_object()['/V']=='approved','page_contents_retained':r.pages[0]['/Contents'].get_data()==b'q\nQ\n','repeat_cleanup_is_stable':after==again}
 print('\nChecks after reopening:')
 for label,ok in checks.items():print(('OK   ' if ok else 'FAIL ')+label.replace('_',' '))
 (output/'actual-demo-results.json').write_text(json.dumps({'before':before,'after':after,'checks':checks,'separate_verification_helper':True},indent=2),encoding='utf-8')
 return 0 if all(checks.values()) else 1
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();raise SystemExit(main(Path(a.output)))