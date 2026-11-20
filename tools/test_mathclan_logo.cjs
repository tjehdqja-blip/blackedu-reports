// No Google requests or emails: exercise the Drive adapter with in-memory doubles.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const properties = new Map([['MATHCLAN_LOGO_FOLDER_ID', 'private-logo-folder']]);
const files = new Map(), emails = [];
const context = {
  console,
  PropertiesService: {getScriptProperties: () => ({getProperty: key => properties.get(key), setProperty: (key, value) => properties.set(key, value)})},
  Utilities: {
    DigestAlgorithm: {SHA_256: 'sha256'},
    base64Decode: value => [...Buffer.from(value, 'base64')],
    base64Encode: value => Buffer.from(value).toString('base64'),
    computeDigest: (kind, value) => [...crypto.createHash(kind).update(Buffer.from(value)).digest()],
    formatDate: () => '2026-11-18',
    newBlob: (bytes, mime, name) => ({bytes, mime, name})
  },
  LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock() {}})},
  DriveApp: {getFolderById: id => {
    assert.equal(id, 'private-logo-folder');
    return {
      getFilesByName: name => ({hasNext: () => files.has(name), next: () => files.get(name)}),
      createFile: blob => {
        const file = {blob, description: '', setDescription(value) {this.description = value;}, getDescription() {return this.description;}, getUrl: () => 'https://drive.google.com/file/d/test-logo/view'};
        files.set(blob.name, file); return file;
      }
    };
  }},
  MailApp: {sendEmail: message => emails.push(message)},
  ContentService: {MimeType: {JSON: 'json'}, createTextOutput: text => ({text, setMimeType() {return this;}})}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, 'mathclan-logo-upload.gs'), 'utf8'), context);
const bytes = Buffer.from('\x89PNG\r\n\x1a\nTEST', 'latin1');
const data = {action: 'uploadLogo', website: '', consent: true, requestId: crypto.randomUUID(),
  applicant: {name: '테스트', academy: '검증학원', cohort: '3기 모집'},
  file: {name: 'logo.png', size: bytes.length, base64: bytes.toString('base64')}};
const call = value => context.mathclanLogoPost({postData: {contents: JSON.stringify(value)}});
const ok = value => JSON.parse(call(value).text).ok;
assert.equal(context.mathclanLogoPost({postData: {contents: JSON.stringify({fields: []})}}), null);
assert.equal(JSON.parse(context.mathclanLogoGet({parameter: {action: 'logoCapabilities'}}).text).service, 'mathclan-logo-v1');
assert.equal(ok({...data, consent: false}), false);
assert.equal(ok({...data, website: 'spam'}), false);
assert.equal(ok({...data, file: {...data.file, name: 'logo.html'}}), false);
assert.equal(ok({...data, file: {...data.file, name: 'logo.pdf'}}), false);
assert.equal(ok({...data, file: {...data.file, size: data.file.size + 1}}), false);
assert.equal(ok({...data, file: {...data.file, size: 10 * 1024 * 1024 + 1}}), false);
assert.equal(files.size, 0);
assert.equal(ok(data), true);
assert.equal(ok(data), true);
assert.equal(files.size, 1, 'Retry must not duplicate the logo');
assert.equal(emails.length, 0, 'Email disabled by default');
const altered = Buffer.from('\x89PNG\r\n\x1a\nEDIT', 'latin1');
assert.equal(ok({...data, file: {...data.file, base64: altered.toString('base64')}}), false);
assert.equal(ok({...data, requestId: crypto.randomUUID(), notify: 'untrusted@example.com'}), true);
assert.equal(emails.length, 0, 'Drive collection never sends email');
properties.set('MATHCLAN_LOGO_DAILY_USAGE', JSON.stringify({date: '2026-11-18', count: 100}));
assert.equal(ok({...data, requestId: crypto.randomUUID()}), false);
assert.equal(files.size, 2);
// 특별판 표지 제작 신청서(cohort 'N기 특별판')의 로고도 받고, 그 밖의 값은 거절한다
properties.delete('MATHCLAN_LOGO_DAILY_USAGE');
assert.equal(ok({...data, requestId: crypto.randomUUID(), applicant: {...data.applicant, cohort: '2기 특별판'}}), true);
assert.equal(ok({...data, requestId: crypto.randomUUID(), applicant: {...data.applicant, cohort: '2기 기타'}}), false);
assert.equal(files.size, 3);
console.log('PASS: dispatch, capabilities, consent, types, file length/size, Drive save, retry, no email, quota.');
