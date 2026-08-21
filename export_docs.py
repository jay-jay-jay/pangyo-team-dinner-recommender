"""README.md 문서를 스타일이 적용된 단독 HTML 및 PDF 출력용 웹페이지로 내보내는 스크립트"""
import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
README_MD = os.path.join(BASE_DIR, "README.md")
README_HTML = os.path.join(BASE_DIR, "README.html")

with open(README_MD, "r", encoding="utf-8") as f:
    text = f.read()

json_text = json.dumps(text)

html_template = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>판교 회식장소 추천 서비스 - 프로젝트 상세 및 프레젠테이션 가이드</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{
            box-sizing: border-box;
            max-width: 960px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 12px 20px;
            background: #ffffff;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        }}
        .btn {{
            background: #0B4F9E;
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
        }}
        .btn:hover {{
            background: #083870;
        }}
        .markdown-body {{
            background: white;
            padding: 45px;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.06);
            border: 1px solid #e2e8f0;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .markdown-body {{ box-shadow: none; border: none; padding: 0; }}
            .no-print {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="top-bar no-print">
        <div style="font-weight: bold; color: #1e293b;">📄 판교 회식 추천 프로젝트 문서 (Export 뷰어)</div>
        <div>
            <button onclick="window.print()" class="btn">🖨️ PDF 파일로 저장 / 인쇄</button>
        </div>
    </div>

    <article class="markdown-body" id="content"></article>

    <script>
        const rawMarkdown = {json_text};
        document.getElementById('content').innerHTML = marked.parse(rawMarkdown);
        mermaid.initialize({{ startOnLoad: true }});
    </script>
</body>
</html>
"""

with open(README_HTML, "w", encoding="utf-8") as f:
    f.write(html_template)

# 데스크톱(바탕화면) 워크스페이스에도 복사본 내보내기
target_dir = r"c:\Users\Skku\OneDrive\Desktop\260821\260821_recommendation"
if os.path.exists(target_dir):
    shutil.copy2(README_MD, os.path.join(target_dir, "README.md"))
    shutil.copy2(README_HTML, os.path.join(target_dir, "README.html"))

print("Export HTML and Desktop sync completed successfully!")
