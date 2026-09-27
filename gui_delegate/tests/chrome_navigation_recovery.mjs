import assert from 'node:assert/strict';
import {navigateInitial} from '../chrome_delegate.mjs';
const url='https://fixture.invalid/';let calls=0,reads=0;
const tab={async goto(){calls++;throw new Error('Navigation timed out');},async url(){reads++;return url;},async getJsDialog(){}};
assert.equal(await navigateInitial(tab,url),true);assert.equal(calls,1);assert.equal(reads,1);
tab.url=async()=> 'about:blank';await assert.rejects(navigateInitial(tab,url),/timed out/);assert.equal(calls,2);
tab.goto=async()=>{throw new Error('user took over browser');};tab.url=async()=>{throw new Error('should not read after interruption');};
await assert.rejects(navigateInitial(tab,url),/user took over/);
console.log(JSON.stringify({status:'PASS',checks:3,mode:'navigation error reconciliation, no reload and no takeover'}));
