FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/static/pyodide && python - <<'EOF'
import os, urllib.request
base = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
files = ["pyodide.js", "pyodide-lock.json", "python_stdlib.zip", "pyodide.asm.js", "pyodide.asm.wasm"]
for f in files:
    dest = f"/app/static/pyodide/{f}"
    urllib.request.urlretrieve(base + f, dest)
    print("downloaded", f, os.path.getsize(dest))
EOF

EXPOSE 9322

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9322"]