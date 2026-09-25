import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {stop} from './chrome_dom.mjs';

function inside(p,r){const rel=path.relative(r,p);return rel===''||(!rel.startsWith('..'+path.sep)&&rel!=='..'&&!path.isAbsolute(rel));}
export function permittedFile(file,roots,{exists=false,write=false}={}){
  if(typeof file!=='string'||!path.isAbsolute(file)||file.startsWith('\\\\')||file.slice(2).includes(':'))stop('CHROME_PATH_DENIED');
  const resolved=path.resolve(file),parent=path.dirname(resolved);
  if(!roots.some(r=>inside(resolved,path.resolve(r))))stop('CHROME_PATH_DENIED');
  let current=resolved;
  while(true){if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())stop('CHROME_PATH_DENIED');const up=path.dirname(current);if(up===current)break;current=up;}
  if(!fs.existsSync(parent)||exists&&!fs.existsSync(resolved))stop('CHROME_FILE_MISSING');
  if(write&&fs.existsSync(resolved))stop('CHROME_OUTPUT_EXISTS');
  return resolved;
}
export function writeArtifact(file,data,contract){
  const out=permittedFile(file,contract.scope.write_roots,{write:true});
  const bytes=typeof data==='string'?Buffer.from(data,'utf8'):Buffer.from(data);
  fs.writeFileSync(out,bytes,{flag:'wx'});
  const actual=fs.readFileSync(out);
  if(!actual.equals(bytes))stop('CHROME_FILE_VERIFICATION_FAILED');
  return {path:out,bytes:actual.length,sha256:createHash('sha256').update(actual).digest('hex')};
}
export function writeScreenshot(file,data,contract){
  const bytes=Buffer.from(data),ext=path.extname(file).toLowerCase();
  const type=bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))?'png':bytes[0]===255&&bytes[1]===216&&bytes[2]===255?'jpeg':null;
  if(!type)stop('CHROME_SCREENSHOT_FORMAT_UNKNOWN');
  if(type==='png'&&ext!=='.png')stop('CHROME_SCREENSHOT_REQUIRES_PNG_PATH');
  if(type==='jpeg'&&!['.jpg','.jpeg'].includes(ext))stop('CHROME_SCREENSHOT_REQUIRES_JPEG_PATH');
  return {...writeArtifact(file,bytes,contract),media_type:'image/'+type};
}
export function copyArtifact(source,destination,contract){
  // The source must be a specific artifact returned by a documented API, not
  // an arbitrary contract/page-supplied local path.
  if(typeof source!=='string'||!path.isAbsolute(source)||!fs.statSync(source).isFile())stop('CHROME_ARTIFACT_UNAVAILABLE');
  return writeArtifact(destination,fs.readFileSync(source),contract);
}
