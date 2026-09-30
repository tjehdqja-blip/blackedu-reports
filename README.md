# THE BLACK EDU 내신분석 리포트

학교별 시험 분석 리포트를 GitHub Pages로 공개하는 저장소입니다.

- 사이트: https://tjehdqja-blip.github.io/blackedu-reports/

## 리포트 목록

| 시험 | 주소 |
|---|---|
| 둔촌고 1학년 2026학년도 2학기 중간고사 공통수학2 | https://tjehdqja-blip.github.io/blackedu-reports/dunchon-h1-2026-2-mid-math2/ |

## 구조

```
index.html                     리포트 목록 페이지
assets/logo.png                로고
<리포트 폴더>/
  index.html                   리포트 본문 (링크 미리보기용 메타 태그 포함)
  og.png                       링크 섬네일 (1200x630)
  <리포트 폴더>.pdf             인쇄·공유용 PDF
```

## 새 리포트 추가

1. `exam-analysis-report` 스킬로 리포트 HTML·PDF 생성
2. 리포트 폴더를 만들어 `index.html`, `og.png`, PDF를 넣기
3. 루트 `index.html`의 카드와 이 문서의 목록에 한 줄 추가
4. 커밋 후 `main`에 푸시하면 자동 배포

시험 문제 원문과 시험지 사진은 올리지 않습니다(저작권은 출제 학교에 있음). 등급컷·정답률은 예상치입니다.
