/* Shared by the 2nd and 3rd cohort forms. Files go to Drive, never GitHub. */
window.createMathclanLogo = function (endpoint) {
  const $ = id => document.getElementById(id);
  const method = $('logoMethod'), file = $('logoFile'), link = $('logoLink');
  const status = $('logoStatus');
  let maxBytes = 10 * 1024 * 1024, uploaded = null, requestId = null;
  const extensions = ['png', 'jpg', 'jpeg', 'pdf', 'ai', 'eps', 'svg'];
  const ext = name => name.split('.').pop().toLowerCase();
  function toggle() {
    $('logoFileField').hidden = method.value !== 'upload';
    $('logoLinkField').hidden = method.value !== 'link';
  }
  method.addEventListener('change', toggle);
  file.addEventListener('change', () => {
    uploaded = null; requestId = null; status.textContent = '';
    const error = validate();
    if (error) status.textContent = error;
  });
  toggle();
  // Older form backends do not support uploads. Enable only after a verified handshake.
  if (endpoint) {
    const url = new URL(endpoint);
    url.searchParams.set('action', 'logoCapabilities');
    fetch(url, {signal: AbortSignal.timeout(10000)}).then(r => r.json()).then(r => {
      if (!r.ok || r.service !== 'mathclan-logo-v1' || !Number.isInteger(r.maxBytes) || r.maxBytes < 1 || r.maxBytes > 20 * 1024 * 1024) return;
      maxBytes = r.maxBytes;
      $('logoUploadOption').disabled = false;
      file.disabled = false;
      $('logoLimit').textContent = `PNG·JPG·PDF·AI·EPS·SVG 중 1개, 최대 ${maxBytes / 1024 / 1024}MB. 더 큰 파일은 파일 링크로 제출해 주세요.`;
      $('logoAvailability').textContent = '첨부한 로고는 운영진 구글드라이브에 저장됩니다.';
    }).catch(() => {});
  }
  function validate() {
    if (method.value === 'link') {
      try { if (new URL(link.value.trim()).protocol !== 'https:') throw Error(); }
      catch (_) { return '로고 파일을 열 수 있는 https:// 링크를 입력해 주세요.'; }
    }
    if (method.value === 'upload') {
      const f = file.files[0];
      if (file.disabled) return '파일 링크 또는 추후 이메일 제출을 선택해 주세요.';
      if (!f) return '학원 로고 파일을 선택해 주세요.';
      if (!extensions.includes(ext(f.name))) return '로고는 PNG·JPG·PDF·AI·EPS·SVG 파일로 제출해 주세요.';
      if (!f.size || f.size > maxBytes) return `로고 파일은 0바이트 초과 ${maxBytes / 1024 / 1024}MB 이하로 첨부해 주세요. 더 큰 파일은 링크로 제출할 수 있습니다.`;
    }
    return '';
  }
  async function prepare(applicant, website) {
    const error = validate();
    if (error) throw Error(error);
    if (method.value === 'later') return {method: '추후 이메일 제출', url: '', name: '', size: ''};
    if (method.value === 'link') return {method: '파일 링크', url: link.value.trim(), name: '', size: ''};
    if (uploaded) return uploaded;
    const f = file.files[0];
    requestId ||= crypto.randomUUID();
    status.textContent = '로고를 저장하는 중입니다…';
    file.disabled = true; method.disabled = true;
    try {
      const base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = () => reject(Error('로고 파일을 읽지 못했습니다. 파일을 다시 선택해 주세요.'));
        reader.readAsDataURL(f);
      });
      const response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'text/plain;charset=utf-8'},
        body: JSON.stringify({action: 'uploadLogo', website, requestId, applicant, consent: true,
          file: {name: f.name, size: f.size, base64}}), signal: AbortSignal.timeout(90000)});
      const result = await response.json();
      if (!result.ok || !/^https:\/\/drive\.google\.com\//.test(result.url)) throw Error();
      uploaded = {method: '구글드라이브 저장', url: result.url, name: f.name, size: f.size};
      status.textContent = '로고가 저장되었습니다. 신청서 접수를 진행합니다.';
      return uploaded;
    } catch (e) {
      status.textContent = '로고 저장을 확인하지 못했습니다.';
      throw Error('로고 저장을 확인하지 못했습니다. 다시 시도하거나 파일 링크·추후 이메일 제출을 선택해 주세요.');
    } finally { file.disabled = false; method.disabled = false; }
  }
  return {validate, prepare};
};
