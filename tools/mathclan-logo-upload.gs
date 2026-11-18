/** Add to the existing form's Apps Script project. See mathclan-logo-setup.md. */
function setupLogo() {
  var props = PropertiesService.getScriptProperties();
  var folderId = props.getProperty('MATHCLAN_LOGO_FOLDER_ID');
  if (!folderId) {
    var folder = DriveApp.createFolder('매쓰클랜 학원 로고');
    folderId = folder.getId();
    props.setProperty('MATHCLAN_LOGO_FOLDER_ID', folderId);
  }
  DriveApp.getFolderById(folderId).getName();
  ensureHeaders(respSheet());
  console.log('학원 로고 폴더: https://drive.google.com/drive/folders/' + folderId);
}

function mathclanLogoGet(e) {
  if (!e || !e.parameter || e.parameter.action !== 'logoCapabilities') return null;
  var ready = !!PropertiesService.getScriptProperties().getProperty('MATHCLAN_LOGO_FOLDER_ID');
  return mathclanLogoJson_({ok: ready, service: 'mathclan-logo-v1', maxBytes: 10 * 1024 * 1024});
}

function mathclanLogoPost(e) {
  var raw = e && e.postData && e.postData.contents;
  if (!raw) return null;
  if (raw.length > 14 * 1024 * 1024) return mathclanLogoJson_({ok: false, error: 'REQUEST_TOO_LARGE'});
  var data;
  try { data = JSON.parse(raw); } catch (_) { return null; }
  if (data.action !== 'uploadLogo') return null;
  try { return mathclanLogoJson_(mathclanLogoSave_(data)); }
  catch (_) { return mathclanLogoJson_({ok: false, error: 'LOGO_UPLOAD_FAILED'}); }
}

function mathclanLogoSave_(data) {
  var props = PropertiesService.getScriptProperties();
  var folderId = props.getProperty('MATHCLAN_LOGO_FOLDER_ID');
  var applicant = data.applicant || {}, f = data.file || {};
  if (!folderId || data.website || data.consent !== true) throw Error('Invalid request');
  if (!/^[a-f0-9-]{36}$/i.test(data.requestId || '')) throw Error('Invalid request id');
  ['name', 'academy', 'cohort'].forEach(function (key) {
    if (typeof applicant[key] !== 'string' || !applicant[key].trim() || applicant[key].length > 100) throw Error('Invalid applicant');
  });
  if (!/^\d{1,2}기 모집$/.test(applicant.cohort)) throw Error('Invalid cohort');
  var types = {png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', pdf: 'application/pdf',
    ai: 'application/postscript', eps: 'application/postscript', svg: 'image/svg+xml'};
  if (typeof f.name !== 'string' || f.name.length > 200) throw Error('Invalid filename');
  var extension = f.name.split('.').pop().toLowerCase();
  if (!types[extension] || !Number.isInteger(f.size) || f.size < 1 || f.size > 10 * 1024 * 1024) throw Error('Invalid file');
  if (typeof f.base64 !== 'string' || f.base64.length > 4 * Math.ceil(f.size / 3) || !/^[A-Za-z0-9+/]+={0,2}$/.test(f.base64)) throw Error('Invalid encoding');
  var bytes = Utilities.base64Decode(f.base64);
  if (bytes.length !== f.size) throw Error('Invalid file length');
  var head = bytes.slice(0, 128).map(function (b) { return String.fromCharCode(b & 255); }).join('');
  var valid = extension === 'png' ? head.slice(0, 8) === '\x89PNG\r\n\x1a\n' :
    /^(jpg|jpeg)$/.test(extension) ? (bytes[0] & 255) === 255 && (bytes[1] & 255) === 216 && (bytes[2] & 255) === 255 :
    extension === 'svg' ? /<svg[\s>]/i.test(head) || /^\s*<\?xml/.test(head) :
    extension === 'pdf' ? head.indexOf('%PDF-') === 0 : head.indexOf('%PDF-') === 0 || head.indexOf('%!PS') === 0;
  if (!valid) throw Error('File type mismatch');
  var fingerprint = Utilities.base64Encode(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes));
  var safe = function (v) { return v.replace(/[\x00-\x1f\\/:*?"<>|]/g, '_').slice(0, 50); };
  var filename = safe(applicant.academy) + '_' + safe(applicant.name) + '_' + data.requestId + '.' + extension;
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) throw Error('Busy');
  var file;
  try {
    var folder = DriveApp.getFolderById(folderId), previous = folder.getFilesByName(filename);
    if (previous.hasNext()) {
      file = previous.next();
      if (file.getDescription() !== fingerprint) throw Error('Request id reused');
      return {ok: true, url: file.getUrl()};
    }
    var today = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd');
    var quota = JSON.parse(props.getProperty('MATHCLAN_LOGO_DAILY_USAGE') || '{}');
    var count = quota.date === today ? Number(quota.count) || 0 : 0;
    if (count >= 100) throw Error('Daily quota reached');
    file = folder.createFile(Utilities.newBlob(bytes, types[extension], filename));
    file.setDescription(fingerprint);
    props.setProperty('MATHCLAN_LOGO_DAILY_USAGE', JSON.stringify({date: today, count: count + 1}));
  } finally { lock.releaseLock(); }
  // No sharing permission is added; keep the destination folder private.
  return {ok: true, url: file.getUrl()};
}

function mathclanLogoJson_(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
