import assert from 'node:assert/strict';
import {readControls,probe} from '../chrome_dom.mjs';
const doc={URL:'https://fixture.invalid/'};
function element(tag='BUTTON',attrs={},extra={}){
  return {tagName:tag,nodeType:1,id:attrs.id||'',parentElement:null,previousElementSibling:null,ownerDocument:doc,
    innerText:attrs.text||'',textContent:attrs.text||'',value:tag==='INPUT'?'':undefined,
    getRootNode(){return doc;},getAttribute(name){return attrs[name]??null;},hasAttribute(name){return name in attrs;},
    getBoundingClientRect(){return {width:attrs.hidden?0:80,height:25};},closest(){return null;},matches(){return true;},...extra};
}
const previous=globalThis.getComputedStyle;globalThis.getComputedStyle=()=>({visibility:'visible',display:'block'});
let checks=0;
try{
  const root=controls=>({ownerDocument:doc,querySelectorAll:()=>controls});
  const read=list=>readControls(root(list));
  const hidden=Array.from({length:700},()=>element('BUTTON',{hidden:true}));
  let value=read([...hidden,element('BUTTON',{text:'Visible'})]);assert.equal(value.overflow,false);assert.equal(value.controls.length,1);checks++;
  const field=element('INPUT',{type:'text',placeholder:'Trending topic',id:'site-search-field'});
  value=read([field]).controls[0];assert.equal(value.name,'Trending topic');assert.equal(value.attributes.public_search,'true');checks++;
  assert.equal(probe(field).name,value.name);assert.ok(value.attributes.dom_path.includes('input:nth-of-type(1)'));checks++;
  const post=element('INPUT',{type:'search',placeholder:'Search'},{form:{getAttribute:()=> 'post',querySelector:()=>null,action:'https://fixture.invalid/private'}});
  assert.equal(read([post]).controls[0].attributes.public_search,'false');checks++;
  const searchForm={getAttribute(name){return {id:'nav-searchform',method:'get'}[name]||null;},querySelector(){return null;},action:'https://fixture.invalid/search'};
  const trending=element('INPUT',{type:'text',placeholder:'Unrelated trending topic'},{form:searchForm});
  assert.equal(read([trending]).controls[0].attributes.public_search,'true');checks++;
  searchForm.querySelector=()=>({type:'password'});
  assert.equal(read([trending]).controls[0].attributes.public_search,'false');checks++;
  value=read(Array.from({length:2401},()=>element('BUTTON',{text:'Large'})));assert.equal(value.overflow,true);assert.deepEqual(value.controls,[]);checks++;
  const container={getAttribute:()=>null,querySelector:()=>({textContent:'Reference'})};
  const duplicate=element('BUTTON',{text:'Open'},{closest(selector){return selector.startsWith('article')?container:null;}});
  value=read([duplicate]).controls[0];assert.equal(value.attributes.context,'Reference');assert.equal(probe(duplicate).context,'Reference');checks++;
  const card={tagName:'DIV',innerText:'Reference guide\nMaintainer · 2026-09-25',parentElement:null,querySelector:()=>null,querySelectorAll:()=>[{},{}]};
  const cardLink=element('A',{text:'Reference guide'},{parentElement:card});
  value=read([cardLink]).controls[0];assert.equal(value.attributes.neighborhood,'Reference guide Maintainer · 2026-09-25');assert.equal(probe(cardLink).neighborhood,value.attributes.neighborhood);checks++;
  card.querySelector=()=>({tagName:'INPUT'});assert.equal(read([cardLink]).controls[0].attributes.neighborhood,'');checks++;
  card.querySelector=()=>null;card.innerText='x'.repeat(301);assert.equal(read([cardLink]).controls[0].attributes.neighborhood,'');checks++;
  const rich=element('DIV',{'contenteditable':'true','aria-label':'Post'},{value:'',isContentEditable:undefined,innerText:'Line one\nLine two',textContent:'Line oneLine two'});
  value=read([rich]).controls[0];assert.equal(value.value,'Line one\nLine two');assert.equal(value.role,'textbox');assert.equal(value.attributes.contenteditable,'true');checks++;
  assert.equal(probe(rich).value,value.value);assert.equal(probe(rich).role,value.role);checks++;
  const plain=element('DIV',{'contenteditable':'plaintext-only'},{value:'',innerText:'Plain\ntext',textContent:'Plaintext'});
  assert.equal(read([plain]).controls[0].value,'Plain\ntext');checks++;
  const inherited=element('SPAN',{'role':'textbox'},{parentElement:rich,value:'',innerText:'Inherited',textContent:'Inherited'});
  assert.equal(read([inherited]).controls[0].value,'Inherited');checks++;
  const stopped=element('DIV',{'contenteditable':'false'},{parentElement:rich,value:'',innerText:'Read only'});
  assert.equal(read([stopped]).controls[0].value,null);assert.equal(read([stopped]).controls[0].attributes.contenteditable,'false');checks++;
  const input=element('INPUT',{type:'text'},{value:'Existing value'});
  assert.equal(read([input]).controls[0].value,'Existing value');assert.equal(probe(input).value,'Existing value');checks++;
  rich.innerText='\n';rich.textContent='';assert.equal(read([rich]).controls[0].value,'');assert.equal(probe(rich).value,'');checks++;
  rich.textContent='\n';assert.equal(read([rich]).controls[0].value,'\n');checks++;
  rich.textContent='';rich.querySelector=()=>({tagName:'IMG'});assert.equal(read([rich]).controls[0].value,'\n');checks++;
}finally{if(previous===undefined)delete globalThis.getComputedStyle;else globalThis.getComputedStyle=previous;}
console.log(JSON.stringify({status:'PASS',checks,mode:'controlled DOM; hidden content, placeholders, search identity, context and explicit overflow'}));
