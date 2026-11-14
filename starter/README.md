# PostgreSQL + pgvector — thí nghiệm retrieval

Các module starter đã hiện thực pipeline PDF → chuẩn hóa → chunk → embedding local → pgvector → đánh giá top-3. Corpus là PDF NIST SP 800-63B-4 chính thức trong `data/`.

## Cài đặt (Windows PowerShell)

Cần Python 3.11+ và Docker Desktop. Chạy từ thư mục này:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

`.env` chọn `sentence-transformers/all-MiniLM-L6-v2` (384 chiều) qua FastEmbed. Model chạy local, dùng cùng encoder cho document và query, không cần API key. Lần đầu chạy sẽ tải model và lưu cache ngoài repository. Không commit `.env`.

## Chạy thí nghiệm theo giai đoạn

Từ `starter/`, chạy split dev 15 câu trước:

```powershell
python -m src.run --split dev
```

Xem metric dev và quy tắc chọn đã đăng ký trước trong `benchmark/selection_criteria.md`. Ghi strategy A/B/C và lý do vào `results/selection.json` **trước** khi chạy test. Lệnh test từ chối chạy nếu thiếu bản ghi lựa chọn:

```powershell
python -m src.run --split test
```

Test đầu tiên đã được xem trong pilot và được thay trước lần chạy đã sửa; xem `benchmark/test_set_history.md`. Kết quả test thay thế là exploratory, không phải holdout độc lập.

Corpus, model và benchmark 20 câu được giữ cố định. A dùng cửa sổ 700 ký tự, overlap 100; B nhóm paragraph tối đa 900 ký tự; C dùng cùng chunk B và áp dụng filter metadata `section` do câu hỏi cung cấp. PostgreSQL dùng exact cosine distance. Upsert thay snapshot của strategy trong transaction; pipeline chạy upsert lần nữa và kiểm tra số bản ghi để xác nhận không tạo bản sao.

## Kết quả

- `data/manifest.json`: nguồn, phiên bản/quyền, SHA-256, trang và lỗi trích xuất.
- `results/ingestion_report.json`: tổng hợp trang trống/lỗi.
- `results/traces.jsonl`: text/score top-3, source/page/section và nhãn evidence.
- `results/metrics.json`: Hit@1 và Evidence Hit@3 theo strategy/split.
- `results/run_metadata.json`: chiều model, phiên bản store, số chunk, thời gian và chi phí.
- `results/selection.json`: lựa chọn strategy chỉ dựa trên dev, lưu trước test.
- `results/metadata_audit.json`: kiểm tra source/page/section top-3 và tuân thủ filter C.
- `results/manual_audit.json`: mẫu coherence cùng vị trí và điểm grounding test kèm text/lý do.
- `results/failure_analysis.md`: miss và phân tích dựa trên trace.

Sau khi chạy cả hai split, tạo lại audit bằng:

```powershell
python scripts/audit_metadata.py
python scripts/build_manual_audit.py
python -m unittest discover -s tests -v
```

Xem README ở thư mục gốc để biết hướng dẫn đầy đủ và giới hạn.
