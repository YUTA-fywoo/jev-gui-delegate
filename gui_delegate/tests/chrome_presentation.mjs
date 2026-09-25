/** Compact the model-facing view without discarding cleanup evidence. */
import assert from 'node:assert/strict';
import {presentation} from '../chrome_gateway.mjs';
const original={status:'completed',usage:{tabs_created:2,tabs_retained:0},
  tab_cleanup:{tabs_created:2,tabs_retained:0,retained:[],warning:'sample'}};
assert.deepEqual(presentation(original).tab_cleanup,{retained:[],warning:'sample'});
assert.equal(original.tab_cleanup.tabs_created,2);
assert.equal(presentation({usage:{tabs_created:1},tab_cleanup:{tabs_created:2}}).tab_cleanup.tabs_created,2);
assert.equal(presentation({status:'blocked'}).status,'blocked');
const retained=[{tab_id:'synthetic',reason:'edited_form'}];
assert.deepEqual(presentation({usage:{tabs_retained:1},tab_cleanup:{tabs_retained:1,retained}}).tab_cleanup.retained,retained);
console.log(JSON.stringify({status:'PASS',assertions:5,scope:'presentation only, preserves warnings and retained-page evidence'}));
