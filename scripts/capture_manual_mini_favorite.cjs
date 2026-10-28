const fs=require('fs');const path=require('path');
const automator=require('../.run/cattle-preview/mini-runtime/node_modules/miniprogram-automator');
const out=path.resolve(__dirname,'../.run/copyright-20261023/screens');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function main(){
 const app=await automator.connect({wsEndpoint:'ws://127.0.0.1:9431'});
 console.log('favorite connected');
 async function invoke(method,...args){return app.evaluate(function(method,args){const p=getCurrentPages();p[p.length-1][method].apply(p[p.length-1],args);return true;},method,args);}
 async function route(url,method='navigateTo'){await app.evaluate(function(url,method){wx[method]({url:url});return true;},url,method);await pause(1200);return app.currentPage();}
 let created=false;let article;
 try{
  await route('/pages/index/index','switchTab');let page=await route('/pages/news/news');console.log('news opened');
  for(let i=0;i<50&&(await page.data()).loading;i++)await pause(250);
  await invoke('changeTab',{currentTarget:{dataset:{tab:'knowledge'}}});article=(await page.data()).articles[0];console.log('article chosen',article.id);
  await invoke('open',{currentTarget:{dataset:{id:article.id}}});await pause(1000);let detail=await app.currentPage();console.log('detail opened');
  if(!(await detail.data()).saved){await invoke('favorite');created=true;await pause(300);}
  await route('/pages/index/index','switchTab');page=await route('/pages/news/news');await invoke('changeTab',{currentTarget:{dataset:{tab:'saved'}}});await pause(400);console.log('favorites opened');
  const file=path.join(out,'wx-news-favorites.png');await app.screenshot({path:file});
  const tabs=await page.$('.news-tabs');const position=await tabs.offset();const size=await tabs.size();
  const rect={left:Number(position.left),top:Number(position.top),width:Number(size.width),bottom:Number(position.top)+Number(size.height)};
  const manifest=JSON.parse(fs.readFileSync(path.join(out,'mini-manifest.json'),'utf8'));
  const item={key:'wx-news-favorites',file,marks:[{rect:[rect.left+rect.width/2,rect.top,rect.left+rect.width*3/4,rect.bottom],label:'1',text:'收藏'}],captured:new Date().toISOString(),width:430,height:834};
  manifest.push(item);
  // These bounds were checked against the actual captures; no application values are edited.
  manifest.find(x=>x.key==='wx-consultation-submit').marks=[{rect:[219,756,414,810],label:'1',text:'提交咨询'}];
  manifest.find(x=>x.key==='wx-assistant-answer').marks=[{rect:[220,636,324,670],label:'1',text:'转专家咨询'},{rect:[14,636,66,670],label:'2',text:'复制'}];
  fs.writeFileSync(path.join(out,'mini-manifest.json'),JSON.stringify(manifest,null,2));
  console.log('Captured favorite and verified missing red-box bounds');
  if(created){await invoke('open',{currentTarget:{dataset:{id:article.id}}});await pause(700);await invoke('favorite');}
  await route('/pages/index/index','switchTab');
 }finally{await app.disconnect();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
